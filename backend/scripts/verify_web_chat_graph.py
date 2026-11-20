"""Read-only graph/source integration smoke test. Does not call Gemini."""
import asyncio
import json
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main():
    os.chdir(BACKEND)
    from src.core.config import get_settings
    from src.core import db
    from src.documents.admin_ingestion import Queue
    from src.graph.graph_store import GraphStore
    from src.graph.viewer import GraphViewerReader
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever
    from src.retrieval_orchestration.web_chat_router import Neo4jChatRetriever
    from src.retrieval_orchestration.hybrid_router.decision_engine import ArtifactPredictor, DecisionEngine
    from src.api.routers.graph_viewer import get_ticker_map
    settings = get_settings()
    pool = await db.connect()
    store = None
    rows = []
    try:
        store = await asyncio.to_thread(GraphStore.from_environment)
        reader = GraphViewerReader(store.driver, database=store.database)
        dense = DenseEvidenceRetriever(pool, None, corpus_version_id=settings.research_corpus_version_id,
            model_ref=settings.embedding_model_ref, backend=settings.research_retrieval_backend,
            corpus_resolver=lambda: Queue(settings.admin_ingestion_directory).serving_corpus(settings.research_corpus_version_id))
        graph = Neo4jChatRetriever(dense, lambda: reader, get_ticker_map)
        engine = DecisionEngine(ArtifactPredictor())
        for question in ('Ai là Chủ tịch FPT?', 'Chủ tịch HĐQT của VCB là ai?',
                         'Ai là Chủ tịch TCB?', 'Liệt kê hội đồng quản trị FPT.'):
            plan = engine.decide(question)
            try:
                pack, facts = await asyncio.wait_for(graph.retrieve(plan.scope), 40)
                row = dict(question=question, route=plan.route, evidence_count=len(pack['items']),
                    relation_count=len(facts), corpus_version_id=pack['corpus_version_id'],
                    graph_versions=sorted({f['graph_version_id'] for f in facts}),
                    status='VERIFIED' if pack['items'] else 'NO_DATA')
            except Exception as exc:
                row = dict(question=question, route=plan.route, status='BLOCKED',
                           reason_code=getattr(exc, 'code', type(exc).__name__))
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        if store:
            await asyncio.to_thread(store.close)
        await db.disconnect()
    output = BACKEND.parent / 'outputs/web-chat-router-20261108/live-source-smoke.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    asyncio.run(main())
