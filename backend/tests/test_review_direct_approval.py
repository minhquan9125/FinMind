"""Exercise the real PostgresReviewStore path, including quarantine row counts."""
import asyncio,json,uuid
from copy import deepcopy
from datetime import datetime,timezone
import pytest
from src.auth.authorization import Principal
from src.graph_review.models import ReviewResult,digest
from src.graph_review.repository import PostgresReviewStore,ReviewConflict
from tests.test_news_graph_contract import payload
from src.graph_review.adapters import from_envelope

class Connection:
    def __init__(self):self.row=None;self.quarantined=False;self.audit=[];self.quarantine_inserts=0
    def transaction(self,**kwargs):return self
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def fetchval(self,sql,*args):
        assert 'INSERT INTO public.graph_review_results' in sql
        self.row=dict(review_id=args[0],graph_version_id=args[1],candidate=json.loads(args[4]),
                      evaluation=json.loads(args[7]),revision=1)
        return args[0]
    async def fetchrow(self,sql,*args):return deepcopy(self.row)
    async def execute(self,sql,*args):
        if 'INSERT INTO public.graph_review_audit' in sql:
            self.audit.append(args[2]);return 'INSERT 0 1'
        if 'UPDATE public.graph_review_results' in sql:
            self.row.update(evaluation=json.loads(args[3]),revision=self.row['revision']+1)
            return 'UPDATE 1'
        if 'INSERT INTO public.quarantine_records' in sql:
            self.quarantined=True;self.quarantine_inserts+=1;return 'INSERT 0 1'
        if 'UPDATE public.quarantine_records' in sql:
            return 'UPDATE 1' if self.quarantined else 'UPDATE 0'
        raise AssertionError('Unexpected SQL')

def initial(status='APPROVED'):
    raw=from_envelope(payload())[0]
    result=ReviewResult(candidate_id=raw['candidate_id'],candidate_sha256=digest(raw),status=status,
        reasons=[] if status=='APPROVED' else ['WARN_EVIDENCE_INSUFFICIENT'],
        source_verified=True,verification_mode='LIVE',checked_at=datetime.now(timezone.utc))
    return raw,result

def test_directly_approved_intake_can_save_real_reviewer_without_quarantine():
    async def run():
        conn=Connection();store=PostgresReviewStore(conn)
        raw,fresh=initial();actor=Principal(uuid.uuid4(),frozenset({'ADMINISTRATOR'}))
        row=await store.save(raw,fresh,uuid.uuid4(),actor)
        assert conn.quarantine_inserts==0
        saved=await store.review(row['review_id'],'APPROVED',fresh,actor,'Đã kiểm hai đoạn nguồn',1)
        assert saved['result']['status']=='APPROVED' and saved['revision']==2
        assert conn.audit==['APPROVED','APPROVED']
        assert conn.quarantine_inserts==0
    asyncio.run(run())

def test_pending_to_approved_still_requires_existing_quarantine_history():
    async def run():
        conn=Connection();store=PostgresReviewStore(conn)
        raw,pending=initial('PENDING');actor=Principal(uuid.uuid4(),frozenset({'ADMINISTRATOR'}))
        row=await store.save(raw,pending,uuid.uuid4(),actor)
        assert conn.quarantined and conn.quarantine_inserts==1
        ready=pending.model_copy(update={'status':'APPROVED','reasons':[]})
        conn.quarantined=False  # Corrupted/missing prior quarantine must stay visible.
        with pytest.raises(ReviewConflict,match='Expected one existing quarantine'):
            await store.review(row['review_id'],'APPROVED',ready,actor,'reviewed',1)
    asyncio.run(run())

def test_existing_quarantine_is_updated_when_an_approved_record_is_reviewed_again():
    async def run():
        conn=Connection();store=PostgresReviewStore(conn)
        raw,fresh=initial();actor=Principal(uuid.uuid4(),frozenset({'ADMINISTRATOR'}))
        row=await store.save(raw,fresh,uuid.uuid4(),actor);conn.quarantined=True
        saved=await store.review(row['review_id'],'APPROVED',fresh,actor,'rechecked',1)
        assert saved['revision']==2 and conn.quarantined
    asyncio.run(run())
