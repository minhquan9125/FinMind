from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routers import market_data as api
from src.auth.authorization import Principal,current_principal
from src.documents.admin_ingestion import Queue
from src.market_data.repository import FileMarketDataRepository


def test_market_fallback_only_exposes_completed_source_articles(tmp_path):
    root=tmp_path/'queue';q=Queue(root);job,_=q.create_job('CRAWL','admin');q.update_job(job,'RUNNING')
    ids=[]
    for status in ['PENDING','APPROVED','REJECTED','QUARANTINED','INDEXED']:
        aid,_=q.save_article(job,{'title':f'{status} title','source':'fireant',
            'url':f'https://fireant.vn/bai-viet/test/{len(ids)}','published_at':'2026-11-06T07:00:00+07:00',
            'content':'Public article text','raw':{'original':'source'}})
        with q.connect() as conn:conn.execute('UPDATE articles SET status=? WHERE id=?',(status,aid))
        ids.append(aid)
    app=FastAPI();app.state.admin_news_queue_root=root;app.include_router(api.router)
    app.dependency_overrides[api.get_market_data_repository]=lambda:FileMarketDataRepository(tmp_path/'empty-feed')
    with TestClient(app) as client:
        assert client.get('/api/market-data/news').status_code==401
        app.dependency_overrides[current_principal]=lambda:Principal(UUID(int=1),frozenset({'RESEARCHER'}))
        response=client.get('/api/market-data/news?limit=10')
        assert response.status_code==200
        items=response.json()['articles']
        assert len(items)==1 and items[0]['id']==ids[-1]
        assert items[0]['origin']=='admin_indexed'
        assert 'reviews' not in items[0] and 'raw' not in items[0]


def test_existing_market_feed_keeps_priority_and_unsafe_urls_are_filtered(tmp_path):
    from src.market_data.admin_news import published_admin_news
    q=Queue(tmp_path/'queue');job,_=q.create_job('CRAWL','admin');q.update_job(job,'RUNNING')
    aid,_=q.save_article(job,{'title':'Unsafe','url':'javascript:alert(1)','source':'fireant'})
    with q.connect() as conn:conn.execute("UPDATE articles SET status='INDEXED' WHERE id=?",(aid,))
    assert published_admin_news(q.root,10)==[]
    app=FastAPI();app.state.admin_news_queue_root=q.root;app.include_router(api.router)
    class Saved:
        def get_news(self,*args):return {'articles':[{'id':'saved','title':'Existing feed'}]}
    app.dependency_overrides[api.get_market_data_repository]=lambda:Saved()
    app.dependency_overrides[current_principal]=lambda:Principal(UUID(int=1),frozenset({'RESEARCHER'}))
    with TestClient(app) as client:assert client.get('/api/market-data/news').json()['articles'][0]['id']=='saved'


def test_market_news_falls_back_to_database_news_when_feeds_are_empty(tmp_path):
    app=FastAPI();app.include_router(api.router)
    app.dependency_overrides[api.get_market_data_repository]=lambda:FileMarketDataRepository(tmp_path/'empty-feed')
    app.dependency_overrides[current_principal]=lambda:Principal(UUID(int=1),frozenset({'RESEARCHER'}))
    async def db_news(limit):
        return [{'id':'doc-1','title':'Tin trong DB','url':'https://fireant.vn/bai-viet/x/1','published_at':'2026-11-18'}][:limit]
    app.dependency_overrides[api.get_db_news]=lambda:db_news
    with TestClient(app) as client:
        items=client.get('/api/market-data/news?limit=5').json()['articles']
    assert [item['id'] for item in items]==['doc-1']


def test_database_news_is_not_used_when_the_feed_has_articles(tmp_path):
    app=FastAPI();app.include_router(api.router)
    class Saved:
        def get_news(self,*args):return {'articles':[{'id':'saved','title':'Existing feed'}]}
    app.dependency_overrides[api.get_market_data_repository]=lambda:Saved()
    app.dependency_overrides[current_principal]=lambda:Principal(UUID(int=1),frozenset({'RESEARCHER'}))
    async def db_news(limit): raise AssertionError('database must not be read')
    app.dependency_overrides[api.get_db_news]=lambda:db_news
    with TestClient(app) as client:
        assert [i['id'] for i in client.get('/api/market-data/news').json()['articles']]==['saved']


def test_db_news_rows_become_safe_articles():
    from src.market_data.db_news import to_article
    ok=to_article({'id':'d1','title':'T','source_url':'https://fireant.vn/bai-viet/a/1','published_at':'2026-11-18'})
    assert ok=={'id':'d1','title':'T','description':'','url':'https://fireant.vn/bai-viet/a/1','published_at':'2026-11-18',
                'category':None,'marker':'uncheck','source':'fireant','origin':'database'}
    assert to_article({'id':'d2','title':'T','source_url':'javascript:alert(1)','published_at':None})['url'] is None
