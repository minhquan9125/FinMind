"""Read-only clone preflight. No model downloads, Gemini calls or DB changes."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from demo_environment import load_demo_environment


async def check(connect=False):
    load_demo_environment(BACKEND)
    from src.core.config import get_settings
    settings=get_settings()
    checks=[]
    def record(name,ok,detail):checks.append(dict(check=name,status='OK' if ok else 'MISSING',detail=detail))
    record('database_config',bool(os.getenv('DATABASE_URL')) and 'PASSWORD' not in settings.database_url,
           'Set DATABASE_URL in backend/.env; no credentials are printed.')
    secret=settings.jwt_secret_key.get_secret_value()
    record('jwt_config',bool(os.getenv('JWT_SECRET_KEY')) and len(secret)>=32 and 'replace-' not in secret,
           'Set a private JWT secret of at least 32 characters.')
    record('gemini_config',bool(settings.gemini_api_key.get_secret_value() or settings.gemini_api_keys.get_secret_value()
           or settings.gemini_keys_secret.get_secret_value()) and settings.b1_gemini_free_tier_confirmed,
           'A usable key/key store and Free Tier confirmation are needed for generated answers; quota is not tested.')
    from src.retrieval_orchestration.intent_v2_classifier import DEFAULT_ARTIFACT
    record('classifier_artifacts',all((DEFAULT_ARTIFACT/name).is_file() for name in
           ('manifest.json','classifier.npz','fit.json','library/manifest.json','library/vectors.npy')),
           'Classifier files ship in Git; model weights download separately at first startup.')
    if connect:
        from src.core import db
        from src.documents.admin_ingestion import Queue
        from src.documents.repository import get_corpus_index
        try:
            pool=await asyncio.wait_for(db.connect(),15)
            cid=Queue(settings.admin_ingestion_directory).serving_corpus(settings.research_corpus_version_id)
            corpus=await asyncio.wait_for(get_corpus_index(pool,cid),15)
            record('postgres_corpus',bool(corpus and corpus['corpus_status']=='FROZEN' and corpus['index_status']=='ACTIVE'
                   and corpus['embedding_model']==settings.embedding_model_ref),'Serving corpus: '+str(cid))
        except Exception as exc:record('postgres_corpus',False,type(exc).__name__+'; check tunnel, corpus and runtime permissions.')
        finally:await db.disconnect()
        from src.graph.graph_store import GraphStore
        def graph_check():
            store=GraphStore.from_environment()
            try:
                with store.driver.session(database=store.database) as session:
                    session.run('RETURN 1 AS ready').single()
            finally:store.close()
        try:
            await asyncio.wait_for(asyncio.to_thread(graph_check),15)
            record('neo4j',True,'Connected; graph/source coverage must also pass verify_web_chat_graph.py.')
        except Exception as exc:record('neo4j',False,type(exc).__name__+'; check tunnel and Neo4j credentials.')
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    return 0 if all(c['status']=='OK' for c in checks) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect',action='store_true',help='Also SELECT from PostgreSQL and Neo4j.')
    args=parser.parse_args()
    raise SystemExit(asyncio.run(check(args.connect)))
