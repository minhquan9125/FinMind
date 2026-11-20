"""Real standalone ASGI + JSON service; no DB, user histories or real secrets."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import jwt
from pydantic import SecretStr
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.src.api.routers import research_chat as api
from backend.src.retrieval_orchestration.web_sessions import SessionStore, ChatError


class ResearchChatAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SessionStore(Path(self.temp.name))
        self.owner = str(uuid4())
        self.settings = SimpleNamespace(jwt_secret_key=SecretStr('isolated-test-key-for-chat-not-production-123456789'))
        self.patch_settings = patch.object(api, 'get_settings', return_value=self.settings)
        self.patch_settings.start()
        self.addCleanup(self.patch_settings.stop)
        self.app = FastAPI()
        self.app.include_router(api.router)
        self.app.dependency_overrides[api.get_store] = lambda: self.store
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers = self.auth(self.owner)

    def auth(self, owner, *, kind='access', expired=False):
        now = datetime.now(timezone.utc)
        token = jwt.encode({'sub': owner, 'type': kind, 'iat': now-timedelta(minutes=2),
                            'exp': now+timedelta(minutes=-1 if expired else 5)},
                           self.settings.jwt_secret_key.get_secret_value(), algorithm='HS256')
        return {'Authorization': 'Bearer '+token}

    def create(self):
        r=self.client.post('/api/research/chat/sessions', headers=self.headers)
        self.assertEqual(r.status_code,201,r.text)
        return r.json()

    def test_all_routes_require_valid_access_token(self):
        sid=str(uuid4())
        cases=[('GET','/sessions'),('POST','/sessions'),('GET',f'/sessions/{sid}'),
               ('POST',f'/sessions/{sid}/resume'),('POST',f'/sessions/{sid}/messages')]
        for method,path in cases:
            for headers in ({}, {'Authorization':'Bearer broken'},self.auth(self.owner,expired=True),self.auth(self.owner,kind='password_reset'),self.auth('not-uuid')):
                with self.subTest(method=method,path=path,headers_kind=bool(headers)):
                    r=self.client.request(method,'/api/research/chat'+path,headers=headers,
                                          json={'text':'BID','revision':0} if path.endswith('messages') else None)
                    self.assertEqual(r.status_code,401,r.text)
                    self.assertEqual(r.headers.get('www-authenticate'),'Bearer')

    def test_real_multiturn_restart_and_resume(self):
        snap=self.create()
        sid=snap['session_id']
        path=f'/api/research/chat/sessions/{sid}'
        for text in ('lợi nhuận năm nay là bao nhiêu','BID, sau thuế','không, là VCB'):
            r=self.client.post(path+'/messages',headers=self.headers,json={'text':text,'revision':snap['revision']})
            self.assertEqual(r.status_code,200,r.text)
            snap=r.json()
        self.assertIn('VCB',snap['context'])
        self.assertIn('sau thuế',snap['context'].lower())
        self.assertEqual(len(snap['messages']),6)
        self.assertEqual(snap['messages'][-1]['result']['execution_mode'],'FIXTURE')
        self.app.dependency_overrides[api.get_store]=lambda:SessionStore(Path(self.temp.name))
        self.assertEqual(self.client.get(path,headers=self.headers).json(),snap)
        file=Path(self.temp.name)/self.owner/(sid+'.json')
        before=file.read_bytes()
        child=self.client.post(path+'/resume',headers=self.headers)
        self.assertEqual(child.status_code,201,child.text)
        self.assertNotEqual(child.json()['session_id'],sid)
        self.assertEqual(child.json()['messages'],snap['messages'])
        self.assertEqual(before,file.read_bytes())
        listed=self.client.get('/api/research/chat/sessions',headers=self.headers).json()['items']
        self.assertEqual(len(listed),2)

    def test_other_user_cannot_read_send_resume_or_list(self):
        snap=self.create()
        other=self.auth(str(uuid4()))
        path='/api/research/chat/sessions/'+snap['session_id']
        self.assertEqual(self.client.get(path,headers=other).status_code,404)
        self.assertEqual(self.client.post(path+'/resume',headers=other).status_code,404)
        self.assertEqual(self.client.post(path+'/messages',headers=other,json={'text':'BID','revision':0}).status_code,404)
        self.assertEqual(self.client.get('/api/research/chat/sessions',headers=other).json(),{'items':[]})

    def test_strict_payload_and_conflict(self):
        snap=self.create()
        path='/api/research/chat/sessions/'+snap['session_id']+'/messages'
        for body in ({'text':' ','revision':0},{'text':'x'*4001,'revision':0},
                     {'text':'BID','revision':True},{'text':'BID','revision':'0'},
                     {'text':'BID','revision':-1},{'text':'BID','revision':0,'owner':self.owner}):
            with self.subTest(body_kind=str(body)[:30]):
                self.assertEqual(self.client.post(path,headers=self.headers,json=body).status_code,422)
        self.assertEqual(self.client.post(path,headers=self.headers,json={'text':'BID','revision':0}).status_code,200)
        self.assertEqual(self.client.post(path,headers=self.headers,json={'text':'BID','revision':0}).status_code,409)

    def test_errors_are_safe_and_owner_not_taken_from_query(self):
        self.app.dependency_overrides[api.get_store]=lambda:SimpleNamespace(create=self.fail)
        r=self.client.post('/api/research/chat/sessions?owner='+str(uuid4()),headers=self.headers)
        self.assertEqual(r.status_code,503)
        self.assertNotIn('private',r.text)

    async def fail(self,*args):
        raise OSError('private disk path')


if __name__=='__main__':
    unittest.main()
