import asyncio
import copy
import hashlib
import json
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from src.retrieval_orchestration.person_graph_chat import PersonGraphChat, personnel_role
from src.retrieval_orchestration.live_research import LiveResearchService, analyze_live
from src.graph_review.models import VerifiedSource
from src.b1_answering.evidence.citations import prepare_evidence, CitationError

VERSION = str(uuid4())
TEXT = 'Trần Văn A\nThành viên Hội đồng Quản trị'
HASH = hashlib.sha256(TEXT.encode()).hexdigest()


def row(kind='HOLDS_ROLE', year='2025'):
    ref = dict(document_id=str(uuid4()), document_version='a'*64, chunk_id=str(uuid4()),
               corpus_id=str(uuid4()), index_version_id=str(uuid4()), content_hash=HASH,
               source_sha256='a'*64, locator={'page': 12}, quote=TEXT, quote_start=0, quote_end=len(TEXT))
    return dict(version=VERSION, name='Trần Văn A', person_id='person', company_id='company',
                subject_id='company' if kind in ('APPOINTS', 'DISMISSES') else 'person',
                claim=dict(key='claim-'+kind, graph_version_id=VERSION, position='Thành viên Hội đồng Quản trị',
                           relation_type=kind, source_report_year=year, evidence_json=json.dumps([ref]),
                           identity_scope='SOURCE_OCCURRENCE', time_scope='SOURCE_DOCUMENT_NOT_CURRENT_OFFICE',
                           source_review_status='APPROVED_IN_SOURCE_REPORT'))


class Reader:
    def __init__(self, rows): self.rows, self.symbols = rows, []
    def company(self, symbol): self.symbols.append(symbol); return copy.deepcopy(self.rows)


async def verified(records): pass


def result(question='hội đồng quản trị FPT'):
    decision = analyze_live(question)
    return dict(scope=decision['scope'], status=decision['decision'], execution_mode='LIVE')


def run(rows=None, question='hội đồng quản trị FPT', verify=verified):
    reader = Reader([row()] if rows is None else rows)
    adapter = PersonGraphChat(lambda: reader, None, verify=verify)
    return asyncio.run(adapter.answer(question, result(question)))


def test_board_answer_preserves_source_year_quotes_and_cautions_without_model():
    answer = run()
    assert answer['answering']['status'] == 'DRAFT_READY'
    text = answer['answering']['draft']
    assert 'Trần Văn A' in text and '2025' in text and 'chưa xác nhận chức vụ đương nhiệm' in text
    assert answer['answering']['manifest']['components'] == {'gemini': False, 'graph': True, 'source_replay': True}
    assert list(prepare_evidence(answer['evidence_pack']).values())[0]['passage'] == TEXT
    assert answer['answering']['citations'][0]['citation_number'] == 1


@pytest.mark.parametrize('kind, phrase', [
    ('APPOINTS', 'Được bổ nhiệm'), ('DISMISSES', 'Được miễn nhiệm'),
    ('FORMER_ROLE', 'Chức vụ trước đây'), ('RESIGNS', 'Từ nhiệm'),
    ('REQUESTS_RESIGNATION', 'Đề nghị từ nhiệm'),
])
def test_events_are_not_rewritten_into_current_holders(kind, phrase):
    assert phrase in run([row(kind)])['answering']['draft']


def test_explicit_year_is_not_filled_from_a_different_or_undated_source():
    assert run([row(year='2025')], 'hội đồng quản trị FPT năm 2024')['status'] == 'NO_DATA'
    assert run([row(year=None)], 'hội đồng quản trị FPT năm 2025')['status'] == 'NO_DATA'
    assert run([row(year=None)])['answering']['draft'].count('nguồn chưa ghi năm báo cáo') == 1


