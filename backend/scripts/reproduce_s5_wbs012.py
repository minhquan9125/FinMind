"""Exercise real chat endpoints/JWT validation with an isolated fixture store.

Never uses the user's signing secret, DB, auth token or chat history.
Output is evidence of fixture behavior, not Web Chat live-data acceptance.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from src.api.routers import research_chat as api
from src.retrieval_orchestration.web_sessions import SessionStore


def run():
    owner, secret = str(uuid4()), secrets.token_hex(32)
    now = datetime.now(timezone.utc)

    def headers(expired=False):
        token = jwt.encode(dict(sub=owner, type='access', iat=now-timedelta(minutes=2),
                                exp=now+timedelta(minutes=-1 if expired else 5)), secret, algorithm='HS256')
        return dict(Authorization='Bearer ' + token)

    app = FastAPI()
    app.include_router(api.router)
    with tempfile.TemporaryDirectory(prefix='s5-wbs012-') as directory:
        store = SessionStore(Path(directory))
        app.dependency_overrides[api.get_store] = lambda: store
        settings = SimpleNamespace(jwt_secret_key=SecretStr(secret))
        with patch.object(api, 'get_settings', return_value=settings), TestClient(app) as client:
            good = headers()
            created = client.post('/api/research/chat/sessions', headers=good)
            assert created.status_code == 201
            snap = created.json()
            path = '/api/research/chat/sessions/' + snap['session_id']
            turns = []
            for question in ['Lợi nhuận sau thuế của BID năm 2025 là bao nhiêu?',
                             'Còn VCB thì sao?', 'Tổng hợp những gì nãy giờ']:
                response = client.post(path + '/messages', headers=good,
                                       json=dict(text=question, revision=snap['revision']))
                assert response.status_code == 200
                snap = response.json()
                result = snap['messages'][-1].get('result', {})
                turns.append(dict(question=question, http_status=response.status_code,
                                  revision=snap['revision'], context=snap['context'],
                                  answer=snap['messages'][-1]['content'], result=result))
            fresh = client.post('/api/research/chat/sessions', headers=good).json()
            no_leak = not fresh['messages'] and 'VCB' not in fresh['context']
            before = client.get(path, headers=good).json()
            denied = client.post(path + '/messages', headers=headers(True),
                                 json=dict(text='Còn VCB thì sao?', revision=before['revision']))
            assert denied.status_code == 401
            after = client.get(path, headers=good).json()
            assert before == after
            scope = turns[1]['result'].get('scope', {})
            return dict(mode='ASGI_FIXTURE_REAL_ENDPOINTS_REAL_EXPIRED_JWT_NOT_LIVE_DB',
                conversation=dict(case_id='S5-WBS01.2-CONTEXT', turns=turns,
                    expected_followup=dict(companies=['VCB'], periods=['2025-12-31'], metric_code='PROFIT_AFTER_TAX'),
                    followup_scope_matches=scope.get('companies') == ['VCB']
                      and scope.get('periods') == ['2025-12-31'] and scope.get('metric_code') == 'PROFIT_AFTER_TAX',
                    new_session_empty_without_prior_scope=no_leak,
                    summary_requires_human_review=True),
                token=dict(case_id='S5-WBS01.2-TOKEN-API', expired_access_status=denied.status_code,
                           response=denied.json(), stored_snapshot_unchanged=True,
                           refresh_behavior_tested=False,
                           conclusion='API correctly rejects expired access; client recovery measured separately'),
                product_source_changed=False, credentials_or_personal_histories_exported=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('Do not overwrite a prior reproduction attempt')
    result = run()
    watched = ['backend/src/api/routers/research_chat.py',
               'backend/src/retrieval_orchestration/chat_logic.py',
               'backend/src/retrieval_orchestration/retrieval_flow/conversation.py',
               'frontend/src/pages/research/chatApi.js', 'frontend/src/shared/api/authorization.js',
               'frontend/src/shared/context/AuthContext.jsx']
    result['source_hashes'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in watched}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(args.out), mode=result['mode'],
                         followup_matches=result['conversation']['followup_scope_matches'],
                         expired_access_status=result['token']['expired_access_status'])))
