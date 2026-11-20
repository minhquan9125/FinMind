import json

from src.retrieval_orchestration.chat_export import DISCLAIMER, build_export, render_txt


def doc():
    cite = {'citation_number': 1, 'title': 'Tin FPT', 'locator': {'url': 'https://fireant.vn/bai-viet/x/1'},
            'evidence_id': '00000000-0000-0000-0000-000000000001', 'content_sha256': 'a' * 64}
    return {'session_id': 's1', 'messages': [
        {'role': 'user', 'content': 'phân tích fpt', 'timestamp': '2026-11-20T03:21:00+00:00'},
        {'role': 'assistant', 'content': 'Giá: 45.450 VND. [1]', 'timestamp': '2026-11-20T03:21:10+00:00',
         'result': {'scope': {'companies': ['FPT']}, 'evidence_pack': {'items': []},
                    'answering': {'status': 'DRAFT_READY', 'citations': [cite]}}},
        {'role': 'user', 'content': '/new', 'timestamp': '2026-11-20T03:22:00+00:00'},
        {'role': 'assistant', 'content': 'Đã bắt đầu phiên mới.', 'result': {'scope': {}}},
        {'role': 'user', 'content': 'Giá VCB?', 'timestamp': '2026-11-20T03:23:00+00:00'},
        {'role': 'assistant', 'content': 'VCB: 52,1 nghìn đồng.', 'result': {'scope': {'companies': ['VCB']}}},
    ]}


def test_export_lists_every_turn_with_its_sources_and_companies():
    data = build_export(doc())
    assert [t['question'] for t in data['turns']] == ['phân tích fpt', 'Giá VCB?']
    assert data['turns'][0]['sources'] == [{'number': 1, 'title': 'Tin FPT', 'url': 'https://fireant.vn/bai-viet/x/1'}]
    assert data['turns'][0]['asked_at'] == '20/11/2026 10:21'
    assert data['companies'] == ['FPT', 'VCB'] and data['turn_count'] == 2
    assert data['summary']['text'] and data['disclaimer'] == DISCLAIMER


def test_export_never_leaks_internal_ids_or_hashes():
    text = json.dumps(build_export(doc()), ensure_ascii=False)
    assert 'evidence_id' not in text and 'a' * 64 not in text and 'evidence_pack' not in text


def test_txt_has_summary_details_and_disclaimer_in_order():
    text = render_txt(build_export(doc()))
    assert text.index('I. TÓM TẮT') < text.index('II. CHI TIẾT HỎI ĐÁP') < text.index(DISCLAIMER)
    assert '1. [20/11/2026 10:21] Hỏi: phân tích fpt' in text
    assert '[1] Tin FPT — https://fireant.vn/bai-viet/x/1' in text


# ---- download endpoint ----
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import research_chat as api
from src.retrieval_orchestration.chat_types import ChatError


class Store:
    async def export_doc(self, owner, session_id):
        if owner != 'me':
            raise ChatError(404, 'Không tìm thấy phiên.')
        return doc()


def client(owner='me'):
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_owner] = lambda: owner
    app.dependency_overrides[api.get_store] = lambda: Store()
    return TestClient(app)


def test_download_txt_and_json():
    txt = client().get('/api/research/chat/sessions/s1/export')
    assert txt.status_code == 200 and txt.headers['content-type'].startswith('text/plain')
    assert 'attachment; filename="finmind-chat-' in txt.headers['content-disposition'] and '.txt"' in txt.headers['content-disposition']
    assert 'I. TÓM TẮT' in txt.content.decode('utf-8')
    js = client().get('/api/research/chat/sessions/s1/export?format=json')
    assert js.status_code == 200 and js.json()['turn_count'] == 2


def test_download_is_owner_only_and_format_is_checked():
    assert client('other').get('/api/research/chat/sessions/s1/export').status_code == 404
    assert client().get('/api/research/chat/sessions/s1/export?format=pdf').status_code == 422


def test_summary_heading_shows_latest_period_in_words():
    from src.retrieval_orchestration.conversation_summary import period_text
    assert period_text(['LATEST_AVAILABLE_PERIOD']) == 'kỳ gần nhất'
    assert period_text(['2025', '2026-Q3']) == '2025, 2026-Q3'
