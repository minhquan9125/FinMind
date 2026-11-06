"""Read-only B1 vector / B2 router retrieval trials; draft gold is never scored.

Run from the repository root: python -m backend.scripts.wbs17_benchmark --help
Only standard-library networking is used. No login, review or graph writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import median
import subprocess
from time import perf_counter
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def validate_suite(suite):
    seen = set()
    for c in suite['cases']:
        if not c.get('case_id') or c['case_id'] in seen or not c.get('question'):
            raise ValueError('Missing question or duplicate/missing case_id')
        seen.add(c['case_id'])
        if c.get('readiness') not in {'READY', 'NOT_READY'}:
            raise ValueError('Invalid readiness')
        if c['readiness'] == 'NOT_READY' and not c.get('blocked_reason'):
            raise ValueError('NOT_READY requires blocked_reason')
        gold = c.get('gold', {})
        if gold.get('status') not in {'DRAFT', 'APPROVED'}:
            raise ValueError('Invalid gold status')
        if gold['status'] == 'APPROVED':
            if not gold.get('reviewer') or not gold.get('reviewed_at'):
                raise ValueError('APPROVED gold requires reviewer and reviewed_at')
            if datetime.fromisoformat(gold['reviewed_at']).utcoffset() is None:
                raise ValueError('Gold reviewed_at requires a timezone')
            expected = c.get('expected', {})
            if not expected.get('route') or not expected.get('status'):
                raise ValueError('Approved gold requires expected route/status')
            if expected['status'] == 'OK' and not expected.get('chunk_ids'):
                raise ValueError('Approved successful case requires gold chunks')
            for relation in expected.get('relations', []):
                if not all(k in relation for k in ('subject_id', 'object_id', 'relation_type', 'as_of', 'graph_version_id')):
                    raise ValueError('Gold relations require direction, type, as_of and graph version')
    if not seen:
        raise ValueError('Empty suite')


def request_body(kind, case, scope):
    if kind == 'B2':
        return {'question': case['question'], 'context': case.get('context', {})}
    context = case.get('context', {})
    companies, periods = context.get('companies', []), context.get('periods', [])
    if len(companies) > 1 or len(periods) > 1:
        raise ValueError('B1 filtered endpoint cannot represent multi-company/period scope')
    return {'query': case['question'], 'corpus_version_id': scope['corpus_version_id'],
            'company_symbol': next(iter(companies), None),
            'period': next(iter(periods), None), 'top_k': 5}


def normalize(kind, payload, scope):
    """Keep factual fields; never infer citations/relations from generated prose."""
    result = {'route': 'VECTOR' if kind == 'B1' else payload.get('route'),
              'status': payload.get('status'), 'execution_mode': payload.get('execution_mode'),
              'relations': [], 'evidence': [], 'scope_errors': [], 'scope': payload.get('scope', {})}
    def check(value, expected, field):
        if value != expected:
            result['scope_errors'].append(field)
    if kind == 'B1':
        hits = payload['results']
        result.update(status='OK' if hits else 'NO_DATA', execution_mode='LIVE', evidence=hits)
        check(payload.get('corpus_version_id'), scope['corpus_version_id'], 'corpus_version_id')
        check(payload.get('index_version_id'), scope['index_version_id'], 'index_version_id')
        result['scope'] = {'companies': sorted({h['company_symbol'] for h in hits if h.get('company_symbol')}),
                           'periods': sorted({h['period'] for h in hits if h.get('period')})}
    else:
        for adapter in payload.get('adapter_results', []):
            if adapter.get('provenance') not in {'LIVE/GRAPH', 'LIVE/VECTOR'}:
                result['scope_errors'].append('non_live_adapter')
            result['evidence'].extend(adapter.get('evidence', []))
            if adapter.get('adapter') == 'GRAPH':
                for path in adapter.get('data', []):
                    version = path.get('graph_version_id')
                    if version not in scope['graph_version_ids']:
                        result['scope_errors'].append('graph_version_id')
                    for edge in path.get('relations', []):
                        result['relations'].append(dict(edge, graph_version_id=version))
                        check(edge.get('corpus_id'), scope['corpus_version_id'], 'corpus_id')
                        check(edge.get('index_version_id'), scope['index_version_id'], 'index_version_id')
            else:
                # Router CONTENT evidence uses source_id, not chunk_id/document_id.
                for hit in adapter.get('data', []):
                    result['evidence'].append(dict(hit, source_verified=False))
        # Use verified citations to enrich CONTENT hits without inventing verification.
        verified = {e.get('source_id'): e for e in result['evidence'] if e.get('source_id')}
        for e in result['evidence']:
            if e.get('chunk_id') in verified:
                e['source_verified'] = verified[e['chunk_id']].get('source_verified') is True
        for e in result['evidence']:
            if e.get('source_id'):
                check(e.get('index_version_id'), scope['index_version_id'], 'evidence_index')
            elif e.get('index_version_id'):
                check(e['index_version_id'], scope['index_version_id'], 'evidence_index')
    return result


def evaluate(case, response, profile='B2'):
    if case['gold']['status'] != 'APPROVED':
        return {'verdict': 'UNREVIEWED', 'relation_precision': None, 'relation_recall': None}
    expected = case['expected']
    evidence, relations = response['evidence'], response['relations']
    chunks = {e.get('chunk_id') or e.get('source_id') for e in evidence}
    documents = {e.get('document_id') for e in evidence}
    wanted_chunks, wanted_docs = set(expected.get('chunk_ids', [])), set(expected.get('document_ids', []))
    checks = {'live': response['execution_mode'] == 'LIVE', 'scope': not response['scope_errors'],
              'source_verified': all(e.get('source_verified') is True for e in evidence),
              'gold_chunks': wanted_chunks <= chunks, 'gold_documents': wanted_docs <= documents}
    if profile == 'B2':
        checks.update(route=response['route'] == expected['route'], status=response['status'] == expected['status'])
        for field in ('companies', 'periods'):
            requested = case.get('context', {}).get(field, [])
            if requested:
                checks[field] = set(response.get('scope', {}).get(field, [])) == set(requested)
        checks['relations'] = all(any(all(actual.get(k) == v for k, v in gold.items())
                                     for actual in relations) for gold in expected.get('relations', []))
    else:
        checks['status'] = response['status'] == expected.get('b1_status', 'OK')
        for field in ('companies', 'periods'):
            requested = set(case.get('context', {}).get(field, []))
            if requested and evidence:
                checks[field] = set(response.get('scope', {}).get(field, [])) == requested
    if expected['status'] == 'OK':
        checks['has_evidence'] = bool(evidence)
    elif profile == 'B2':
        checks['no_facts_on_error'] = not relations and not evidence
    # Exact-set relation metrics are possible only with complete adjudicated gold.
    precision = recall = None
    if profile == 'B2' and case['gold'].get('complete') and expected.get('relations'):
        fields = ('subject_id', 'object_id', 'relation_type', 'as_of', 'graph_version_id')
        keys = lambda rows: {tuple(r.get(k) for k in fields) for r in rows}
        actual, gold = keys(relations), keys(expected['relations'])
        correct = len(actual & gold)
        precision, recall = correct / len(actual) if actual else 0.0, correct / len(gold)
        checks['exact_relations'] = actual == gold
    return {'verdict': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'relation_precision': precision, 'relation_recall': recall,
            'required_chunk_coverage': len(wanted_chunks & chunks)/len(wanted_chunks) if wanted_chunks else None}


def http_send(profile, body, timeout):
    headers = {'Content-Type': 'application/json'}
    if profile.get('token_env'):
        headers['Authorization'] = 'Bearer ' + os.environ[profile['token_env']]
    request = Request(profile['url'], data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, {'error': 'HTTP_ERROR'}


def summarize(rows):
    profiles = {}
    for profile in ('B1', 'B2'):
        measured = [r for r in rows if r['phase'] == 'MEASURED' and r['profile'] == profile]
        latencies = sorted(r['latency_ms'] for r in measured if r.get('http_status') == 200 and not r.get('error'))
        verdicts = Counter(r['evaluation']['verdict'] for r in measured)
        profiles[profile] = {'attempts': len(measured), 'scored': verdicts['PASS']+verdicts['FAIL'],
            'verdicts': dict(verdicts), 'transport_errors': sum(bool(r.get('error')) for r in measured),
            'http_errors': sum(r.get('http_status', 200) != 200 for r in measured),
            'application_statuses': dict(Counter(r.get('normalized', {}).get('status') for r in measured)),
            'latency_http200_p50_ms': median(latencies) if latencies else None,
            'latency_http200_p95_ms': latencies[math.ceil(len(latencies)*.95)-1] if latencies else None,
            'scope_errors': dict(Counter(error for r in measured for error in r.get('normalized', {}).get('scope_errors', []))),
            'by_group': {group: dict(Counter(r['evaluation']['verdict'] for r in measured if r['group']==group))
                         for group in sorted({r['group'] for r in measured})},
            'failed_checks': dict(Counter(check for r in measured for check, ok in r['evaluation'].get('checks', {}).items() if not ok))}
    return {'profiles': profiles, 'skipped': [r for r in rows if r['phase'] == 'SKIPPED'],
            'quality_claim': 'No B2 superiority claim; draft cases excluded from scoring.',
            'level': 'retrieval_only', 'latency_note': 'HTTP round trip; HTTP-200 application errors retained in status counts; warmup excluded.'}


def write_report(output, report):
    lines = ['# WBS17 — retrieval trial', '',
             'B1: dense vector API. B2: hybrid router API. Answer quality and UI E2E are not evaluated.', '',
             'Gold DRAFT is unscored. PASS means required checks passed; partial gold does not establish full recall/precision.', '',
             '| Profile | Attempts | Scored | PASS | FAIL | Transport/schema errors | HTTP errors | HTTP-200 p50 ms | HTTP-200 p95 ms |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, values in report['profiles'].items():
        verdicts = values['verdicts']
        cells = [name, values['attempts'], values['scored'], verdicts.get('PASS', 0), verdicts.get('FAIL', 0),
                 values['transport_errors'], values['http_errors'], values['latency_http200_p50_ms'], values['latency_http200_p95_ms']]
        lines.append('| '+' | '.join('—' if v is None else str(v) for v in cells)+' |')
    lines.extend(['', report['latency_note'], '', 'No superiority claim is made. See summary.json for group/status/scope errors and results.jsonl for every request and response.', '', '## NOT_READY', ''])
    lines.extend(f"- {r['case_id']}: {r['reason']}" for r in report['skipped'])
    (output/'report.md').write_text('\n'.join(lines)+'\n', 'utf-8')


def run_benchmark(suite, config, output, *, send=http_send, warmups=1, repeats=3, timeout=60, manifest=None):
    validate_suite(suite)
    if warmups < 0 or repeats < 1:
        raise ValueError('Invalid warmup/repeat count')
    output.mkdir(parents=True, exist_ok=False)
    if manifest is not None:
        (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    rows = []
    def record(row):
        rows.append(row)
        with (output/'results.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
    for case in suite['cases']:
        if case['readiness'] == 'NOT_READY':
            record({'case_id': case['case_id'], 'phase': 'SKIPPED', 'reason': case['blocked_reason']})
            continue
        for iteration in range(warmups + repeats):
            phase = 'WARMUP' if iteration < warmups else 'MEASURED'
            repeat = iteration - warmups
            order = ('B1', 'B2') if phase == 'WARMUP' or repeat % 2 == 0 else ('B2', 'B1')
            for profile in order:
                row = {'case_id': case['case_id'], 'group': case['group'], 'question': case['question'],
                       'profile': profile, 'phase': phase, 'repeat': repeat,
                       'timestamp': datetime.now(timezone.utc).isoformat()}
                start = perf_counter()
                try:
                    body = request_body(profile, case, config['scope'])
                    code, payload = send(config['profiles'][profile], body, timeout)
                    row['latency_ms'] = round((perf_counter()-start)*1000, 3)
                    row.update(http_status=code, request=body, response=payload)
                    if code != 200:
                        row['evaluation'] = {'verdict': 'HTTP_ERROR'}
                    else:
                        response = normalize(profile, payload, config['scope'])
                        row.update(normalized=response, evaluation=evaluate(case, response, profile))
                except Exception as exc:
                    # Never persist exception strings: URLs/headers can contain credentials.
                    row.update(error=type(exc).__name__, evaluation={'verdict': 'TRANSPORT_OR_SCHEMA_ERROR'})
                row.setdefault('latency_ms', round((perf_counter()-start)*1000, 3))
                record(row)
    report = summarize(rows)
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    write_report(output, report)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, default=Path('docs/sprint4/wbs17/cases.draft.json'))
    parser.add_argument('--config', type=Path, default=Path('docs/sprint4/wbs17/run-config.example.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true', help='Validate and write a plan; no HTTP calls')
    parser.add_argument('--warmups', type=int, default=1)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    suite = json.loads(args.suite.read_text('utf-8'))
    config = json.loads(args.config.read_text('utf-8'))
    validate_suite(suite)
    if config['scope'] != suite['scope']:
        raise ValueError('Run config must match the suite corpus/index/graph scope exactly')
    for kind, profile in config['profiles'].items():
        url = urlsplit(profile['url'])
        if kind not in {'B1', 'B2'} or profile['kind'] != kind or url.scheme not in {'http', 'https'} or url.username or url.password or url.query:
            raise ValueError('Invalid profile or URL; keep credentials in token_env only')
    if set(config['profiles']) != {'B1', 'B2'}:
        raise ValueError('Both B1 and B2 are required')
    if not args.dry_run and config.get('operator_confirmed_same_environment') is not True:
        raise ValueError('Confirm corpus/model/deployment settings in a local run config first')
    if not args.dry_run and not all(config.get(k) for k in ('embedding_model_ref', 'deployment_ref', 'machine_ref')):
        raise ValueError('Record model, deployment commit/config receipt, and machine before running')
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    manifest = {'suite_sha256': hashlib.sha256(args.suite.read_bytes()).hexdigest(),
                'config_sha256': hashlib.sha256(args.config.read_bytes()).hexdigest(),
                'suite': suite, 'config': config, 'dry_run': args.dry_run,
                'warmups': args.warmups, 'repeats': args.repeats, 'timeout_seconds': args.timeout,
                'runner_git_head': revision, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'created_at': datetime.now(timezone.utc).isoformat()}
    if args.dry_run:
        args.output.mkdir(parents=True, exist_ok=False)
        plan = [{'case_id': c['case_id'], 'readiness': c['readiness'], 'gold_status': c['gold']['status'],
                 'requests': {p: request_body(p, c, config['scope']) for p in ('B1', 'B2')} if c['readiness']=='READY' else {}}
                for c in suite['cases']]
        (args.output/'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')
    else:
        run_benchmark(suite, config, args.output, warmups=args.warmups, repeats=args.repeats, timeout=args.timeout, manifest=manifest)
    (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'output': str(args.output), 'dry_run': args.dry_run,
                      'cases': len(suite['cases']), 'approved_gold': sum(c['gold']['status']=='APPROVED' for c in suite['cases'])}))


if __name__ == '__main__':
    main()
