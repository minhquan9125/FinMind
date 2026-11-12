"""Read-only annual-report retrieval smoke test; never calls Gemini."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main():
    os.chdir(BACKEND)
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    from src.core.config import get_settings
    from src.core import db
    from src.documents.embeddings import get_embedding_service
    from src.documents.admin_ingestion import Queue
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, analyze_live
    from src.b1_answering.evidence.citations import prepare_evidence
    settings = get_settings()
    pool = await db.connect()
    output = BACKEND.parent / 'outputs/web-chat-annual-20261108/live-source-smoke.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    try:
        retriever = DenseEvidenceRetriever(pool, get_embedding_service(),
            corpus_version_id=settings.research_corpus_version_id, model_ref=settings.embedding_model_ref,
            backend=settings.research_retrieval_backend,
            corpus_resolver=lambda: Queue(settings.admin_ingestion_directory).serving_corpus(settings.research_corpus_version_id))
        print('Preparing verified retrieval cache (local model only; no Gemini).', flush=True)
        await asyncio.wait_for(retriever.warmup(), 300)
        for symbol in ('BID','CMG','CTG','ELC','FPT','ICT','ITD','MBB','TCB','VCB'):
            question = f'Theo BCTN {symbol} năm 2025, định hướng và chiến lược phát triển là gì?'
            decision = analyze_live(question)
            started = time.monotonic()
            try:
                if decision['decision'] != 'SEARCH':
                    raise RuntimeError(decision['reason_code'])
                pack = await asyncio.wait_for(retriever.retrieve(question, decision['scope']), 45)
                evidence = prepare_evidence(pack)
                exact = all(i['source_type'] == 'BCTN' and str(i['locator'].get('reporting_year')) == '2025'
                            and i['locator'].get('symbol') == symbol
                            and type(i['locator'].get('pdf_page')) is int for i in evidence.values())
                row = dict(company=symbol, status='VERIFIED' if exact else 'SCOPE_MISMATCH',
                    evidence_count=len(evidence), seconds=round(time.monotonic()-started,2),
                    pages=sorted({i['locator']['pdf_page'] for i in evidence.values()}),
                    corpus_version_id=pack['corpus_version_id'], index_version_id=pack['data_version']['id'])
            except Exception as exc:
                row = dict(company=symbol, status='BLOCKED', reason_code=getattr(exc, 'code', type(exc).__name__),
                    seconds=round(time.monotonic()-started,2))
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')
    finally:
        await db.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
