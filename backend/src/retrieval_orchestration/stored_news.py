"""Read-only latest-news listing from the serving, source-verified DB corpus."""
import json
import re
import uuid
from datetime import date, datetime, timezone, timedelta
from ..graph_review.sources import PostgresSourceReader
from ..b1_answering.evidence.citations import prepare_evidence
from .market_research import publication_time
from .news_presentation import has_recommendation_headline
from .retrieval_flow.intent import _fold


def rank_article_chunks(query, items):
    """Prefer answer-bearing body text over repeated PDF/news headers.

    Retrieval selects documents; this bounded rerank selects their passages for
    the model's input window. It never changes source text or citation binding.
    """
    stop = set('cho toi minh biet hay theo trong bai tin tuc cua va la co cac nhung duoc '
               'voi tu tai the nay do ai gi nao nhu sao dang ngay thang nam bao nhieu '
               'thong bao ve'.split())
    words = set(re.findall(r'[a-z0-9]+', _fold(query))) - stop
    def dates(text):
        found=set()
        for match in re.finditer(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b|\b(\d{1,2})[./](\d{1,2})[./]((?:19|20|21)\d{2})\b',text):
            parts=match.groups()
            try:
                y,m,d=map(int,parts[:3]if parts[0]else(parts[5],parts[4],parts[3]))
                found.add(date(y,m,d))
            except ValueError:pass
        return found
    requested_dates=dates(query)
    def score(item):
        body = item['passage'].partition('\n')[2]
        tokens = set(re.findall(r'[a-z0-9]+', _fold(body)))
        title=item.get('title')or item['passage'].partition('\n')[0]
        title_tokens=set(re.findall(r'[a-z0-9]+',_fold(title)))
        # Keep informative headlines and exact calendar hints ahead of generic
        # newer documents. A relevance hint is not a publication-date filter.
        temporal=bool(requested_dates&dates(item['passage']))
        return len(words&tokens)+2*len(words&title_tokens)+6*temporal
    return sorted(items, key=score, reverse=True)


async def latest_news(retriever, scope):
    corpus = await retriever._corpus()
    cid, iid = str(retriever.corpus_version_id), str(corpus['index_version_id'])
    symbols = scope.get('companies') or []
    day = (scope.get('_market_request') or {}).get('day')
    month = (scope.get('_market_request') or {}).get('month')
    publisher = scope.get('publisher')
    query = (scope.get('_market_request') or {}).get('query')
    urls = scope.get('_article_urls') or []
    request=scope.get('_market_request') or {}
    # Search article bodies through the existing vector/BM25 reader. A natural
    # question need not repeat a headline. The resulting IDs only rank corpus
    # members below; their text is replayed and verified again before citation.
    ranked_documents = []
    ranked_chunks = {}
    if query and not urls:
        search_scope = {**scope, 'source_type': 'NEWS', 'metric_code': None,
                        'periods': [day or month] if day or month else ['LATEST_AVAILABLE_PERIOD'], 'reporting_entity': 'UNKNOWN'}
        # Article tags are OR filters. A story may mention a parent, subsidiary
        # or counterparty that has no separately indexed company document.
        for symbol in symbols or [None]:
            child={**search_scope,'companies':[symbol] if symbol else []}
            found = await retriever.retrieve(query, child)
            if (str(found['corpus_version_id']) != cid
                    or str(found['data_version']['id']) != iid):
                raise ValueError('Serving corpus changed during news search')
            if found.get('items'):
                prepare_evidence(found)
                for item in found['items']:
                    document=str(item['source_id'])
                    if document not in ranked_documents:ranked_documents.append(document)
                    ranked_chunks.setdefault(document, []).append(item['chunk_id'])
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
                if month and stamp.strftime('%Y-%m')!=month:continue
                if as_of and not window_start<=stamp.date()<=as_of: continue
                if urls and url not in urls: continue
                if publisher and publisher.lower() not in (loc.get('source') or loc.get('publisher') or url or '').lower(): continue
                if not urls and not query and has_recommendation_headline(row['title']): continue
                candidates.append((stamp,row,url))
            candidates.sort(key=lambda entry:(entry[0],entry[1]['document_id']), reverse=True)
            anchor=scope.get('_article_anchor')or{}
            if (urls and anchor.get('corpus_version_id')==cid and anchor.get('index_version_id')==iid):
                anchor_documents={v['document_id']for v in anchor.get('chunks',[])}
                # Several frozen snapshots can share a URL. Deduplicating by
                # URL must retain the exact document cited in the prior turn.
                candidates.sort(key=lambda entry:entry[1]['document_id']not in anchor_documents)
            if query and not urls:
                from .market_dialogue import matching_articles
                matches = matching_articles(query,[dict(title=row['title'],url=url) for _,row,url in candidates])
                matching_urls={item['url'] for item in matches}
                candidates=[entry for entry in candidates if entry[2] in matching_urls
                            or entry[1]['document_id'] in ranked_documents]
                # An exact headline outranks semantic candidates; otherwise
                # retain the retrieval ranking rather than recency alone.
                candidates.sort(key=lambda entry: (entry[2] not in matching_urls,
                    ranked_documents.index(entry[1]['document_id'])
                    if entry[1]['document_id'] in ranked_documents else len(ranked_documents)))
            reader = PostgresSourceReader(conn)
            documents=0
            for stamp,row,url in candidates:
                if url and url in seen: continue
                refs=[dict(chunk_id=row['chunk_id'])]
                truncated=False
                if analysis or request.get('action') in ('DETAIL','SUMMARY'):
                    refs=await conn.fetch('''SELECT chunk_id::text FROM text_chunks WHERE document_id=$1::uuid
                        AND index_version_id=$2::uuid AND superseded_at IS NULL ORDER BY chunk_index LIMIT 65''',
                        uuid.UUID(row['document_id']),uuid.UUID(iid))
                    truncated=len(refs)>8
                    # Put the semantic hits first, including a hit beyond the
                    # bounded article prefix. Then provide adjacent context.
                    ordered=[ref['chunk_id'] for ref in refs]
                    anchor=scope.get('_article_anchor')or{}
                    anchors=([v['chunk_id']for v in anchor.get('chunks',[])
                        if v['document_id']==row['document_id']]
                        if anchor.get('corpus_version_id')==cid and anchor.get('index_version_id')==iid else [])
                    hits=list(dict.fromkeys(anchors+ranked_chunks.get(row['document_id'], [])))
                    selected=list(dict.fromkeys(hits))[:5]
                    for hit in hits:
                        if hit in ordered:
                            index=ordered.index(hit)
                            for neighbor in ordered[max(0,index-1):index+2]:
                                if neighbor not in selected: selected.append(neighbor)
                    selected=list(dict.fromkeys(selected + ordered))[:8]
                    refs=[dict(chunk_id=chunk) for chunk in selected]
                for ref in refs:
                    source = await reader.read_current(ref['chunk_id'],cid)
                    if source.index_version_id != iid or not source.active or str(source.document_id) != row['document_id']:
                        raise ValueError('Stored news is not active in the serving index')
                    items.append(dict(evidence_id=source.chunk_id,chunk_id=source.chunk_id,source_id=source.document_id,
                        source_type='NEWS',title=row['title'],passage=source.text,locator=source.locator,
                        source_url=url,source_sha256=source.source_sha256,content_sha256=source.content_hash,
                        source_verified=True,score=dict(type='RRF',value=1.0),
                        stored_news=dict(published_at=stamp.isoformat(),content_truncated=truncated)))
                if url: seen.add(url)
                documents+=1
                if documents==3: break
    if query:
        subject=' '.join(scope.get('_article_subject_quotes')or[])
        items=rank_article_chunks(query+' '+subject,items)
    pack=dict(schema_version='1.1',query_id=str(uuid.uuid4()),corpus_version_id=cid,
        data_version=dict(kind='INDEX',id=iid),items=items,retrieval_backend='stored_news_corpus')
    if items: prepare_evidence(pack)
    return pack


def render_stored_news(items):
    lines=['Tin mới nhất đã được pipeline thu thập và nạp vào kho dữ liệu FinMind:']
    for number,item in enumerate(items,1):
        stamp=datetime.fromisoformat(item['stored_news']['published_at'])
        lines.append(f"{number}. {item['title']}\nNgày đăng: {stamp:%d/%m/%Y} [{number}]")
        excerpt=news_body_excerpt(item)
        lines.append(f'Nội dung chính (trích nguồn): {excerpt} [{number}]' if excerpt else
                     'Kho hiện chưa có đoạn nội dung đủ để tóm tắt tin này; mới xác định được tiêu đề và ngày đăng.')
    latest=max(datetime.fromisoformat(i['stored_news']['published_at']) for i in items)
    lines.append(f'Bài mới nhất trong kết quả đăng ngày {latest:%d/%m/%Y}. Đây là dữ liệu đã nạp, không lấy tin trực tiếp khi bạn hỏi.')
    return '\n\n'.join(lines)


def news_body_excerpt(item):
    """Bounded verbatim body excerpt; never infer an article from its headline."""
    title=' '.join((item.get('title') or '').split())
    body=[]
    for line in (item.get('passage') or '').splitlines():
        clean=' '.join(line.split())
        if not clean or clean==title:continue
        if re.match(r'^(?:Ngày đăng:|Ngày xuất bản:|https?://)',clean):continue
        if '|' in clean and re.search(r'NEWS|Tin tức|Nguồn:|Ngày đăng|PDF trang',clean):continue
        body.append(clean)
    text=' '.join(body)
    if len(text)<60:return None
    sentences=re.split(r'(?<=[.!?])\s+',text)
    excerpt=' '.join(sentences[:2])
    if len(excerpt)>600:
        excerpt=excerpt[:600].rsplit(' ',1)[0]+'…'
    return excerpt
