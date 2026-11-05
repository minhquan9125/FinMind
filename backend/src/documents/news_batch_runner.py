"""Checkpointed WBS16 preparation using the existing bounded News extractor.

No DB writes or review decisions. A full run stages candidates, not approved
graph relations. DB reconciliation consumes separately exported inventories.
"""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path

from .news_event_extractor import extract_batch, manifest_news_ids, rule_candidates
from . import news_event_extractor

VERSION = 'wbs16-staging-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    """Atomic replacement; a failed write never replaces the prior checkpoint."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def run_lock(output):
    path = output / '.runner.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('RUN_LOCKED: another runner or an interrupted process holds the lock') from None
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def check_receipt(receipt, *, corpus, manifest_sha256, extractor_version):
    """Explicit local handoff format; not a replacement for WBS09.5 testing."""
    if not isinstance(receipt, dict) or receipt.get('schema_version') != 'wbs09.5-news-handoff-v1':
        raise ValueError('WBS09_5_RECEIPT_REQUIRED')
    required = ('source_verified', 'extractor_contract', 'review_gate',
                'idempotent_rerun', 'postgres_neo4j_keys')
    checks = receipt.get('checks')
    if (receipt.get('status') != 'PASS' or receipt.get('execution_mode') != 'LIVE'
            or receipt.get('corpus_version_id') != corpus
            or receipt.get('manifest_sha256') != manifest_sha256
            or receipt.get('extractor_version') != extractor_version
            or not isinstance(checks, dict) or any(checks.get(k) is not True for k in required)
            or not receipt.get('reviewer') or not receipt.get('reviewed_at')
            or not receipt.get('evidence_paths')):
        raise ValueError('WBS09_5_RECEIPT_NOT_READY_OR_SCOPE_MISMATCH')


def reconcile(manifest, postgres, neo4j):
    """Compare full exported inventories for the same News graph scope.

    Input records: relation_id, document_ids, review_status. PostgreSQL includes
    drafts; only APPROVED keys may exist in Neo4j. Missing exports stay NOT_READY.
    """
    if postgres is None or neo4j is None:
        return {'status': 'NOT_READY', 'reason': 'BOTH_DB_EXPORTS_REQUIRED'}
    members = set(manifest_news_ids(manifest).values())
    corpus = manifest.get('corpus_version_id')
    graph = postgres.get('graph_version_id')
    if (not graph or graph != neo4j.get('graph_version_id')
            or any(x.get('corpus_version_id') != corpus for x in (postgres, neo4j))
            or any(x.get('manifest_sha256') != manifest.get('manifest_sha256') for x in (postgres, neo4j))):
        raise ValueError('DB_EXPORT_SCOPE_MISMATCH')
    def inventory(payload):
        rows = payload.get('relations')
        if not isinstance(rows, list):
            raise ValueError('INVALID_DB_INVENTORY')
        result = {}
        for row in rows:
            key, docs = row.get('relation_id'), row.get('document_ids')
            if (not isinstance(key, str) or not key or key in result
                    or not isinstance(docs, list) or not docs
                    or not set(docs) <= members
                    or row.get('review_status') not in {'APPROVED', 'PENDING', 'REJECTED', 'QUARANTINED'}):
                raise ValueError('INVALID_DB_INVENTORY_RECORD')
            result[key] = row
        return result
    pg, neo = inventory(postgres), inventory(neo4j)
    approved = {k for k, row in pg.items() if row['review_status'] == 'APPROVED'}
    missing, extra = sorted(approved - neo.keys()), sorted(neo.keys() - approved)
    mismatched = sorted(k for k in approved & neo.keys()
        if set(pg[k]['document_ids']) != set(neo[k]['document_ids'])
        or neo[k]['review_status'] != 'APPROVED')
    pending = sorted(k for k in neo if neo[k]['review_status'] != 'APPROVED')
    per_document = []
    for document_id in sorted(members):
        related = {k: row for k, row in pg.items() if document_id in row['document_ids']}
        per_document.append({'document_id': document_id,
            'postgres_status_counts': {s: sum(row['review_status'] == s for row in related.values())
                for s in ('APPROVED', 'PENDING', 'REJECTED', 'QUARANTINED')},
            'postgres_relation_ids': sorted(related),
            'neo4j_relation_ids': sorted(k for k, row in neo.items() if document_id in row['document_ids'])})
    return {'status': 'PASS' if not (missing or extra or mismatched or pending) else 'FAIL',
            'comparison_mode': 'EXPORTED_INVENTORIES', 'graph_version_id': graph,
            'postgres_relations': len(pg), 'postgres_approved': len(approved),
            'neo4j_relations': len(neo), 'missing_in_neo4j': missing,
            'unexpected_in_neo4j': extra, 'mismatched': mismatched,
            'unapproved_in_neo4j': pending, 'documents': per_document}


