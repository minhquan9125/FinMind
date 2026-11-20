"""Latest market news already ingested into the database (the same NEWS documents the chat reads)."""
from urllib.parse import urlsplit

_SQL = """
SELECT d.document_id::text AS id, d.title, d.source_url,
       coalesce(d.published_at::date::text,
                (SELECT coalesce(t.locator_json->>'published_at', t.locator_json->'admin_news_snapshot'->>'published_at')
                 FROM text_chunks t WHERE t.document_id = d.document_id LIMIT 1)) AS published_at
FROM documents d
WHERE d.doc_type = 'NEWS' AND coalesce(d.title, '') <> ''
ORDER BY 4 DESC NULLS LAST
LIMIT $1
"""


def to_article(row):
    url = row.get('source_url') or ''
    parsed = urlsplit(url)
    safe = url if parsed.scheme == 'https' and parsed.hostname in ('fireant.vn', 'www.fireant.vn') else None
    return {'id': row['id'], 'title': row['title'], 'description': '', 'url': safe,
            'published_at': row.get('published_at'), 'category': None, 'marker': 'uncheck',
            'source': 'fireant', 'origin': 'database'}


async def recent_db_news(pool, limit):
    async with pool.acquire() as conn:
        return [to_article(dict(row)) for row in await conn.fetch(_SQL, limit)]
