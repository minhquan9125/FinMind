"""Benchmark evidence must never turn draft labels or fixtures into quality scores."""
from copy import deepcopy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from backend.scripts.wbs17_benchmark import (
    evaluate, http_send, normalize, request_body, run_benchmark, summarize, validate_suite,
)


def case(state='APPROVED'):
    return {'case_id': 'G01', 'question': 'FPT subsidiaries in 2025?', 'group': 'enterprise',
            'readiness': 'READY', 'gold': {'status': state, 'reviewer': 'reviewer-1',
            'reviewed_at': '2026-11-06T01:00:00+00:00', 'complete': False},
            'context': {'companies': ['FPT'], 'periods': ['2025']},
            'expected': {'route': 'GRAPH', 'status': 'OK', 'relations': [
                {'subject_id': 'fpt', 'object_id': 'ftel', 'relation_type': 'HAS_SUBSIDIARY',
                 'as_of': '2025-12-31', 'graph_version_id': 'v1'}],
                'chunk_ids': ['c1'], 'document_ids': ['d1']}}


def observed():
    return {'route': 'GRAPH', 'status': 'OK', 'execution_mode': 'LIVE',
            'relations': deepcopy(case()['expected']['relations']),
            'evidence': [{'chunk_id': 'c1', 'document_id': 'd1', 'source_verified': True}],
            'scope': {'companies': ['FPT'], 'periods': ['2025']},
            'scope_errors': []}


def test_draft_is_captured_but_never_scored():
    assert evaluate(case('DRAFT'), observed())['verdict'] == 'UNREVIEWED'


def test_draft_retains_diagnostic_checks_without_a_quality_verdict():
    response = observed()
    response['route'] = 'VECTOR'
    result = evaluate(case('DRAFT'), response)
    assert result['verdict'] == 'UNREVIEWED'
    assert result['diagnostic_checks']['route'] is False
    assert result['relation_precision'] is None


def test_b1_document_scope_does_not_override_router_question_interpretation():
    c = case()
    c['context'] = {}
    c['b1_context'] = {'companies': ['FPT'], 'periods': ['2025']}
    assert request_body('B1', c, {'corpus_version_id': 'c'})['period'] == '2025'
    assert request_body('B2', c, {})['context'] == {}


def test_shared_workbook_requires_five_measured_repeats_before_creating_output(tmp_path):
    with pytest.raises(ValueError, match='minimum'):
        run_benchmark({'cases': [case()], 'minimum_repeats': 5}, {}, tmp_path/'run', repeats=3)
    assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('field,value', [('subject_id', 'ftel'), ('as_of', '2024-12-31'),
                                        ('relation_type', 'HAS_ASSOCIATE'), ('graph_version_id', 'v2')])
def test_wrong_direction_time_type_or_version_fails(field, value):
    response = observed()
    response['relations'][0][field] = value
    assert evaluate(case(), response)['verdict'] == 'FAIL'


def test_partial_gold_reports_target_checks_without_precision_or_recall():
    result = evaluate(case(), observed())
    assert result['verdict'] == 'PASS'
    assert result['relation_precision'] is None and result['relation_recall'] is None


def test_gold_attributes_are_required_but_extra_runtime_metadata_is_allowed():
    c, response = case(), observed()
    c['expected']['relations'][0]['attributes'] = {'ownership_percent': '45.66'}
    response['relations'][0]['attributes'] = {'ownership_percent': '45.66', 'inference_basis': 'ownership_table'}
    assert evaluate(c, response)['verdict'] == 'PASS'
    response['relations'][0]['attributes']['ownership_percent'] = '80.15'
    assert evaluate(c, response)['verdict'] == 'FAIL'


def test_complete_gold_penalizes_extra_relations_and_deduplicates_paths():
    c, response = case(), observed()
    c['gold']['complete'] = True
    response['relations'] *= 2
    assert evaluate(c, response)['relation_precision'] == 1
    response['relations'].append(dict(response['relations'][0], object_id='unrelated'))
    score = evaluate(c, response)
    assert score['verdict'] == 'FAIL' and score['relation_precision'] == .5


def test_wrong_company_scope_or_missing_gold_chunk_cannot_pass():
    for response in [dict(observed(), scope={'companies': ['CTG'], 'periods': ['2025']}),
                     dict(observed(), evidence=[{'chunk_id': 'different', 'source_verified': True}])]:
        assert evaluate(case(), response)['verdict'] == 'FAIL'


def test_empty_no_data_requires_zero_facts_and_evidence():
    c = case()
    c['expected'] = {'route': 'GRAPH', 'status': 'NO_DATA', 'relations': [], 'chunk_ids': [], 'document_ids': []}
    assert evaluate(c, observed())['verdict'] == 'FAIL'


def test_unverified_evidence_and_fixture_cannot_pass():
    for response in [dict(observed(), execution_mode='FIXTURE'),
                     dict(observed(), evidence=[{'chunk_id': 'c1', 'source_verified': False}])]:
        assert evaluate(case(), response)['verdict'] == 'FAIL'


def test_router_normalization_flattens_paths_and_rejects_wrong_scope():
    payload = {'route': 'GRAPH', 'status': 'OK', 'execution_mode': 'LIVE', 'adapter_results': [
        {'adapter': 'GRAPH', 'provenance': 'LIVE/GRAPH', 'data': [
            {'graph_version_id': 'v1', 'relations': [dict(case()['expected']['relations'][0],
                corpus_id='other', index_version_id='i1')]}], 'evidence': observed()['evidence']}]}
    result = normalize('B2', payload, {'corpus_version_id': 'corpus', 'index_version_id': 'i1',
                                      'graph_version_ids': ['v1']})
    assert len(result['relations']) == 1
    assert result['scope_errors']


