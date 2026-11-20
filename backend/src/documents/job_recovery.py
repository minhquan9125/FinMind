"""Single-machine worker locks: OS releases them even after a hard process exit."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from datetime import datetime, timezone, timedelta
import os


@contextmanager
def worker_lock(queue, ident):
    path=queue.root/'worker-locks'/ (ident+'.lock');path.parent.mkdir(parents=True,exist_ok=True)
    stream=path.open('a+b');locked=False
    try:
        stream.seek(0,os.SEEK_END)
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            locked=True
        except (OSError,BlockingIOError):pass
        yield locked
    finally:
        if locked:
            stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        stream.close()


def job_worker(fn):
    @wraps(fn)
    def run(queue,ident,*args,**kwargs):
        with worker_lock(queue,ident) as acquired:
            if not acquired or queue.get_job(ident)['status'] not in ('QUEUED','RUNNING'):return
            return fn(queue,ident,*args,**kwargs)
    return run


def recover_stopped_jobs(queue, *, at=None, grace_seconds=30):
    """Release orphaned queue entries; keep manifests for explicit safe resume.

    No age timeout kills an active worker: even a very old job keeps its OS lock.
    Recovery never publishes or changes article approvals on its own.
    """
    cutoff=(at or datetime.now(timezone.utc))-timedelta(seconds=grace_seconds)
    recovered=[]
    with queue.connect() as conn:
        candidates=[dict(row) for row in conn.execute("SELECT id,status,updated_at FROM jobs WHERE status IN ('QUEUED','RUNNING')")]
    for job in candidates:
        if datetime.fromisoformat(job['updated_at'])>cutoff:continue
        with worker_lock(queue,job['id']) as acquired:
            if not acquired:continue
            with queue.connect() as conn:
                row=conn.execute('SELECT status,updated_at,details FROM jobs WHERE id=?',(job['id'],)).fetchone()
                if row['status'] not in ('QUEUED','RUNNING') or row['updated_at']!=job['updated_at']:continue
                from .admin_ingestion import canonical,now
                import json
                details=json.loads(row['details']);details.update(error='WORKER_STOPPED',recovered_at=now())
                conn.execute("UPDATE jobs SET status='FAILED',updated_at=?,details=? WHERE id=?",(now(),canonical(details),job['id']))
                conn.execute('INSERT INTO audit(actor,action,resource,at) VALUES(?,?,?,?)',
                             ('system:recovery','RECOVER_STOPPED_JOB',job['id'],now()))
                recovered.append(job['id'])
    return recovered
