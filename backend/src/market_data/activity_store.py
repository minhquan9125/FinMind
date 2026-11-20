"""Transactional current-per-day observations, never summed intraday snapshots."""
from datetime import date, datetime
import json
import asyncio
from pathlib import Path
import sys

VALUES = ('volume','total_value_vnd','foreign_buy_volume','foreign_sell_volume',
          'foreign_buy_value_vnd','foreign_sell_value_vnd')
META = ('volume_basis','value_basis','observation_status','quality_status')


async def upsert_activity(conn, record, *, company_id, source_id, payload_id):
    day, stamp = record['trade_date'], record['fetched_at']
    if type(day) is not date or not isinstance(stamp,datetime) or stamp.utcoffset() is None:
        raise ValueError('Activity requires a date and timezone-aware observation')
    key = (company_id,day,source_id)
    incoming = {field:record.get(field) for field in VALUES}
    meta = {field:record[field] for field in META}
    async with conn.transaction():
        provenance = await conn.fetchrow('''SELECT j.source_id FROM public.raw_payloads r
            JOIN public.ingestion_jobs j USING(job_id) WHERE r.payload_id=$1''',payload_id)
        if provenance is not None and provenance['source_id'] != source_id:
            raise ValueError('Activity source differs from its raw payload source')
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))',
                           f'activity:{company_id}:{day}:{source_id}')
        old = await conn.fetchrow('''SELECT * FROM public.daily_market_activity
            WHERE company_id=$1 AND trade_date=$2 AND source_id=$3 FOR UPDATE''',*key)
        if old:
            if stamp < old['fetched_at']:
                return 'needs_reconciliation'
            merged = {field:incoming[field] if incoming[field] is not None else old[field] for field in VALUES}
            if any(old[f] is not None and merged[f] is not None and merged[f] < old[f] for f in VALUES):
                return 'needs_reconciliation'
            if any(old[f] != 'unknown' and meta[f] != old[f] for f in ('volume_basis','value_basis')):
                return 'needs_reconciliation'
            changed = any(merged[f] != old[f] for f in VALUES) or any(meta[f] != old[f] for f in META)
            if changed and (stamp == old['fetched_at'] or
                            old['quality_status']=='validated' and meta['quality_status']!='validated' or
                            old['observation_status']=='after_close' and meta['observation_status']!='after_close'):
                return 'needs_reconciliation'
            if not changed and stamp == old['fetched_at']:
                return 'unchanged'
            origins = json.loads(old['field_payload_ids']) if isinstance(old['field_payload_ids'],str) else dict(old['field_payload_ids'])
            for field in VALUES:
                if old[field] is not None:origins.setdefault(field,str(old['payload_id']))
            revision = old['revision'] + int(changed)
            updated = record.get('source_updated_at') or old['source_updated_at']
        else:
            merged, origins, revision, updated = incoming, {}, 1, record.get('source_updated_at')
            changed = True
        for field in VALUES:
            if incoming[field] is not None:origins[field] = str(payload_id)
        columns = (*VALUES,*META,'source_updated_at','fetched_at','payload_id','field_payload_ids','revision')
        args = [*(merged[f] for f in VALUES),*(meta[f] for f in META),updated,stamp,payload_id,json.dumps(origins),revision]
        if old:
            assignments = ','.join(f'{field}=${i+4}'+('::jsonb' if field=='field_payload_ids' else '') for i,field in enumerate(columns))
            await conn.execute('UPDATE public.daily_market_activity SET '+assignments+
                               ',updated_at=now() WHERE company_id=$1 AND trade_date=$2 AND source_id=$3',*key,*args)
            return 'updated' if changed else 'unchanged'
        fields = ('company_id','trade_date','source_id',*columns)
        placeholders = ','.join(f'${i+1}'+('::jsonb' if f=='field_payload_ids' else '') for i,f in enumerate(fields))
        await conn.execute('INSERT INTO public.daily_market_activity ('+','.join(fields)+') VALUES ('+placeholders+')',*key,*args)
        return 'inserted'


def ingest_module():
    """The shared importer; importable even when the API runs as ``src.*`` from backend/."""
    root = str(Path(__file__).resolve().parents[3])
    if root not in sys.path:
        sys.path.append(root)
    from backend.scripts import ingest_market_news_to_supabase as ingest
    return ingest


async def flush_pending_activity(pool, repository, *, timeout=15):
    ingest = ingest_module()
    result={'saved':0,'rejected':0,'failed':0,'deferred':0}
    deadline=asyncio.get_running_loop().time()+timeout
    def last_import(item):
        ack=item['path'].with_suffix('.ack.json')
        return ack.stat().st_mtime if ack.exists() else 0.0
    # Least recently imported first: a bounded flush cannot starve the rest of the basket by
    # re-importing the same frequently changing snapshots every minute.
    for item in sorted(repository.pending_activity(),key=last_import):
        relative=item['path'].relative_to(repository.root.resolve())
        plan={'symbol':item['symbol'],'source':'vnstock_kbs','is_index':False,
              'live':item['envelope'],'live_path':ingest.PROJECT_ROOT/relative}
        try:
            async with asyncio.timeout(max(0,deadline-asyncio.get_running_loop().time())):
                async with pool.acquire() as conn:
                    outcome=await ingest.apply_live(conn,plan)
            status=outcome['activity_status']
            repository.ack_activity(item,status)
            result['saved' if status in ('inserted','updated','unchanged') else 'rejected']+=1
        except TimeoutError:
            # Out of flush time after progress: the rest waits for the next flush, not a failure.
            result['deferred' if result['saved'] or result['rejected'] else 'failed']+=1
            break  # Keep the unacknowledged snapshot for the next bounded flush.
        except Exception:
            result['failed']+=1
            continue  # Keep the failed snapshot pending while allowing later archives to import.
    return result
