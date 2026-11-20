"""WBS16 orchestration regressions; no DB, model, network or human approvals."""
import json

import pytest

from src.documents.news_batch_runner import digest, read_json, reconcile, run


def fixture():
    articles = [
        {'article_id': 'a1', 'content': 'FPT đã hoàn thiện hai AI Factory.', 'published_at': '2026-11-01'},
        {'article_id': 'a2', 'content': 'Bài viết không có mẫu hành động được hỗ trợ.'},
        {'article_id': 'a3', 'content': 'Một bài cần kiểm tra riêng.'},
    ]
    payload = {'documents': [{'document_id': 'd' + a['article_id'], 'doc_type': 'NEWS',
        'chunks': [{'locator': {'source_table': 'news_articles', 'source_id': a['article_id']}}]}
        for a in articles]}
    manifest = {'corpus_version_id': 'fixture-corpus', 'manifest_sha256': digest(payload), 'manifest': payload}
    return manifest, articles


def receipt(manifest):
    return {'schema_version': 'wbs09.5-news-handoff-v1', 'execution_mode': 'LIVE', 'status': 'PASS',
        'extractor_version': 'news-event-extractor-v1',
        'corpus_version_id': manifest['corpus_version_id'], 'manifest_sha256': manifest['manifest_sha256'],
        'reviewer': 'fixture-only', 'reviewed_at': '2026-11-05', 'evidence_paths': ['fixture-only'],
        'checks': {k: True for k in ('source_verified', 'extractor_contract', 'review_gate',
                                   'idempotent_rerun', 'postgres_neo4j_keys')}}


def test_stages_every_manifest_member_without_promoting_candidates(tmp_path):
    m, a = fixture()
    result = run(m, a, tmp_path, candidates={'a3': [{'source_span': 'invented'}]})
    assert result['staging_complete']
    assert result['counts'] == {'PENDING_REVIEW': 1, 'QUARANTINED': 1, 'NO_CANDIDATE': 1,
                                'ERROR': 0, 'MISSING_SOURCE': 0, 'UNPROCESSED': 0}
    assert result['review_decisions_written'] == result['database_writes'] == 0
    assert result['acceptance_status'] == 'NOT_EVALUATED'
    assert result['database_reconciliation']['status'] == 'NOT_READY'


def test_resume_processes_only_remaining_articles_and_preserves_events(tmp_path):
    m, a = fixture()
    first = run(m, a, tmp_path, limit=1)
    assert first['counts']['UNPROCESSED'] == 2 and not first['staging_complete']
    file = tmp_path / 'records' / (digest('a1') + '.json')
    original = file.read_bytes()
    second = run(m, a, tmp_path, resume=True)
    assert second['staging_complete'] and file.read_bytes() == original
    run(m, a, tmp_path, resume=True)
    assert len(list((tmp_path / 'records').glob('*.json'))) == 3
    with pytest.raises(ValueError, match='USE_RESUME'):
        run(m, a, tmp_path)


def test_resume_rejects_changed_source_proposals_or_checkpoint(tmp_path):
    m, a = fixture()
    run(m, a, tmp_path, limit=1)
    with pytest.raises(ValueError, match='INPUT_MISMATCH'):
        run(m, a, tmp_path, resume=True, candidates={'a2': []})
    a[0]['content'] += ' Changed.'
    with pytest.raises(ValueError, match='INPUT_MISMATCH'):
        run(m, a, tmp_path, resume=True)
    a[0]['content'] = 'FPT đã hoàn thiện hai AI Factory.'
    path = tmp_path / 'records' / (digest('a1') + '.json')
    saved = read_json(path); saved['record']['status'] = 'NO_CANDIDATE'
    path.write_text(json.dumps(saved), encoding='utf-8')
    with pytest.raises(ValueError, match='CHECKPOINT_CHANGED'):
        run(m, a, tmp_path, resume=True)


def test_missing_source_and_extractor_failure_are_accounted_and_retryable(tmp_path):
    m, a = fixture()
    def broken(article):
        raise RuntimeError('postgres://secret@private')
    result = run(m, a[:2], tmp_path, propose=broken)
    assert result['counts']['ERROR'] == 2 and result['counts']['MISSING_SOURCE'] == 1
    assert not result['staging_complete'] and result['all_articles_accounted_for']
    assert 'secret' not in ''.join(p.read_text('utf-8') for p in tmp_path.rglob('*.json'))
    result = run(m, a[:2], tmp_path, resume=True, retry_errors=True)
    assert result['counts']['ERROR'] == 0 and result['counts']['MISSING_SOURCE'] == 1


