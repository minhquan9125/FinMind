"""Public source metadata from completed admin ingestion, never review drafts."""
import json
from urllib.parse import urlsplit


def published_admin_news(root, limit):
    from ..documents.admin_ingestion import Queue
    queue=Queue(root)
    with queue.connect() as conn:
        rows=conn.execute('''SELECT id,payload FROM articles WHERE status='INDEXED'
            ORDER BY datetime(json_extract(payload,'$.published_at')) DESC,created_at DESC,id
            LIMIT ?''',(limit*3,)).fetchall()
    articles=[];seen=set()
    for row in rows:
        payload=json.loads(row['payload']);url=payload.get('url') or ''
        try:parsed=urlsplit(url)
        except ValueError:continue
        if (payload.get('source')!='fireant' or parsed.scheme!='https'
                or parsed.hostname not in ('fireant.vn','www.fireant.vn')
                or parsed.username or parsed.password or not payload.get('title') or url in seen):continue
        seen.add(url)
        articles.append({'id':row['id'],'title':payload['title'],'url':url,
            'published_at':payload.get('published_at'),'source':'fireant',
            'description':payload.get('description') or (payload.get('content') or '')[:240],
            'origin':'admin_indexed'})
        if len(articles)>=limit:break
    return articles