@pytest.mark.parametrize('change', ['name', 'direction', 'scope', 'version'])
def test_unbound_person_direction_scope_and_version_fail_closed(change):
    item = row()
    if change == 'name': item['name'] = 'Người không có trong nguồn'
    if change == 'direction': item['subject_id'] = 'company'
    if change == 'scope': item['claim']['identity_scope'] = 'GLOBAL_PERSON'
    if change == 'version': item['claim']['graph_version_id'] = 'other'
    assert run([item])['status'] == 'SYSTEM_UNAVAILABLE'


def test_source_replay_failure_does_not_return_a_name_or_fallback_to_vector():
    async def broken(records): raise ValueError('changed source')
    answer = run(verify=broken)
    assert answer['status'] == 'SYSTEM_UNAVAILABLE'
    assert answer['evidence_pack'] is None and 'answering' not in answer


def test_citation_tampering_is_rejected_and_saved_reference_works():
    answer = run()
    changed = copy.deepcopy(answer['evidence_pack']); changed['items'][0]['passage'] = 'invented'
    with pytest.raises(CitationError): prepare_evidence(changed)
    service = LiveResearchService(None)
    reference = asyncio.run(service.answer('xem nguồn', 'session', answer['scope'], previous_result=answer))
    assert reference['answering']['reason_code'] == 'SOURCE_REFERENCE'
    assert reference['answering']['citations'] == answer['answering']['citations']


def test_engine_routes_numeric_membership_choice_to_graph_without_vector_or_model():
    class Never:
        async def retrieve(self, *args): pytest.fail('person query must not search financial/news vectors')
    reader = Reader([row()])
    adapter = PersonGraphChat(lambda: reader, None, verify=verified)
    service = LiveResearchService(Never(), person_graph=adapter)
    scope = analyze_live('tất cả thành viên FPT')['scope']
    answer = asyncio.run(service.answer('1', 'session', scope))
    assert answer['answering']['manifest']['response_mode'] == 'GRAPH_SOURCE_CLAIMS'
    assert reader.symbols == ['FPT']
    assert personnel_role('doanh thu FPT') is None


def test_recent_personnel_query_does_not_turn_into_price_analysis_or_generic_news():
    class Never:
        async def answer(self, *args, **kwargs): pytest.fail('organizational intent must precede generic article routing')
    adapter = PersonGraphChat(lambda: Reader([row()]), None, verify=verified)
    service = LiveResearchService(None, person_graph=adapter, admin_news=Never())
    answer = asyncio.run(service.answer('thông tin hội đồng quản trị FPT gần đây', 'session'))
    assert answer['answering']['manifest']['response_mode'] == 'GRAPH_SOURCE_CLAIMS'


@pytest.mark.parametrize('tamper', [None, 'hash', 'offset', 'inactive'])
def test_default_source_replay_uses_readonly_transaction_and_checks_source(monkeypatch, tamper):
    item = row(); ref = json.loads(item['claim']['evidence_json'])[0]
    source = VerifiedSource(**{k: ref[k] for k in ('document_id', 'document_version', 'chunk_id', 'corpus_id', 'index_version_id', 'source_sha256', 'content_hash', 'locator')},
                            text=TEXT + ('changed' if tamper == 'hash' else ''), active=tamper != 'inactive')
    class SourceReader:
        cache = {}
        def __init__(self, conn): pass
        async def prefetch(self, *args): pass
        async def resolve(self, *args): return source
    class Connection:
        @asynccontextmanager
        async def transaction(self, **options):
            assert options == {'isolation': 'repeatable_read', 'readonly': True}
            yield
    class Pool:
        @asynccontextmanager
        async def acquire(self): yield Connection()
    if tamper == 'offset':
        ref['quote_end'] -= 1
        item['claim']['evidence_json'] = json.dumps([ref])
    monkeypatch.setattr('src.retrieval_orchestration.person_graph_chat.PostgresSourceReader', SourceReader)
    adapter = PersonGraphChat(lambda: Reader([item]), Pool())
    answer = asyncio.run(adapter.answer('hội đồng quản trị FPT', result()))
    assert answer['status'] == ('EVIDENCE_READY' if tamper is None else 'SYSTEM_UNAVAILABLE')