@pytest.mark.parametrize('change', ['missing', 'failed', 'scope', 'mock', 'partial'])
def test_full_run_requires_passed_scoped_live_receipt_before_writes(tmp_path, change):
    m, a = fixture(); r = receipt(m)
    if change == 'missing': r = None
    elif change == 'failed': r['status'] = 'FAIL'
    elif change == 'scope': r['manifest_sha256'] = 'wrong'
    elif change == 'mock': r['execution_mode'] = 'FIXTURE'
    else: r['checks']['review_gate'] = False
    with pytest.raises(ValueError, match='RECEIPT'):
        run(m, a, tmp_path, mode='full', receipt=r)
    assert not list(tmp_path.iterdir())


def test_full_staging_does_not_claim_database_acceptance(tmp_path):
    m, a = fixture()
    result = run(m, a, tmp_path, mode='full', receipt=receipt(m))
    assert result['staging_complete']
    assert result['acceptance_status'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('kind', ['duplicate', 'outside', 'tampered', 'candidates'])
def test_manifest_boundary_and_input_validation(tmp_path, kind):
    m, a = fixture(); c = None
    if kind == 'duplicate': a.append(a[0])
    elif kind == 'outside': a.append({'article_id': 'outside'})
    elif kind == 'tampered': m['manifest']['documents'][0]['document_id'] = 'tampered'
    else: c = {'outside': []}
    with pytest.raises(ValueError): run(m, a, tmp_path, candidates=c)


def inventories(m):
    header = {'corpus_version_id': m['corpus_version_id'], 'manifest_sha256': m['manifest_sha256'],
              'graph_version_id': 'fixture-graph'}
    approved = {'relation_id': 'r1', 'document_ids': ['da1'], 'review_status': 'APPROVED'}
    pending = {'relation_id': 'r2', 'document_ids': ['da3'], 'review_status': 'PENDING'}
    return ({**header, 'relations': [approved, pending]}, {**header, 'relations': [approved.copy()]})


def test_reconcile_exact_keys_and_document_statuses():
    m, _ = fixture(); pg, neo = inventories(m)
    result = reconcile(m, pg, neo)
    assert result['status'] == 'PASS' and result['postgres_relations'] == 2
    assert result['documents'][2]['postgres_status_counts']['PENDING'] == 1
    neo['relations'] = []
    assert reconcile(m, pg, neo)['missing_in_neo4j'] == ['r1']
    neo['relations'] = pg['relations']
    result = reconcile(m, pg, neo)
    assert result['status'] == 'FAIL' and result['unexpected_in_neo4j'] == ['r2']
    assert result['unapproved_in_neo4j'] == ['r2']


def test_reconcile_rejects_wrong_scope_duplicate_or_changed_source_keys():
    m, _ = fixture(); pg, neo = inventories(m)
    neo['relations'][0]['document_ids'] = ['da2']
    assert reconcile(m, pg, neo)['mismatched'] == ['r1']
    neo['graph_version_id'] = 'other'
    with pytest.raises(ValueError, match='SCOPE_MISMATCH'): reconcile(m, pg, neo)
    pg, neo = inventories(m); pg['relations'].append(pg['relations'][0])
    with pytest.raises(ValueError, match='INVENTORY_RECORD'): reconcile(m, pg, neo)


def test_lock_prevents_two_runners(tmp_path):
    m, a = fixture(); (tmp_path / '.runner.lock').touch()
    with pytest.raises(ValueError, match='RUN_LOCKED'): run(m, a, tmp_path)


def test_interruption_keeps_committed_article_and_releases_lock(tmp_path):
    from src.documents.news_event_extractor import rule_candidates
    m, a = fixture()
    def interrupted(article):
        if article['article_id'] == 'a2': raise KeyboardInterrupt()
        return rule_candidates(article)
    with pytest.raises(KeyboardInterrupt): run(m, a, tmp_path, propose=interrupted)
    assert not (tmp_path / '.runner.lock').exists()
    assert len(list((tmp_path / 'records').glob('*.json'))) == 1
    result = run(m, a, tmp_path, resume=True)
    assert result['staging_complete'] and result['counts']['PENDING_REVIEW'] == 1


def test_cli_reports_fixture_separately_and_blocks_full_without_receipt(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    m, a = fixture()
    manifest = tmp_path / 'manifest.json'; articles = tmp_path / 'articles.json'
    manifest.write_text(json.dumps(m), encoding='utf-8')
    articles.write_text(json.dumps(a), encoding='utf-8')
    script = Path(__file__).resolve().parents[1] / 'scripts/run_news_manifest.py'
    command = [sys.executable, str(script), '--manifest', str(manifest), '--articles', str(articles)]
    output = tmp_path / 'fixture-run'
    p = subprocess.run(command + ['--mode', 'fixture', '--output', str(output)], capture_output=True, text=True, encoding='utf-8')
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)['mode'] == 'fixture'
    blocked = tmp_path / 'full-run'
    p = subprocess.run(command + ['--mode', 'full', '--output', str(blocked)], capture_output=True, text=True, encoding='utf-8')
    assert p.returncode == 2
    assert json.loads(p.stderr)['reason'] == 'WBS09_5_RECEIPT_REQUIRED'
    assert not blocked.exists()
