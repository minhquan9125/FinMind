"""Legacy diagnostic of Nhan's 23 candidates, Vu's metadata and Quan's news.

Do not use this diagnostic as final Vu/Quan acceptance: its one-chunk quote
adapter cannot represent FULL_PDF_PAGE / FULL_WEB_SNAPSHOT evidence and its
article-ID deduplication loses per-folder occurrences. Use
recheck_vu_quan_sources.py and the source-audited handoffs instead.

No migration, source update, review update, LLM, embedding or Neo4j writes.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
import asyncpg
from src.core.config import get_settings
from src.graph_review.adapters import entity, from_handoff, from_news_article, source_ref
from src.graph_review.engine import IdentityRegistry, ReviewEngine, EVENT_CUES, text_key
from src.graph_review.models import digest
from src.graph_review.sources import PostgresSourceReader


def obj(value):
    return json.loads(value) if isinstance(value, str) else value


async def person_candidates(c, reader, registry):
    rows = await c.fetch("""SELECT a.*,v.corpus_version_id::text AS corpus_id,
        v.index_version_id::text AS index_id,g.source_span,
        s.entity_type AS st,s.canonical_name AS sn,s.resolution_status AS sr,
        o.entity_type AS ot,o.canonical_name AS oname,o.resolution_status AS ores
        FROM graph_metadata.assertions a JOIN graph_metadata.versions v USING(graph_version_id)
        JOIN public.graph_extractions g USING(extraction_id)
        JOIN graph_metadata.entities s ON s.graph_version_id=a.graph_version_id AND s.entity_id=a.subject_id
        JOIN graph_metadata.entities o ON o.graph_version_id=a.graph_version_id AND o.entity_id=a.object_id
        ORDER BY a.extraction_id""")
    output = []
    for ordinal, row in enumerate(rows, 1):
        p = obj(row["payload"]); evidence = []; errors = []
        if digest(p) != row["content_sha256"]:
            errors.append("ERR_CANDIDATE_HASH_MISMATCH")
        quote = row["source_span"] or ""
        # This schema stores locators, not chunk text. Replay registered sources.
        bindings = await c.fetch("""SELECT s.chunk_id::text,s.content_hash
            FROM graph_metadata.source_chunks s
            WHERE s.extraction_id=$1 ORDER BY s.chunk_id""", row["extraction_id"])
        unavailable = set()
        for binding in bindings:
            try:
                actual = await reader.read_current(binding["chunk_id"], row["corpus_id"])
                if quote and quote in actual.text:
                    evidence.append(source_ref(actual, quote, content_hash=binding["content_hash"]))
                    break
            except Exception as exc:
                unavailable.add(getattr(exc, "code", "ERR_SOURCE_UNAVAILABLE"))
        if not evidence:
            errors.extend(unavailable or {"ERR_EVIDENCE_UNGROUNDED"})
        def ep(which):
            key = "subject_id" if which == "s" else "object_id"
            return entity(dict(entity_id=str(row[key]), entity_type=row["st" if which == "s" else "ot"],
                canonical_name=row["sn" if which == "s" else "oname"],
                resolution_status="unresolved", aliases=[]), registry)
        output.append(dict(candidate_id=str(row["extraction_id"]), group="person", relation_type=row["relation_type"],
            subject=ep("s"), object=ep("o"), evidence=evidence, attributes={"position": p.get("position")},
            temporal={"valid_from": p.get("effective_date")},
            conflicts=["SOURCE_CONFLICT"] if p.get("validation_status") == "SOURCE_CONFLICT" else [],
            extractor_metadata={"format": "source-bound-person-role-v2", "original_review_status": p.get("review_status"),
                "original_validation_status": p.get("validation_status"), "original_resolution": [row["sr"],row["ores"]],
                "input_errors": sorted(set(errors)), "raw_sha256": row["content_sha256"]}))
        if ordinal % 30 == 0:
            print(f'PERSON_SOURCE_CHECK {ordinal}/{len(rows)}',flush=True)
    return output


async def news_candidates(c, reader, registry):
    candidates, articles, preliminary = [], {}, []
    for path in sorted((ROOT / "data/News").glob("*/batch_extracted.json")):
        for article in json.loads(path.read_text("utf-8-sig")):
            articles.setdefault(article["article_id"], (article, str(path.relative_to(ROOT))))
    for ordinal,(article_id, (article, filename)) in enumerate(articles.items(), 1):
        normalized = from_news_article(article, registry)
        source_rows = await c.fetch("""SELECT DISTINCT t.chunk_id::text,cv.corpus_version_id::text AS corpus_id
            FROM public.text_chunks t JOIN public.documents d USING(document_id)
            JOIN public.index_versions i USING(index_version_id)
            JOIN public.corpus_versions cv ON cv.index_version_id=i.index_version_id
            JOIN public.corpus_documents cd ON cd.corpus_version_id=cv.corpus_version_id AND cd.document_id=d.document_id
            WHERE t.locator_json->>'source_table'='news_articles' AND t.locator_json->>'source_id'=$1
              AND t.superseded_at IS NULL AND i.status='ACTIVE' AND cv.status IN ('ACTIVE','FROZEN')""", article_id)
        for item in normalized:
            quote = item["extractor_metadata"]["original_quote"] or ""
            bound = []
            for row in source_rows:
                try:
                    actual = await reader.read_current(row["chunk_id"], row["corpus_id"])
                    if quote and quote in actual.text:
                        bound.append(actual)
                except Exception:
                    continue
            if len(bound) == 1:
                item["evidence"] = [source_ref(bound[0], quote)]
                item["extractor_metadata"]["input_errors"] = []
            elif len(bound) > 1:
                item["extractor_metadata"]["input_errors"] = ["ERR_SOURCE_BINDING_AMBIGUOUS"]
            item["extractor_metadata"]["file"] = filename
            candidates.append(item)
        for event in article.get("events", []):
            quote = " ".join(filter(None, [event.get("event_name_evidence"),event.get("status_evidence")]))
            cue = EVENT_CUES.get(event.get("event_type"))
            import re
            if cue and not re.search(cue, text_key(quote)):
                preliminary.append(dict(article_id=article_id, event_id=event["local_event_id"], file=filename,
                    code="ERR_EVENT_TYPE_UNGROUNDED", proposed_type=event.get("event_type"), quote=quote,
                    basis="LOCAL_EXTRACTOR_OUTPUT_REVIEW_NOT_LIVE_SOURCE_VERIFICATION"))
        if ordinal % 40 == 0:
            print(f'NEWS_SOURCE_CHECK {ordinal}/{len(articles)}',flush=True)
    return candidates, {"article_count": len(articles), "preliminary_findings": preliminary}


async def main(args):
    registry_path=Path(args.registry) if args.registry else ROOT/"backend/src/sprint4_runtime/company.registry.20261030.r1.json"
    registry = IdentityRegistry(json.loads(registry_path.read_text("utf-8")))
    handoff = json.loads(subprocess.check_output(["git","show",args.handoff_ref+":docs/sprint4/WBS03-23-candidate-review.json"],cwd=ROOT))
    connection = await asyncpg.connect(get_settings().database_url, timeout=15, statement_cache_size=0)
    report = {"policy": "wbs06-evidence-v1", "checked_at": datetime.now(timezone.utc).isoformat(),
              "database_writes": 0, "neo4j_writes": 0, "registry_sha256": registry.sha256,
              "registry_file_sha256": __import__('hashlib').sha256(registry_path.read_bytes()).hexdigest(),
              "handoff_ref": args.handoff_ref,
              "handoff_commit": subprocess.check_output(['git','rev-parse',args.handoff_ref],cwd=ROOT,text=True).strip(),
              "handoff_sha256": digest(handoff), "owners": {}}
    try:
        async with connection.transaction(readonly=True,isolation="repeatable_read"):
            reader=PostgresSourceReader(connection);engine=ReviewEngine(reader,registry)
            if args.input_snapshot:
                prior=json.loads(Path(args.input_snapshot).read_text('utf-8'))
                groups=[(owner,[x['candidate'] for x in data['items']]) for owner,data in prior['owners'].items()]
                report['input_snapshot_sha256']=digest(prior)
                report['input_snapshot_checked_at']=prior['checked_at']
                report['news']=prior['news']
                # Recheck saved extractor input, not its old APPROVED flags.
                # Every supplied source is independently replayed again below.
                import re
                report['news']['preliminary_findings']=[x for x in report['news']['preliminary_findings']
                    if not re.search(EVENT_CUES.get(x['proposed_type'],r'(?!)'),text_key(x['quote']))]
            else:
                groups = []
                selected=set(args.owner or ('NHAN','VU','QUAN'))
                if 'NHAN' in selected:
                    items=await from_handoff(handoff,reader,registry)
                    groups.append(('NHAN',items))
                    print('NHAN_SOURCE_CHECK',len(items),flush=True)
                if 'VU' in selected:
                    groups.append(("VU",await person_candidates(connection,reader,registry)))
                if 'QUAN' in selected:
                    news, news_info=await news_candidates(connection,reader,registry)
                    groups.append(("QUAN",news));report["news"]=news_info
            report["graph_states"]=[dict(r) for r in await connection.fetch('SELECT graph_version_id::text,status FROM public.graph_versions')]
            for owner,items in groups:
                results=await engine.evaluate_batch(items)
                report["owners"][owner]={"count":len(items),"statuses":dict(Counter(r.status for r in results)),
                    "reasons":dict(Counter(code for r in results for code in r.reasons)),
                    "source_verified":sum(r.source_verified for r in results),
                    "items":[{"candidate":i,"result":r.model_dump(mode="json"),"load_allowed":r.load_allowed} for i,r in zip(items,results)]}
                print(owner,json.dumps({k:v for k,v in report['owners'][owner].items() if k!='items'}),flush=True)
    finally:
        await connection.close()
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print('READ_ONLY_REPORT',target)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--handoff-ref',default='origin/nhan-sprint-401')
    parser.add_argument('--input-snapshot',help='Recheck saved input candidates against LIVE DB; never trust saved decisions')
    parser.add_argument('--owner',action='append',choices=['NHAN','VU','QUAN'],help='Audit only selected handoff owners')
    parser.add_argument('--registry',help='Trusted registry version used by the extractor being reviewed')
    asyncio.run(main(parser.parse_args()))
