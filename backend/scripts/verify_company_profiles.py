"""Read-only profile source verification for the ten project companies; no LLM."""
import asyncio, json, os
from pathlib import Path
import sys
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

async def main():
    os.chdir(BACKEND)
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    from src.core.config import get_settings
    from src.core import db
    from src.documents.embeddings import get_embedding_service
    from src.documents.admin_ingestion import Queue
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, analyze_live
    from src.b1_answering.evidence.citations import prepare_evidence
    settings = get_settings()
    pool = await db.connect()
    rows = []
    try:
        reader = DenseEvidenceRetriever(pool, get_embedding_service(),
            corpus_version_id=settings.research_corpus_version_id, model_ref=settings.embedding_model_ref,
            backend=settings.research_retrieval_backend,
            corpus_resolver=lambda: Queue(settings.admin_ingestion_directory).serving_corpus(settings.research_corpus_version_id))
        for symbol in ('BID','CMG','CTG','ELC','FPT','ICT','ITD','MBB','TCB','VCB'):
            question = 'Thông tin công ty ' + symbol
            scope = analyze_live(question)['scope']
            try:
                pack = await asyncio.wait_for(reader.retrieve(question, scope), 30)
                items = list(prepare_evidence(pack).values())
                ok = bool(items) and all(i['source_type'] == 'COMPANY_PROFILE' and i['locator'].get('symbol') == symbol for i in items)
                row = dict(company=symbol, verified=ok, evidence_count=len(items))
            except Exception as exc:
                row = dict(company=symbol, verified=False, error=getattr(exc, 'code', type(exc).__name__))
            rows.append(row)
            print(json.dumps(row), flush=True)
        output = BACKEND.parent/'outputs/company-profile-20261108/verification.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(rows, indent=2), encoding='utf8')
    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
