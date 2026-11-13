from datetime import datetime,timedelta,timezone
from pathlib import Path
import subprocess
import sys
import time

from src.documents.admin_ingestion import Queue
from src.documents.job_recovery import worker_lock,recover_stopped_jobs,job_worker


def aged_job(q):
    ident,_=q.create_job('CRAWL','admin');q.update_job(ident,'RUNNING',phase='COLLECTING')
    with q.connect() as c:c.execute('UPDATE jobs SET updated_at=? WHERE id=?',
        ((datetime.now(timezone.utc)-timedelta(hours=3)).isoformat(),ident))
    return ident


def test_live_worker_is_never_recovered_by_age_alone(tmp_path):
    q=Queue(tmp_path);ident=aged_job(q)
    with worker_lock(q,ident) as locked:
        assert locked
        assert recover_stopped_jobs(q)==[]
    assert recover_stopped_jobs(q)==[ident]
    assert q.get_job(ident)['status']=='FAILED'
    assert q.get_job(ident)['details']['error']=='WORKER_STOPPED'
    q.resume_job(ident,'admin')
    assert q.get_job(ident)['status']=='QUEUED'


def test_os_unlocks_after_worker_process_terminates(tmp_path):
    q=Queue(tmp_path);ident=aged_job(q)
    script="""import sys,time
from src.documents.admin_ingestion import Queue
from src.documents.job_recovery import worker_lock
with worker_lock(Queue(sys.argv[1]),sys.argv[2]) as locked:
 print('LOCKED' if locked else 'FAILED',flush=True)
 time.sleep(60)
"""
    process=subprocess.Popen([sys.executable,'-c',script,str(tmp_path),ident],cwd=Path(__file__).resolve().parents[1],stdout=subprocess.PIPE,text=True)
    try:
        assert process.stdout.readline().strip()=='LOCKED'
        assert recover_stopped_jobs(q)==[]
    finally:process.terminate();process.wait(timeout=10)
    # Windows releases a dead process's file locks asynchronously (LockFileEx docs), so poll briefly.
    deadline=time.monotonic()+5
    while (recovered:=recover_stopped_jobs(q))==[] and time.monotonic()<deadline:time.sleep(0.05)
    assert recovered==[ident]


def test_duplicate_worker_does_not_execute_a_finished_job(tmp_path):
    q=Queue(tmp_path);ident,_=q.create_job('CRAWL','admin');calls=[]
    @job_worker
    def work(queue,job):calls.append(job);queue.update_job(job,'COMPLETED')
    work(q,ident);work(q,ident)
    assert calls==[ident]


def test_partial_index_retry_uses_new_id_and_preserves_approvals(tmp_path):
    q=Queue(tmp_path);crawl,_=q.create_job('CRAWL','admin');q.update_job(crawl,'RUNNING')
    aid,_=q.save_article(crawl,{'title':'Test source','url':'https://fireant.vn/bai-viet/test/1','content':'Full source text. '*50})
    q.update_job(crawl,'COMPLETED');q.review(aid,'APPROVED','Reviewed text','admin')
    index,_=q.create_job('INDEX','admin',article_ids=[aid]);q.update_job(index,'FAILED',phase='WRITING_INDEX',error='WORKER_STOPPED')
    successor=q.retry_index(index,'admin')
    assert successor!=index and q.get_job(successor)['status']=='QUEUED'
    assert q.get_job(successor)['details']['recovered_from']==index
    assert q.get_job(index)['details']['error']=='WORKER_STOPPED'
    assert q.article(aid)['status']=='APPROVED'


def test_recovery_retains_manifest_and_active_corpus(tmp_path):
    q=Queue(tmp_path);ident=aged_job(q)
    q.update_job(ident,'RUNNING',manifest_sha256='a'*64)
    q.publish_corpus('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000002')
    future=datetime.now(timezone.utc)+timedelta(minutes=1)
    assert recover_stopped_jobs(q,at=future)==[ident]
    assert q.get_job(ident)['details']['manifest_sha256']=='a'*64
    assert q.serving_corpus(None)=='00000000-0000-0000-0000-000000000001'