def run(manifest, articles, output, *, mode='fixture', receipt=None, candidates=None,
        resume=False, retry_errors=False, limit=None, postgres=None, neo4j=None,
        propose=None, extractor_version='news-event-extractor-v1'):
    if mode not in {'fixture', 'full'}:
        raise ValueError('INVALID_MODE')
    if limit is not None and (not isinstance(limit, int) or limit < 1):
        raise ValueError('INVALID_LIMIT')
    if not manifest.get('corpus_version_id') or not manifest.get('manifest_sha256'):
        raise ValueError('PINNED_MANIFEST_REQUIRED')
    members = manifest_news_ids(manifest)  # validates the payload hash
    if not members:
        raise ValueError('EMPTY_NEWS_MANIFEST')
    if mode == 'full':
        check_receipt(receipt, corpus=manifest['corpus_version_id'],
                      manifest_sha256=manifest['manifest_sha256'], extractor_version=extractor_version)
    if not isinstance(articles, list) or any(not isinstance(a, dict) or not a.get('article_id') for a in articles):
        raise ValueError('ARTICLES_ARRAY_REQUIRED')
    by_id = {str(a['article_id']): a for a in articles}
    if len(by_id) != len(articles) or not set(by_id) <= members.keys():
        raise ValueError('DUPLICATE_OR_OUTSIDE_MANIFEST_ARTICLE')
    supplied = candidates if candidates is not None else {}
    if (not isinstance(supplied, dict) or not set(supplied) <= members.keys()
            or any(not isinstance(v, list) for v in supplied.values())):
        raise ValueError('INVALID_CANDIDATES')
    # All input pins are immutable across a resumed run, including absent rows.
    pins = {'runner_version': VERSION, 'extractor_version': extractor_version,
            'extractor_code_sha256': hashlib.sha256(Path(news_event_extractor.__file__).read_bytes()).hexdigest(),
            'manifest_sha256': manifest['manifest_sha256'], 'corpus_version_id': manifest['corpus_version_id'],
            'articles_sha256': digest(articles), 'candidates_sha256': digest(supplied),
            'mode': mode, 'receipt_sha256': digest(receipt)}
    comparison = reconcile(manifest, postgres, neo4j)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / 'checkpoint.json'
    with run_lock(output):
        if state_path.exists():
            if not resume:
                raise ValueError('OUTPUT_EXISTS_USE_RESUME')
            saved = read_json(state_path)
            state = saved['state']
            if saved.get('sha256') != digest(state) or state.get('pins') != pins:
                raise ValueError('CHECKPOINT_CHANGED_OR_INPUT_MISMATCH')
        else:
            if resume:
                raise ValueError('NO_CHECKPOINT_TO_RESUME')
            state = {'pins': pins}
            write_json(state_path, {'sha256': digest(state), 'state': state})
        record_dir = output / 'records'
        record_dir.mkdir(exist_ok=True)
        paths = {aid: record_dir / (digest(aid) + '.json') for aid in members}
        if set(record_dir.iterdir()) - set(paths.values()):
            raise ValueError('UNEXPECTED_CHECKPOINT_FILE')
        records = {}
        for aid, path in paths.items():
            if path.exists():
                saved = read_json(path)
                row = saved['record']
                if (saved.get('sha256') != digest(row) or saved.get('pins_sha256') != digest(pins)
                        or row.get('article_id') != aid or row.get('document_id') != members[aid]
                        or row.get('status') not in {'ERROR', 'MISSING_SOURCE', 'PENDING_REVIEW', 'QUARANTINED', 'NO_CANDIDATE'}):
                    raise ValueError('ARTICLE_CHECKPOINT_CHANGED')
                records[aid] = row
        documents = {str(d['document_id']): d for d in manifest.get('manifest', manifest)['documents']}
        processed = 0
        for aid, document_id in sorted(members.items()):
            old = records.get(aid)
            if old and not (retry_errors and old['status'] == 'ERROR'):
                continue
            if limit is not None and processed >= limit:
                break
            record = {'article_id': aid, 'document_id': document_id}
            if aid not in by_id:
                record.update(status='MISSING_SOURCE', reason='ARTICLE_ROW_NOT_SUPPLIED')
            else:
                try:
                    article = deepcopy(by_id[aid])
                    if not isinstance(article.get('content'), str) or not article['content'].strip():
                        raise ValueError('EMPTY_ARTICLE_BODY')
                    def proposals(row):
                        if propose is not None:
                            return propose(row)
                        return supplied[aid] if aid in supplied else rule_candidates(row)
                    # Global membership/hash was checked once; avoid rehashing
                    # the entire corpus for every article in a full run.
                    local_manifest = {'corpus_version_id': manifest['corpus_version_id'],
                                      'documents': [documents[document_id]]}
                    batch = extract_batch(local_manifest, [article], proposals)
                    item = batch['article_results'][0]
                    record.update(status={'EVENT': 'PENDING_REVIEW', 'REVIEW': 'QUARANTINED',
                                          'NO_EVENT': 'NO_CANDIDATE'}[item['status']],
                                  extraction=item, events=batch['events'])
                except Exception as exc:
                    # Do not persist raw exceptions, connection strings or article text as errors.
                    record.update(status='ERROR', reason='EXTRACTOR_' + type(exc).__name__)
            records[aid] = record
            write_json(paths[aid], {'pins_sha256': digest(pins), 'sha256': digest(record), 'record': record})
            processed += 1
        if not set(records) <= members.keys():
            raise ValueError('CHECKPOINT_OUTSIDE_MANIFEST')
        counts = {s: sum(r['status'] == s for r in records.values()) for s in
                  ('PENDING_REVIEW', 'QUARANTINED', 'NO_CANDIDATE', 'ERROR', 'MISSING_SOURCE')}
        counts['UNPROCESSED'] = len(members) - len(records)
        report = {'schema_version': VERSION, 'mode': mode, 'pins': pins,
                  'total_manifest_news': len(members), 'counts': counts,
                  'all_articles_accounted_for': sum(counts.values()) == len(members),
                  'staging_complete': not any(counts[s] for s in ('ERROR', 'MISSING_SOURCE', 'UNPROCESSED')),
                  'database_writes': 0, 'review_decisions_written': 0,
                  'acceptance_status': 'NOT_EVALUATED', 'database_reconciliation': comparison,
                  'unresolved': [{'article_id': aid, 'status': records[aid]['status'],
                                  'reason': records[aid].get('reason')}
                                 if aid in records else {'article_id': aid, 'status': 'UNPROCESSED'}
                                 for aid in sorted(members)
                                 if aid not in records or records[aid]['status'] != 'NO_CANDIDATE']}
        write_json(output / 'report.json', report)
        return report
