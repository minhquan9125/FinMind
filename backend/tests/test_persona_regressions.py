"""User-facing regressions found by novice/expert conversation evaluation."""
import asyncio
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest

from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService
from src.retrieval_orchestration.web_sessions import SessionStore
from src.b1_answering.evidence.grounded import build_grounded_request
from src.b1_answering.core.policy import Limits
from tests.test_live_research import Retriever, Provider


def test_all_recorded_novice_and_expert_interpretations():
    script = Path(__file__).resolve().parents[1] / 'scripts/evaluate_research_personas.py'
    spec = importlib.util.spec_from_file_location('personas', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failed = [row for row in module.evaluate_parser() if not row['passed']]
    assert not failed, [(row['title'], row['turns']) for row in failed]


@pytest.mark.parametrize('question', [
    'LNST FPT quý 4/2025', 'LNTT FPT quý 4/2025',
    'lợi nhuận của FPT quý 4 sau thuế năm 2025 là bao nhiêu',
])
def test_metric_abbreviations_never_become_company(question):
    result = analyze_live(question)
    assert result['decision'] == 'SEARCH'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['periods'] == ['2025-Q4']


@pytest.mark.parametrize('question', [
    'lợi nhuận sau thuế FPT quý 4 năm 2025 và quý 3 năm 2026',
    'lợi nhuận sau thuế FPT quý 4 năm 2025 và 2026-Q4',
    'lợi nhuận sau thuế FPT quý 5 sau thuế năm 2025',
])
def test_ambiguous_or_invalid_quarters_do_not_silently_choose(question):
    assert analyze_live(question)['decision'] == 'ASK_CLARIFICATION'


def test_pending_quarter_cleared_by_reset_or_explicit_full_year():
    first = analyze_live('lợi nhuận FPT quý 4 sau thuế')['scope']
    year = analyze_live('cả năm 2025', first)
    assert year['scope']['periods'] == ['2025']
    reset = analyze_live('/moi', first)
    assert reset['scope'] == {}
    assert analyze_live('2025', reset['scope'])['decision'] == 'ASK_CLARIFICATION'


def test_pending_quarter_does_not_leak_into_new_company_or_metric():
    pending = analyze_live('lợi nhuận FPT quý 4 sau thuế')['scope']
    other = analyze_live('tổng tài sản SSI năm 2026', pending)
    assert other['scope']['periods'] == ['2026']
    assert other['scope']['companies'] == ['SSI']


def test_parent_share_metric_does_not_select_parent_only_statement():
    result = analyze_live('LNST cổ đông công ty mẹ FPT quý 4/2025')
    assert result['scope']['metric_code'] == 'PARENT_NET_PROFIT'
    assert result['scope']['reporting_entity'] == 'UNKNOWN'
    separate = analyze_live('LNST cổ đông công ty mẹ FPT báo cáo riêng quý 4/2025')
    assert separate['scope']['reporting_entity'] == 'PARENT'


def test_source_reference_uses_saved_response_without_retrieval_or_gemini(tmp_path):
    async def run():
        retriever, provider = Retriever(), Provider()
        retriever.evidence['items'][0]['title'] = 'Clean mapped financial report '+str(uuid4())
        store = SessionStore(tmp_path, engine=LiveResearchService(retriever, provider=provider))
        owner = str(uuid4())
        snap = await store.create(owner)
        sid = snap['session_id']
        snap = await store.send(owner, sid, 'tiền và tương đương tiền FPT quý 2/2026', 0)
        citations = snap['messages'][-1]['result']['answering']['citations']
        snap = await store.send(owner, sid, 'nguồn đâu', 1)
        assert len(retriever.calls) == provider.calls == 1
        assert snap['messages'][-1]['result']['answering']['citations'] == citations
        assert 'nguồn' in snap['messages'][-1]['content'].lower()
        assert 'Clean mapped' not in snap['messages'][-1]['content']
        snap = await store.send(owner, sid, '/moi', 2)
        snap = await store.send(owner, sid, 'nguồn đâu', 3)
        assert snap['messages'][-1]['result']['status'] == 'ASK_CLARIFICATION'
        assert len(retriever.calls) == provider.calls == 1
    asyncio.run(run())


def test_news_request_is_bounded_without_increasing_token_budget():
    evidence = {f'e{i}': {'passage': 'Đoạn nguồn. '*700} for i in range(5)}
    request = build_grounded_request('Tin FPT?', evidence, Limits.load(), {'source_type': 'NEWS'})
    content = json.loads(request['contents'][0]['parts'][0]['text'])
    assert len(content['evidence']) <= 3
    assert all(len(item['passage']) <= 3500 for item in content['evidence'])
    schema = request['generationConfig']['responseJsonSchema']['properties']['claims']
    assert schema['maxItems'] == 2
    assert request['generationConfig']['maxOutputTokens'] == 2048
    assert len(evidence['e0']['passage']) > 3500


def test_source_reference_does_not_reuse_an_answer_with_different_measure_basis():
    async def run():
        service = LiveResearchService(Retriever(), provider=Provider())
        previous = await service.answer('tiền và tương đương tiền FPT quý 2/2026', 'session')
        changed = {**previous['scope'], 'measure_basis': 'YTD'}
        result = await service.answer('nguồn đâu', 'session', changed, previous_result=previous)
        assert result['status'] == 'ASK_CLARIFICATION'
    asyncio.run(run())


def test_unknown_reporting_scope_is_not_parent_only_just_because_quarter_is_standalone(monkeypatch):
    from src.documents import repository
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever
    from tests.test_live_research import pack, INDEX
    item = pack()['items'][0]
    item['passage'] = item['passage'].replace(' | Phạm vi:', ' (riêng quý) | Phạm vi:')
    import hashlib
    row = dict(chunk_id=item['chunk_id'], document_id=item['source_id'], text=item['passage'],
               content_hash=hashlib.sha256(item['passage'].encode()).hexdigest(),
               source_sha256=item['source_sha256'], locator_json=item['locator'], title='FPT', score=0.9)
    class Embedder:
        def embed_query(self, text): return [1.0]+[0.0]*1023
    async def corpus(*args):
        return dict(index_version_id=INDEX, corpus_status='FROZEN', index_status='ACTIVE',
                    embedding_model='BAAI/bge-m3@5617a9f61b02')
    async def search(*args, **kwargs): return [row]
    monkeypatch.setattr(repository, 'get_corpus_index', corpus)
    monkeypatch.setattr(repository, 'vector_search_filtered', search)
    scope = analyze_live('tiền và tương đương tiền FPT báo cáo riêng quý 2/2026')['scope']
    result = asyncio.run(DenseEvidenceRetriever(object(), Embedder()).retrieve('tiền', scope))
    assert not result['items']