def test_b1_uses_same_question_and_explicit_corpus_without_graph_parameters():
    body = request_body('B1', case(), {'corpus_version_id': 'corpus'})
    assert body == {'query': case()['question'], 'corpus_version_id': 'corpus',
                    'company_symbol': 'FPT', 'period': '2025', 'top_k': 5}


def test_suite_rejects_duplicate_ids_or_unattributed_approval():
    for cases in [[case(), case()], [dict(case(), gold={'status': 'APPROVED'})]]:
        with pytest.raises(ValueError):
            validate_suite({'cases': cases})


def test_runner_skips_not_ready_keeps_warmup_and_errors_and_alternates_order(tmp_path):
    calls = []
    def send(profile, body, timeout):
        calls.append(profile['kind'])
        if profile['kind'] == 'B1':
            raise TimeoutError('must not leak arbitrary exception messages')
        return 200, {'route': 'GRAPH', 'status': 'NO_DATA', 'execution_mode': 'LIVE', 'adapter_results': []}
    config = {'scope': {'corpus_version_id': 'corpus', 'index_version_id': 'i1', 'graph_version_ids': ['v1']},
              'profiles': {'B1': {'kind': 'B1'}, 'B2': {'kind': 'B2'}}}
    c = case('DRAFT')
    suite = {'cases': [c, dict(c, case_id='G02', readiness='NOT_READY', blocked_reason='no source')]}
    rows = run_benchmark(suite, config, tmp_path/'run', send=send, warmups=1, repeats=2)
    assert calls == ['B1', 'B2', 'B1', 'B2', 'B2', 'B1']
    assert sum(r['phase'] == 'WARMUP' for r in rows) == 2
    report = summarize(rows)
    assert report['profiles']['B1']['transport_errors'] == 2
    assert report['profiles']['B1']['latency_http200_p50_ms'] is None
    assert report['profiles']['B2']['scored'] == 0
    assert len(list((tmp_path/'run').glob('results.jsonl'))) == 1
    with pytest.raises(FileExistsError):
        run_benchmark(suite, config, tmp_path/'run', send=send)


def test_real_http_transport_and_normalization_with_isolated_stub_server(tmp_path):
    """HTTP integration only: server data is synthetic, never a live benchmark receipt."""
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append((self.path, body))
            if self.path == '/vector':
                response = {'corpus_version_id': 'corpus', 'index_version_id': 'i1', 'results': [
                    dict(observed()['evidence'][0], company_symbol='FPT', period='2025')]}
            else:
                response = {'route': 'GRAPH', 'status': 'OK', 'execution_mode': 'LIVE',
                    'scope': observed()['scope'], 'adapter_results': [{'adapter': 'GRAPH',
                    'provenance': 'LIVE/GRAPH', 'evidence': observed()['evidence'], 'data': [
                    {'graph_version_id': 'v1', 'relations': [dict(observed()['relations'][0],
                     corpus_id='corpus', index_version_id='i1')]}]}]}
            data = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        config = {'scope': {'corpus_version_id': 'corpus', 'index_version_id': 'i1', 'graph_version_ids': ['v1']},
                  'profiles': {'B1': {'kind': 'B1', 'url': base+'/vector'},
                               'B2': {'kind': 'B2', 'url': base+'/router'}}}
        rows = run_benchmark({'cases': [case()]}, config, tmp_path/'http', send=http_send, warmups=0, repeats=1)
        assert [r['evaluation']['verdict'] for r in rows] == ['PASS', 'PASS']
        assert received[0][1]['query'] == received[1][1]['question']
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_checked_in_draft_has_no_approved_gold_and_covers_required_groups():
    from pathlib import Path
    suite = json.loads((Path(__file__).resolve().parents[2]/'docs/sprint4/wbs17/cases.draft.json').read_text('utf-8'))
    validate_suite(suite)
    assert len(suite['cases']) == 18
    assert all(c['gold']['status'] == 'DRAFT' for c in suite['cases'])
    assert {c['group'] for c in suite['cases']} >= {'enterprise', 'role', 'event', 'vector', 'both', 'error'}


def test_cli_plan_is_reproducible_and_live_requires_environment_confirmation(tmp_path):
    from pathlib import Path
    import subprocess
    import sys
    repo = Path(__file__).resolve().parents[2]
    command = [sys.executable, '-m', 'backend.scripts.wbs17_benchmark', '--output', str(tmp_path/'plan')]
    planned = subprocess.run(command+['--dry-run'], cwd=repo, capture_output=True, text=True)
    assert planned.returncode == 0, planned.stderr
    manifest = json.loads((tmp_path/'plan/manifest.json').read_text('utf-8'))
    assert manifest['dry_run'] is True and len(manifest['suite_sha256']) == 64
    assert manifest['suite']['cases'][0]['gold']['status'] == 'DRAFT'
    assert (tmp_path/'plan/plan.json').exists()
    assert not (tmp_path/'plan/results.jsonl').exists()
    live = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert live.returncode != 0
    assert 'Confirm corpus/model/deployment' in live.stderr
