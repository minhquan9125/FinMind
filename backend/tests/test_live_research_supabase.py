"""Opt-in ASGI integration: actual read-only corpus + local embedding, no Gemini calls.

Run explicitly with RUN_LIVE_RESEARCH_SMOKE=1 and the existing offline HF cache.
"""
import hashlib
import json
import os
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(os.getenv('RUN_LIVE_RESEARCH_SMOKE') != '1',
                                reason='explicit opt-in for read-only Supabase/model smoke')


@pytest.mark.parametrize('retrieval_backend', ['dense', 'hybrid'])
def test_asgi_real_sources_and_b1_contract_without_gemini(tmp_path, retrieval_backend):
    import torch
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.core.db import connect, disconnect
    from src.documents.embeddings import get_embedding_service
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, LiveResearchService
    from src.retrieval_orchestration.web_sessions import SessionStore
    from src.api.routers import research_chat as api

    class LocalContractProvider:
        calls = 0

        async def count_tokens(self, request): return 100

        async def generate(self, request):
            self.calls += 1
            body = json.loads(request['contents'][0]['parts'][0]['text'])
            item = body['evidence'][0]
            metric = body['scope'].get('metric_code')
            text = (next(line for line in item['passage'].splitlines() if f'({metric})' in line)
                    if metric else item['passage'])
            return {'model_version': 'LOCAL_CONTRACT_TEST_NOT_GEMINI',
                    'usage': {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150},
                    'payload': {'claims': [{'text': text, 'evidence_ids': [item['evidence_id']],
                                           'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': item['passage']}]}]}}

    provider = LocalContractProvider()
    torch.set_num_threads(4)

    @asynccontextmanager
    async def lifespan(app):
        pool = await connect()
        app.state.store = SessionStore(tmp_path, engine=LiveResearchService(
            DenseEvidenceRetriever(pool, get_embedding_service(), backend=retrieval_backend,
                                   cache_dir=tmp_path / 'lexical-cache'), provider=provider))
        try: yield
        finally: await disconnect()

    app = FastAPI(lifespan=lifespan)
    app.include_router(api.router)
    owner = str(uuid4())
    app.dependency_overrides[api.get_owner] = lambda: owner
    app.dependency_overrides[api.get_store] = lambda: app.state.store
    receipts = []
    with TestClient(app) as client:
        created = client.post('/api/research/chat/sessions')
        assert created.status_code == 201
        snapshot = created.json()
        path = '/api/research/chat/sessions/' + snapshot['session_id']
        for question, expected_status, expected_period in (
            ('Tiền và tương đương tiền FPT quý 2/2026', 'EVIDENCE_READY', '2026-Q2'),
            ('Tin tức FPT tháng 9/2026', 'EVIDENCE_READY', '2026-09'),
            ('Tin tức FPT theo CafeF ngày 29/9/2026', 'EVIDENCE_READY', '2026-09-29'),
            ('Tổng tài sản FPT quý 4/2099', 'NO_DATA', '2099-Q4'),
        ):
            started = time.monotonic()
            response = client.post(path + '/messages', json={'text': question, 'revision': snapshot['revision']})
            assert response.status_code == 200
            snapshot = response.json()
            result = snapshot['messages'][-1]['result']
            assert result['scope']['periods'] == [expected_period]
            assert result['status'] == expected_status, result
            items = (result.get('evidence_pack') or {}).get('items', [])
            assert all(hashlib.sha256(item['passage'].encode()).hexdigest() == item['content_sha256'] for item in items)
            if items:
                assert result['answering']['status'] == 'DRAFT_READY'
                assert result['answering']['citations'][0]['locator'] == items[0]['locator']
                assert items[0]['score']['type'] == ('RRF' if retrieval_backend == 'hybrid' else 'COSINE_SIMILARITY')
                assert result['answering']['manifest']['retrieval_backend'] == retrieval_backend
                if result['scope'].get('publisher'):
                    from src.vector_retrieval.backend import _derive_publisher
                    assert all(_derive_publisher({'locator_json': item['locator']}) == 'cafef' for item in items)
            receipts.append({'status': result['status'], 'hits': len(items),
                             'seconds': round(time.monotonic()-started, 2)})
        calls = provider.calls
        assert client.get(path).json()['messages'] == snapshot['messages']
        assert client.post(path + '/resume').status_code == 201
        assert provider.calls == calls == 3
    print(json.dumps({'backend': retrieval_backend, 'real_source_asgi_smoke': receipts, 'gemini_calls': 0,
                      'history_resume_without_regeneration': True}))
