"""Read-only latest-news listing from the serving, source-verified DB corpus."""
import json
import uuid
from datetime import date, datetime, timezone, timedelta
from ..graph_review.sources import PostgresSourceReader
from ..b1_answering.evidence.citations import prepare_evidence
from .market_research import publication_time
from .news_presentation import has_recommendation_headline


async def latest_news(retriever, scope):
    corpus = await retriever._corpus()
    cid, iid = str(retriever.corpus_version_id), str(corpus['index_version_id'])
    symbols = scope.get('companies') or []
    day = (scope.get('_market_request') or {}).get('day')
    publisher = scope.get('publisher')
    query = (scope.get('_market_request') or {}).get('query')
    urls = scope.get('_article_urls') or []
    request=scope.get('_market_request') or {}
    analysis=request.get('action')=='ANALYSIS'
    as_of=date.fromisoformat(request['as_of']) if analysis and request.get('as_of') else None
    window_start=as_of-timedelta(days=30) if as_of else None
    items, seen = [], set()
    now = datetime.now(timezone(timedelta(hours=7)))
    async with retriever.pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            rows = await conn.fetch('''SELECT DISTINCT ON (d.document_id)
                d.document_id::text,d.title,d.source_url,t.chunk_id::text,t.locator_json,
                coalesce(t.locator_json->>'published_at',t.locator_json->'admin_news_snapshot'->>'published_at') AS published_at
                FROM corpus_documents cd JOIN documents d USING(document_id)
                JOIN text_chunks t ON t.document_id=d.document_id AND t.index_version_id=$2::uuid
                LEFT JOIN companies c USING(company_id)
                WHERE cd.corpus_version_id=$1::uuid AND cd.document_hash=d.sha256
                  AND d.doc_type='NEWS' AND t.superseded_at IS NULL
                  AND (cardinality($3::text[])=0 OR coalesce(c.symbol,t.locator_json->>'symbol')=ANY($3)
                       OR EXISTS (SELECT 1 FROM news_articles n WHERE n.article_id::text=t.locator_json->>'source_id'
                                  AND n.symbols && $3::text[]))
                ORDER BY d.document_id,t.chunk_index''', uuid.UUID(cid), uuid.UUID(iid), symbols)
            candidates = []
            for raw in rows:
                row = dict(raw)
                loc = json.loads(row['locator_json']) if isinstance(row['locator_json'],str) else row['locator_json']
                stamp = publication_time(row['published_at'])
                url = row['source_url'] or loc.get('url')
                if not stamp or stamp > now or (day and stamp.date().isoformat()!=day): continue
                if as_of and not window_start<=stamp.date()<=as_of: continue
                if urls and url not in urls: continue
                if publisher and publisher.lower() not in (loc.get('source') or loc.get('publisher') or url or '').lower(): continue
                if not urls and not query and has_recommendation_headline(row['title']): continue
                candidates.append((stamp,row,url))
            candidates.sort(key=lambda entry:(entry[0],entry[1]['document_id']), reverse=True)
            if query:
                from .market_dialogue import matching_articles
                matches = matching_articles(query,[dict(title=row['title'],url=url) for _,row,url in candidates])
                if not matches:
                    candidates=[]
                else:
                    # Several publishers/announcements may cover the same
                    # event. Read the matching sources (bounded below), rather
                    # than turning multiple supporting articles into NO_DATA.
                    matching_urls={item['url'] for item in matches}
                    candidates=[entry for entry in candidates if entry[2] in matching_urls]
            reader = PostgresSourceReader(conn)
            documents=0
            for stamp,row,url in candidates:
                if url and url in seen: continue
                refs=[dict(chunk_id=row['chunk_id'])]
                truncated=False
                if analysis or request.get('action') in ('DETAIL','SUMMARY'):
                    refs=await conn.fetch('''SELECT chunk_id::text FROM text_chunks WHERE document_id=$1::uuid
                        AND index_version_id=$2::uuid AND superseded_at IS NULL ORDER BY chunk_index LIMIT 9''',
                        uuid.UUID(row['document_id']),uuid.UUID(iid))
                    truncated=len(refs)>8
                    if truncated: refs=refs[:8]
                for ref in refs:
                    source = await reader.read_current(ref['chunk_id'],cid)
                    if source.index_version_id != iid or not source.active:
                        raise ValueError('Stored news is not active in the serving index')
                    items.append(dict(evidence_id=source.chunk_id,chunk_id=source.chunk_id,source_id=source.document_id,
                        source_type='NEWS',title=row['title'],passage=source.text,locator=source.locator,
                        source_url=url,source_sha256=source.source_sha256,content_sha256=source.content_hash,
                        source_verified=True,score=dict(type='RRF',value=1.0),
                        stored_news=dict(published_at=stamp.isoformat(),content_truncated=truncated)))
                if url: seen.add(url)
                documents+=1
                if documents==3: break
    pack=dict(schema_version='1.1',query_id=str(uuid.uuid4()),corpus_version_id=cid,
        data_version=dict(kind='INDEX',id=iid),items=items,retrieval_backend='stored_news_corpus')
    if items: prepare_evidence(pack)
    return pack


def render_stored_news(items):
    lines=['Tin mới nhất đã được pipeline thu thập và nạp vào kho dữ liệu FinMind:']
    for number,item in enumerate(items,1):
        stamp=datetime.fromisoformat(item['stored_news']['published_at'])
        lines.append(f"{number}. {item['title']}\nNgày đăng: {stamp:%d/%m/%Y} [{number}]")
    latest=max(datetime.fromisoformat(i['stored_news']['published_at']) for i in items)
    lines.append(f'Bài mới nhất trong kết quả đăng ngày {latest:%d/%m/%Y}. Đây là dữ liệu đã nạp, không lấy tin trực tiếp khi bạn hỏi.')
    return '\n\n'.join(lines)
