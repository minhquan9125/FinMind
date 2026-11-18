"""Frozen-source NEWS pack for offline chat tests (never a network feed)."""
from datetime import datetime
from uuid import uuid4
from src.documents.db_chunking import news_documents, chunk_document


def stored_pack(entries, scope, content):
    items=[]
    urls=scope.get('_article_urls') or []
    for entry in entries:
        if urls and entry['url'] not in urls: continue
        doc=news_documents([dict(article_id=str(uuid4()),title=entry['title'],content=content,
            published_at=datetime.fromisoformat(entry['published_at']),source='fireant',
            symbols=scope['companies'],url=entry['url'])])[0]
        chunk=chunk_document(doc)[0]
        items.append(dict(evidence_id=chunk.chunk_id,chunk_id=chunk.chunk_id,source_id=doc.document_id,
            source_type='NEWS',title=doc.title,passage=chunk.text,locator=chunk.locator,source_url=entry['url'],
            source_sha256='a'*64,content_sha256=chunk.content_hash,source_verified=True,
            score=dict(type='RRF',value=1.0),stored_news=dict(published_at=entry['published_at'])))
    return dict(schema_version='1.1',query_id=str(uuid4()),corpus_version_id=str(uuid4()),
        data_version=dict(kind='INDEX',id=str(uuid4())),items=items,retrieval_backend='stored_news_corpus')
