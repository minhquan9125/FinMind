"""Independent S5-WBS04.3 acceptance checks; never tune policy, gold or model."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
BUSINESS = ROOT / 'docs/sprint5/router-acceptance-v1/business.jsonl'
POLICY = ROOT / 'backend/src/retrieval_orchestration/intent_routing.py'
ROUTES = dict(NUMERIC='VECTOR', REPORT_CONTENT='VECTOR', NEWS='VECTOR',
              PERSON_ROLE='GRAPH', ENTITY_RELATION='GRAPH', TREND='BOTH')
LABELS = ['ENTITY_RELATION', 'MIXED', 'NEWS', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']
GATES = ['line_coverage', 'branch_coverage', 'behavior_coverage', 'policy_success',
         'new_question_success', 'regression_success', 'new_label_accuracy', 'new_candidate_route_accuracy']
REQUIREMENTS = sorted({*(f'LABEL_{label}' for label in LABELS), 'DEFAULT_FALLBACK',
    'MIXED_VECTOR_VECTOR', 'MIXED_GRAPH_GRAPH', 'MIXED_GRAPH_VECTOR', 'MIXED_UNVERIFIED',
    'LOW_CONFIDENCE', 'SMALL_GAP', 'THRESHOLD_BOUNDARY', 'MISSING_COMPANY', 'INVALID_COMPANY',
    'CONTEXT', 'INVALID_PERIOD', 'VALID_PERIOD', 'SCORE_METADATA', 'SCORE_VALIDATION',
    'DISTINCT_GROUPS', 'CLASSIFIER_UNCALIBRATED', 'V7_EVIDENCE', 'LABEL_DISAGREEMENT',
    'CONTRACT_FAILURE', 'CLASSIFIER_ERROR', 'CONFIGURATION', 'PRIVACY', 'CLARIFICATION_PRIORITY',
    'CANDIDATE_TOP3'})


def acceptance_verdict(metrics):
    failed = [k for k in GATES if type(metrics.get(k)) not in (int, float)
              or not math.isfinite(metrics[k]) or not .9 <= metrics[k] <= 1]
    return {'status': 'FAIL' if failed else 'PASS', 'failed_gates': failed, 'threshold': .9}


def check_expected(actual, expected):
    errors = []
    for path, value in expected.items():
        node = actual
        key = path.removeprefix('len:')
        try:
            for part in key.split('.'):
                node = node[int(part)] if isinstance(node, list) else node[part]
            if path.startswith('len:'):
                node = len(node)
        except (KeyError, IndexError, TypeError, ValueError):
            node = '<MISSING>'
        if node != value:
            errors.append(f'{path}: expected={value!r}, actual={node!r}')
    return errors


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def cosine(label='PERSON_ROLE', first=.9, second=.2):
    return dict(ranking_policy='cosine-max-per-label-v1', score_type='COSINE_SIMILARITY_NOT_PROBABILITY',
                groups=[dict(intent_label=label, score=first),
                        dict(intent_label='NEWS' if label != 'NEWS' else 'NUMERIC', score=second)])


def resolution(**changes):
    return dict(ranking_policy='intent-request-objectives-v5', score_type='DECISION_EVIDENCE_NO_CONFIDENCE',
                intent_label='PERSON_ROLE', confidence=None, reason='EXPLICIT_REQUEST_TYPE',
                component_labels=[], runtime_enabled=False, explicit_evidence=[], unresolved_requests=[]) | changes


def policy_cases():
    """Contract partitions and adversarial inputs; scores here are explicit fixtures."""
    cases = []
    def add(name, tags, *, ranking=None, scope=None, expected=None, error=None, **options):
        cases.append(dict(test_id=f'S5-043-P{len(cases)+1:03}', question='Ai là Chủ tịch FPT năm 2025?',
            category=name, requirement_ids=tags, ranking=deepcopy(cosine() if ranking is None else ranking),
            scope={'company_ticker': 'FPT', 'period': '2025'} | (scope or {}),
            expected=expected or dict(decision='NEED_FALLBACK', route=None, reason_code='DIRECT_SEARCH_DISABLED'),
            expected_error=error, **options))
    for label, route in ROUTES.items():
        for diagnostic in (False, True):
            add(f'{label}, diagnostic={diagnostic}', [f'LABEL_{label}', 'DEFAULT_FALLBACK'], ranking=cosine(label),
                diagnostic=diagnostic, expected=dict(decision='SEARCH', route=route, intent_label=label)
                if diagnostic else None)
    aliases = dict(SO_LIEU='NUMERIC', BCTC_BCTN='REPORT_CONTENT', CHUC_VU='PERSON_ROLE',
                   QUAN_HE='ENTITY_RELATION', XU_HUONG='TREND')
    for alias, label in aliases.items():
        add(f'Alias {alias}', [f'LABEL_{label}'], ranking=cosine(alias), diagnostic=True,
            expected=dict(decision='SEARCH', route=ROUTES[label], intent_label=label))
    for components, route, tag in [(['NUMERIC', 'NEWS'], 'VECTOR', 'MIXED_VECTOR_VECTOR'),
            (['PERSON_ROLE', 'ENTITY_RELATION'], 'GRAPH', 'MIXED_GRAPH_GRAPH'),
            (['PERSON_ROLE', 'REPORT_CONTENT'], 'BOTH', 'MIXED_GRAPH_VECTOR'),
            (['CHUC_VU', 'BCTC_BCTN'], 'BOTH', 'MIXED_GRAPH_VECTOR'),
            (['NUMERIC', 'TREND'], 'BOTH', 'MIXED_GRAPH_VECTOR')]:
        add(f'MIXED {components}', ['LABEL_MIXED', tag], ranking=cosine('MIXED'), diagnostic=True,
            components=components, confirmed=True, expected=dict(decision='SEARCH', route=route, intent_label='MIXED'))
    for confirmed in (False, None, 1):
        add('Unverified MIXED', ['LABEL_MIXED', 'MIXED_UNVERIFIED'], ranking=cosine('MIXED'),
            diagnostic=True, components=['PERSON_ROLE', 'NEWS'], confirmed=confirmed,
            expected=dict(decision='NEED_FALLBACK', route=None, reason_code='MIXED_COMPONENTS_REQUIRED'))
    for components in ([], ['NEWS'], ['NEWS', 'NEWS'], ['MIXED', 'NEWS'], ['UNKNOWN', 'NEWS'], 'NEWS'):
        add('Bad component contract', ['MIXED_UNVERIFIED', 'CONTRACT_FAILURE'], ranking=cosine('MIXED'),
            diagnostic=True, components=components, confirmed=True, error='ANY_CONTRACT_ERROR')
    for first, second, outcome in [(.65, .57, 'SEARCH'), (.649999, .2, 'LOW_CONFIDENCE'),
            (.8, .720001, 'SMALL_GAP'), (.8, .72, 'SEARCH'), (.64, .63, 'LOW_CONFIDENCE_AND_SMALL_GAP'),
            (-.2, -.3, 'LOW_CONFIDENCE'), (.5, .5, 'LOW_CONFIDENCE_AND_SMALL_GAP'),
            (1, -1, 'SEARCH'), (.65, .570001, 'SMALL_GAP'), (.650001, .570001, 'SEARCH')]:
        add(f'Threshold {first}/{second}', ['THRESHOLD_BOUNDARY', 'LOW_CONFIDENCE', 'SMALL_GAP'],
            ranking=cosine(first=first, second=second), diagnostic=True,
            expected=dict(decision='SEARCH', route='GRAPH') if outcome == 'SEARCH' else
            dict(decision='NEED_FALLBACK', route=None, reason_code=outcome))
    missing = dict(decision='ASK_CLARIFICATION', route=None, need_fallback=False, reason_code='MISSING_COMPANY')
    add('No company', ['MISSING_COMPANY', 'CLARIFICATION_PRIORITY'], scope={'company_ticker': None},
        mode='wrapper', expected=missing | {'_matcher_calls': 0})
    for bad in ['', 'BCTC', '123', 'FPT VCB', 1, ['FPT']]:
        add('Invalid company', ['INVALID_COMPANY'], scope={'company_ticker': bad}, mode='wrapper',
            expected=missing | {'reason_code': 'INVALID_COMPANY', '_matcher_calls': 0})
    add('Registry rejects unknown ticker', ['INVALID_COMPANY'], scope={'valid_tickers': ['VCB']},
        expected=missing | {'reason_code': 'INVALID_COMPANY'})
    for same, confirmed in [(False, True), (True, False), (False, False)]:
        add('Untrusted session context', ['CONTEXT', 'MISSING_COMPANY'], mode='wrapper',
            scope=dict(company_ticker=None, context_company_ticker='VCB', context_same_session=same,
                       context_confirmed=confirmed), expected=missing | {'_matcher_calls': 0})
    for context in ['VCB', ['VCB']]:
        add('Confirmed context', ['CONTEXT'], scope=dict(company_ticker=None, context_company_ticker=context,
            context_same_session=True, context_confirmed=True), expected=dict(decision='NEED_FALLBACK',
                **{'scope.company_ticker': 'VCB', 'scope.company_source': 'CONTEXT'}))
    for context in [[], ['FPT', 'VCB']]:
        add('Ambiguous context', ['CONTEXT'], scope=dict(company_ticker=None, context_company_ticker=context,
            context_same_session=True, context_confirmed=True), expected=missing | {'reason_code': 'AMBIGUOUS_CONTEXT_COMPANY'})
    add('Current company overrides context', ['CONTEXT'], scope=dict(context_company_ticker='VCB',
        context_same_session=True, context_confirmed=True), expected={'scope.company_ticker': 'FPT', 'scope.company_source': 'CURRENT'})
    add('Market-wide news needs no company', ['MISSING_COMPANY'], scope=dict(company_ticker=None, company_required=False))
    for text in ['quý 5/2025', 'Q 0/2025', 'quý +5', 'quý -1', 'quý 1.5', 'quý 1,5/2025',
                 'quý 1 và 5/2025', 'quý 1-6 năm 2025', 'ngày 31/2/2025', '2025-02-29']:
        add(text, ['INVALID_PERIOD', 'CLARIFICATION_PRIORITY'], mode='wrapper',
            expected=missing | {'reason_code': 'INVALID_PERIOD', '_matcher_calls': 0})
        cases[-1]['question'] = f'Doanh thu FPT {text}?'
    for text in ['Q3-2025', 'quý 2 - 2025', 'quý 1 đến 30/6/2025', 'quý 1 đến 6/2025',
                 'quý 1 - 06/2025', 'quý 1–06/2025', 'quý 1—6/2025', 'quý 1,2/2025',
                 'quý 1 và 2/2025', 'ngày 29/2/2024']:
        add(text, ['VALID_PERIOD']); cases[-1]['question'] = f'Doanh thu FPT {text}?'
    for period in ['', '0000', '0000-Q2', '2025-Q5', '2025-02-30', 2025, [], True, 'UNKNOWN']:
        add('Invalid resolved period', ['INVALID_PERIOD'], scope={'period': period},
            expected=missing | {'reason_code': 'INVALID_PERIOD'})
    for period in ['2025-Q1', '2025-11-04', 'LATEST_AVAILABLE_PERIOD', 'CURRENT', 'CURRENT_YEAR',
                   'PREVIOUS_YEAR', 'CURRENT_QUARTER', 'PREVIOUS_QUARTER', 'LATEST_PUBLISHED_PERIOD', None]:
        add('Supported period token', ['VALID_PERIOD'], scope={'period': period})
    for text in [None, '   ', 'x'*4001]:
        for mode in ['function', 'wrapper']:
            add('Invalid user input', ['CLARIFICATION_PRIORITY'], mode=mode,
                expected=missing | {'reason_code': 'INVALID_QUESTION'})
            cases[-1]['question'] = text
    add('Empty wrapper input', ['CLARIFICATION_PRIORITY'], mode='wrapper',
        expected=missing | {'reason_code': 'INVALID_QUESTION'}); cases[-1]['question'] = ''
    for field in ['ranking_policy', 'score_type']:
        for value in ['DELETE', None, '', 'UNKNOWN']:
            payload = cosine()
            if value == 'DELETE': del payload[field]
            else: payload[field] = value
            add('Missing/unknown score metadata', ['SCORE_METADATA', 'CONTRACT_FAILURE'], ranking=payload, error='ANY_CONTRACT_ERROR')
    mutations = [dict(groups=[]), dict(groups=[{'intent_label': 'PERSON_ROLE', 'score': .9}]),
                 dict(groups='not-a-list'), dict(question='A stale different question')]
    for value in [True, None, '0.9', float('nan'), float('inf'), -1.1, 1.1]:
        payload = cosine(); payload['groups'][0]['score'] = value; mutations.append(payload)
    for value in ['UNKNOWN', None, [], 'NEWS']:
        payload = cosine(); payload['groups'][0]['intent_label'] = value; mutations.append(payload)
    for value in [True, 2, '1']:
        payload = cosine(); payload['groups'][0]['rank'] = value; mutations.append(payload)
    payload = cosine(); payload['groups'][1]['score'] = .95; mutations.append(payload)
    for change in mutations:
        add('Malformed ranking', ['SCORE_VALIDATION', 'DISTINCT_GROUPS', 'CONTRACT_FAILURE'],
            ranking=cosine() | change, error='ANY_CONTRACT_ERROR')
    add('Examples are not competing groups', ['DISTINCT_GROUPS'], diagnostic=True,
        ranking=cosine() | {'examples': [{'intent_label': 'NEWS', 'score': 1}]*5},
        expected=dict(decision='SEARCH', route='GRAPH'))
    payload = cosine(); payload['groups'] += [dict(intent_label='NUMERIC', score=.1), dict(intent_label='TREND', score=0)]
    add('Top3 groups and privacy', ['CANDIDATE_TOP3', 'PRIVACY'], ranking=payload | {'history': ['SECRET']},
        expected={'len:fallback_payload.candidates': 3, 'fallback_payload.candidates.2.intent_label': 'NUMERIC',
                  'fallback_payload.score_type': 'COSINE_SIMILARITY_NOT_PROBABILITY'})
    classifier = cosine() | {'ranking_policy': 'intent-linear-v1', 'score_type': 'CLASSIFIER_PROBABILITY_UNCALIBRATED'}
    for diagnostic in (False, True):
        add('Uncalibrated classifier', ['CLASSIFIER_UNCALIBRATED'], ranking=classifier, diagnostic=diagnostic,
            expected=dict(decision='NEED_FALLBACK', route=None, reason_code='UNCALIBRATED_CLASSIFICATION'))
    for version in ['intent-request-consensus-v1'] + [f'intent-request-objectives-v{i}' for i in range(1, 6)]:
        add('Supported evidence version', ['V7_EVIDENCE'], ranking=resolution(ranking_policy=version),
            expected=dict(decision='NEED_FALLBACK', route=None, reason_code='UNCALIBRATED_CLASSIFICATION'))
    for base_label in ['PERSON_ROLE', 'NUMERIC']:
        base = deepcopy(classifier); base['groups'][0]['intent_label'] = base_label
        add('Producer resolution envelope', ['LABEL_DISAGREEMENT', 'V7_EVIDENCE'],
            ranking={'base_ranking': base, 'resolution': resolution()},
            expected=dict(decision='NEED_FALLBACK', route=None, reason_code=(
                'LABEL_DISAGREEMENT' if base_label != 'PERSON_ROLE' else 'UNCALIBRATED_CLASSIFICATION')))
    for change in [dict(confidence=.9), dict(intent_label='UNKNOWN'), dict(reason=''), dict(reason=3),
            dict(component_labels='NEWS'), dict(component_labels=['NEWS', 'NEWS']),
            dict(component_labels=['MIXED', 'NEWS']), dict(runtime_enabled=True),
            dict(unresolved_requests=[1]), dict(explicit_evidence=[1]),
            dict(explicit_evidence=[{'text': '', 'intent_label': 'NEWS'}])]:
        add('Bad evidence contract', ['V7_EVIDENCE', 'CONTRACT_FAILURE'], ranking=resolution(**change), error='ANY_CONTRACT_ERROR')
    for evidence in [dict(), dict(base_ranking=classifier), dict(resolution=resolution()),
            dict(base_ranking=classifier, resolution=resolution(), groups=[]),
            dict(base_ranking=classifier, resolution=resolution(), question='Stale query')]:
        add('Bad envelope', ['V7_EVIDENCE', 'CONTRACT_FAILURE'], ranking=evidence, error='ANY_CONTRACT_ERROR')
    for action in ['timeout', 'technical_error', 'empty', 'contract_error']:
        add('Matcher '+action, ['CLASSIFIER_ERROR', 'CONTRACT_FAILURE'], mode='wrapper', matcher_action=action,
            error='ANY_CONTRACT_ERROR' if action in ['empty', 'contract_error'] else None,
            expected=dict(decision='NEED_FALLBACK', route=None, reason_code='CLASSIFICATION_ERROR'))
    for config in [1, 'true', None]:
        for mode in ['function', 'wrapper']:
            add('Invalid configuration', ['CONFIGURATION'], mode=mode, diagnostic=config, error='ANY_CONTRACT_ERROR')
    add('Scope outranks broken classification', ['CLARIFICATION_PRIORITY'], scope={'company_ticker': None},
        ranking={}, expected=missing)
    return cases


def run_policy_case(case):
    from src.retrieval_orchestration.intent_routing import IntentClassificationContractError, IntentRoutingPolicy, decide_intent_route
    class Matcher:
        calls = 0
        def match(self, question, **kwargs):
            self.calls += 1
            action = case.get('matcher_action')
            if action == 'timeout': raise TimeoutError('fixture timeout')
            if action == 'technical_error': raise RuntimeError('fixture technical error')
            if action == 'contract_error': raise IntentClassificationContractError('UPSTREAM_CONTRACT_ERROR')
            return None if action == 'empty' else deepcopy(case['ranking'])
    matcher = Matcher(); started = time.perf_counter(); actual = None; error = None
    try:
        options = dict(query_components=case.get('components'), query_components_confirmed=case.get('confirmed', False))
        if case.get('mode') == 'wrapper':
            actual = IntentRoutingPolicy(matcher, allow_direct_search=case.get('diagnostic', False)).decide(
                case['question'], **case['scope'], **options)
        else:
            actual = decide_intent_route(deepcopy(case['ranking']), question=case['question'], **case['scope'],
                                         allow_direct_search=case.get('diagnostic', False), **options)
        actual['_matcher_calls'] = matcher.calls
        mismatches = check_expected(actual, case['expected'])
        if 'PRIVACY' in case['requirement_ids'] and 'SECRET' in repr(actual):
            mismatches.append('Unrelated ranking history leaked into the fallback handoff')
        if case['expected_error']: mismatches.append('Expected a contract error but returned normally')
    except IntentClassificationContractError as exc:
        error = exc.code
        mismatches = [] if case['expected_error'] in ['ANY_CONTRACT_ERROR', error] else ['Unexpected contract error: '+error]
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        mismatches = ['Unexpected non-contract exception: '+error]
    return dict(test_id=case['test_id'], question=case['question'], category=case['category'],
                requirement_ids=case['requirement_ids'], expected=case['expected'], expected_error=case['expected_error'],
                actual=actual, actual_error=error, passed=not mismatches, mismatches=mismatches,
                elapsed_ms=(time.perf_counter()-started)*1000, input_kind='CONTROLLED_FIXTURE')


def jsonable(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'invalid_fixture_number': repr(value)}
    if isinstance(value, dict): return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [jsonable(v) for v in value]
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(jsonable(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                          encoding='utf-8', newline='\n')


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def normalized_text(text):
    plain = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
                    if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', plain).strip()


def business_route(label, components=()):
    if label != 'MIXED': return ROUTES.get(label)
    if len(components) < 2 or len(set(components)) != len(components) or any(c not in ROUTES for c in components):
        return None
    routes = {ROUTES[c] for c in components}
    return 'BOTH' if len(routes) > 1 or 'BOTH' in routes else next(iter(routes))


def assess_prediction(case, label, components, route):
    if case['expected_decision'] == 'ASK_CLARIFICATION' or case['expected_label'] is None:
        return dict(label_pass=None, component_pass=None, candidate_route_pass=None, mismatches=[])
    expected_components = case['expected_components']
    checks = dict(label_pass=label == case['expected_label'],
                  component_pass=(sorted(components) == sorted(expected_components)),
                  candidate_route_pass=route == case['expected_business_route'])
    errors = []
    for key, expected, actual in [('label_pass', case['expected_label'], label),
            ('component_pass', expected_components, components),
            ('candidate_route_pass', case['expected_business_route'], route)]:
        if not checks[key]: errors.append(f'{key}: expected={expected!r}, actual={actual!r}')
    return checks | dict(mismatches=errors)


def include_failure(row):
    return not row['passed']


def question_status(row):
    if not row['passed']: return 'FAIL'
    return 'OBSERVATION' if row['dataset'] == 'REGRESSION_032' and row['expected_label'] is None else 'PASS'


def load_business():
    cases = read_rows(BUSINESS)
    assert len(cases) == len({c['test_id'] for c in cases}) == 80
    clear = [c for c in cases if c['expected_decision'] == 'NEED_FALLBACK']
    assert Counter(c['expected_label'] for c in clear) == Counter({label: 10 for label in LABELS})
    for case in clear:
        assert business_route(case['expected_label'], case['expected_components']) == case['expected_business_route']
    previous = {}
    for path in [ROOT/'docs/sprint5/intent-dataset-v1/library.jsonl',
                 ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl',
                 ROOT/'outputs/s5_intent_scorer_20261112/training.jsonl']:
        for row in read_rows(path): previous[normalized_text(row.get('text', row.get('question', '')))] = str(path)
    for path in [ROOT/'outputs/s5_intent_scorer_20261112/evaluation-cases.json',
                 ROOT/'outputs/s5_intent_review2_20261112/run03/cases.json']:
        for row in json.loads(path.read_text(encoding='utf-8')):
            previous[normalized_text(row.get('text', row.get('question', '')))] = str(path)
    overlaps = [c['test_id'] for c in cases if normalized_text(c['question']) in previous]
    assert not overlaps, f'New question overlaps known datasets: {overlaps}'
    assert len({normalized_text(c['question']) for c in cases}) == 80
    return cases


def regression_cases():
    # These scopes are explicit evaluator fixtures, not a benchmark of a company/period resolver.
    symbols = {'FPT','VCB','TCB','MBB','BID','HPG','PNJ','MWG','VNM','REE','ACB','GMD','DGC','SSI','VHC','DPM','VRE','SAB'}
    cases = []
    for row in read_rows(ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl'):
        found = [t for t in re.findall(r'\b[A-Z][A-Z0-9]{2,4}\b', row['text']) if t in symbols]
        company = found[0] if found else None
        # All 56 texts are ranked offline; scope fixtures do not manufacture a company.
        cases.append(dict(test_id=row['id'], question=row['text'], expected_label=row['intent_label'],
            expected_components=row['component_intents'], expected_business_route=business_route(
                row['intent_label'], row['component_intents']), scope=dict(company_ticker=company, period=None,
                company_required=False), expected_decision='NEED_FALLBACK', expected_reason='DIRECT_SEARCH_DISABLED',
            category='Hồi quy 03.2 / '+row['annotation_status'], oracle_rationale=row['annotation_note'],
            requirement_ids=['REGRESSION_032']))
    return cases


def measured_policy(output):
    from coverage import Coverage
    cov = Coverage(branch=True, source_pkgs=['src.retrieval_orchestration.intent_routing'],
                   data_file=str(output/'.coverage'))
    cov.start()
    rows = [run_policy_case(case) for case in policy_cases()]
    cov.stop(); cov.save(); cov.json_report(outfile=str(output/'coverage.json'))
    cov.html_report(directory=str(output/'coverage-html'))
    detail = next(iter(json.loads((output/'coverage.json').read_text(encoding='utf-8'))['files'].values()))
    summary = detail['summary']
    metrics = dict(line_coverage=summary['covered_lines']/summary['num_statements'],
                   branch_coverage=summary['covered_branches']/summary['num_branches'],
                   policy_success=sum(r['passed'] for r in rows)/len(rows))
    return rows, detail, metrics


def evaluate_questions(new_cases, old_cases, library, params, model, output):
    import numpy as np
    from src.documents.embeddings import EmbeddingService
    from src.retrieval_orchestration.intent_matching import IntentMatcher
    from src.retrieval_orchestration.intent_scoring import classifier_probabilities, rankings
    from src.retrieval_orchestration.intent_semantic_requests import requests, resolve_objectives
    from src.retrieval_orchestration.intent_routing import IntentRoutingPolicy
    questions = [c['question'] for c in new_cases if c['expected_decision'] != 'ASK_CLARIFICATION']
    questions += [c['question'] for c in old_cases]
    texts = sorted(set(questions) | {part for q in questions for part in requests(q)})
    write_json(output/'embedded-texts.json', texts)
    print(f'Embedding {len(texts)} frozen texts with real pinned BGE-M3; no fit/calibration.', flush=True)
    encoder = EmbeddingService(model['name'], revision=model['revision'], device='cpu', batch_size=4)
    matcher = IntentMatcher(library, encoder)
    started = time.perf_counter()
    vectors = np.asarray(encoder.embed_texts(texts), dtype=np.float32)
    elapsed = time.perf_counter()-started
    assert vectors.shape == (len(texts), 1024) and np.isfinite(vectors).all()
    np.save(output/'embedded-vectors.npy', vectors, allow_pickle=False)
    lookup = dict(zip(texts, vectors))
    class FrozenMatcher:
        def __init__(self, value): self.value, self.calls = value, 0
        def match(self, question, **kwargs): self.calls += 1; return deepcopy(self.value)
    results = []
    for dataset, cases in [('NEW', new_cases), ('REGRESSION_032', old_cases)]:
        for case in cases:
            q = case['question']; spans = requests(q)
            cos_rank = class_rank = resolved = None
            if q in lookup:
                cos_rank = matcher._rank(q, lookup[q], 7, 5)
                base = classifier_probabilities(np.stack([lookup[q]]), params['coefficients'], params['intercepts'])[0]
                class_rank = rankings([q], [base], LABELS, 'intent-linear-v1',
                                      'CLASSIFIER_PROBABILITY_UNCALIBRATED', model)[0]
                parts = classifier_probabilities(np.stack([lookup[s] for s in spans]),
                    params['coefficients'], params['intercepts']) if spans != [q] else []
                resolved = resolve_objectives(base, parts, LABELS, spans)
            cos_matcher = FrozenMatcher(cos_rank)
            actual = IntentRoutingPolicy(cos_matcher).decide(q, **case['scope'])
            expected = dict(decision=case['expected_decision'], route=None, reason_code=case['expected_reason'])
            mismatch = check_expected(actual, expected)
            if case['expected_decision'] == 'ASK_CLARIFICATION' and cos_matcher.calls:
                mismatch.append('Scope gate called matcher')
            v7_actual = diagnostic = None
            candidate = predicted = None
            if resolved:
                v7_actual = IntentRoutingPolicy(FrozenMatcher(dict(base_ranking=class_rank, resolution=resolved))).decide(q, **case['scope'])
                predicted = resolved['intent_label']
                components = resolved.get('component_labels', [])
                verified = (resolved['reason'] == 'TWO_EXPLICIT_REQUEST_TYPES' and not resolved.get('unresolved_requests'))
                candidate = business_route(predicted, components if verified else [])
                diagnostic = IntentRoutingPolicy(FrozenMatcher(cos_rank), allow_direct_search=True).decide(q,
                    **case['scope'], query_components=components, query_components_confirmed=verified)
                reason = ('LABEL_DISAGREEMENT' if class_rank['groups'][0]['intent_label'] != predicted
                          else 'UNCALIBRATED_CLASSIFICATION')
                mismatch.extend('V7: '+message for message in check_expected(v7_actual,
                    dict(decision=case['expected_decision'], route=None, need_fallback=True,
                         reason_code=reason, scope=actual['scope'],
                         **{'classification_evidence.resolution.intent_label': predicted,
                            'classification_evidence.resolution.confidence': None,
                            'classification_evidence.resolution.component_labels': components})))
            assessment = assess_prediction(case, predicted, resolved.get('component_labels', []) if resolved else [], candidate)
            policy_pass = not mismatch
            mismatch.extend(assessment.pop('mismatches'))
            results.append(dict(case, dataset=dataset, input_kind=('SCOPE_GATE_NO_MODEL' if q not in lookup
                else 'REAL_BGE_M3_AND_FROZEN_V7'),
                actual_label=predicted, actual_components=resolved.get('component_labels', []) if resolved else [],
                candidate_route=candidate, actual_decision=actual['decision'], actual_route=actual['route'],
                reason_code=actual['reason_code'], v7_reason_code=v7_actual['reason_code'] if v7_actual else None,
                **assessment, policy_pass=policy_pass, passed=not mismatch, v7_handoff=v7_actual,
                matcher_calls=cos_matcher.calls, diagnostic=diagnostic, cosine_ranking=cos_rank,
                classifier_ranking=class_rank, resolution=resolved, mismatches=mismatch))
    return results, dict(embedded_texts=len(texts), batch_embedding_seconds=elapsed, actual_batch_size=4, device='cpu',
                        per_request_latency_measured=False, no_refit=True, fresh_model_inference=True)


def write_workbook(path, summary, questions, policy_rows, coverage_detail, behavior):
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(); wb.remove(wb.active)
    def sheet(name, headers, values, widths):
        ws = wb.create_sheet(name); ws.append(headers)
        for values_row in values:
            ws.append([safe_cell(v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)) for v in values_row])
        ws.freeze_panes = 'C2' if len(headers) > 5 else 'A2'
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_view.zoomScale = 85
        ws.row_dimensions[1].height = 34
        for cell in ws[1]:
            cell.fill = PatternFill('solid', fgColor='14656E'); cell.font = Font(name='Calibri', color='FFFFFF', bold=True)
            cell.alignment = Alignment(wrap_text=True, vertical='center')
        for row in ws.iter_rows(min_row=2):
            ws.row_dimensions[row[0].row].height = 58 if len(headers) > 5 else 30
            for cell in row:
                cell.font = Font(name='Calibri', size=11)
                cell.alignment = Alignment(wrap_text=True, vertical='top')
                if cell.row % 2 == 0: cell.fill = PatternFill('solid', fgColor='EFF6F7')
                if cell.value in ('PASS', 'FAIL'):
                    cell.font = Font(name='Calibri', bold=True, color='18713C' if cell.value == 'PASS' else 'B42318')
        for index, width in enumerate(widths, 1): ws.column_dimensions[get_column_letter(index)].width = width
        ws.print_options.horizontalCentered = True; ws.print_title_rows = '1:1'
        return ws
    overview = [['Kết luận', summary['verdict']['status'], 'Tất cả cổng đều phải >=90%'],
        ['Ngưỡng', .9, 'Không sửa gold/model/ngưỡng sau khi xem kết quả'],
        ['Chế độ thật của 04.2', 'FALLBACK-ONLY', 'NEED_FALLBACK không phải tìm kiếm thành công'],
        ['Loại điểm', 'Cosine và probability ghi riêng', 'Probability chưa hiệu chỉnh, V7 confidence=null'],
        ['Model', summary['model']['name'], summary['model']['revision']],
        ['Câu mới', 80, '70 đủ scope +10 hỏi lại; soạn không đọc implementation'],
        ['Hồi quy 03.2', 56, '47 có nhãn; 9 null chỉ quan sát, bộ này đã được xem trong phát triển'],
        ['Phạm vi', 'Policy và model offline', 'Chưa gọi AI fallback07.2, retrieval, DB hoặc UI'],
        ['Log gốc', str(path.parent/'results.json'), 'Có đầy đủ payload và hash trong method.json'],
        ['Kỳ vọng trước inference', summary['business_sha256'], 'Không có trùng chuẩn hóa với bộ cũ đã kiểm']]
    for key, value in summary['metrics'].items(): overview.append([key, value, 'PASS' if value is not None and value >= .9 else 'FAIL'])
    ws = sheet('Tong_quan', ['Chỉ mục', 'Giá trị', 'Giải thích / kết quả'], overview, [35,55,95])
    for row in ws.iter_rows(min_row=12):
        if isinstance(row[1].value, float): row[1].number_format = '0.00%'
    headers = ['Test_ID','Câu hỏi','Nhãn kỳ vọng','Nhãn V7 thật','Nhánh nghiệp vụ kỳ vọng','Nhánh đề xuất V7',
        'Decision kỳ vọng','Decision04.2 thật','Route04.2 thật','Lý do kỳ vọng','Lý do04.2','Lý doV7',
        'Thành phần kỳ vọng','Thành phần V7','Thành phần đúng?', 'Cosine top1:nhãn','Cosine top1',
        'Cosine top2','Cosine gap','Classifier top1:nhãn','Probability top1 (chưa hiệu chỉnh)',
        'Kết quả','Giải thích gold / lỗi','Scope fixture']
    for dataset, name in [('NEW','Cau_hoi_moi'),('REGRESSION_032','Hoi_quy_03_2')]:
        values = []
        for r in questions:
            if r['dataset'] != dataset: continue
            cos = (r['cosine_ranking'] or {}).get('groups', [])
            clf = (r['classifier_ranking'] or {}).get('groups', [])
            values.append([r['test_id'],r['question'],r['expected_label'],r['actual_label'],r['expected_business_route'],
                r['candidate_route'],r['expected_decision'],r['actual_decision'],r['actual_route'],r['expected_reason'],
                r['reason_code'],r['v7_reason_code'],r['expected_components'],r['actual_components'],r.get('component_pass'),
                cos[0]['intent_label'] if cos else None,cos[0]['score'] if cos else None,
                cos[1]['score'] if cos else None,cos[0]['score']-cos[1]['score'] if cos else None,
                clf[0]['intent_label'] if clf else None,clf[0]['score'] if clf else None,question_status(r),
                r['oracle_rationale']+'; '+'; '.join(r['mismatches']),r['scope']])
        sheet(name, headers, values, [20,80,23,23,20,20,24,24,20,32,32,38,40,40,20,22,18,18,18,22,25,16,90,50])
    values = []
    for r in policy_rows:
        a = r['actual'] or {}
        values.append([r['test_id'],r['category'],str(r['question'])[:400],r['expected'],r['expected_error'],
            a.get('decision'),a.get('route'),a.get('reason_code') or r['actual_error'],a.get('top_1_score'),
            a.get('top_2_score'),a.get('score_gap'),'PASS' if r['passed'] else 'FAIL',r['requirement_ids'],r['mismatches']])
    sheet('Policy_04_2',['Test_ID','Ca contract (điểm fixture)','Câu hỏi','Kỳ vọng','Lỗi kỳ vọng','Decision thật',
        'Route thật','Lý do / lỗi thật','Top1 fixture','Top2 fixture','Gap fixture','Kết quả','Nhóm yêu cầu','Sai lệch'],
        values,[20,46,65,65,26,25,16,42,20,20,20,16,55,70])
    values = [[k,summary['metrics'][k],'>=90%', 'PASS' if summary['metrics'][k]>=.9 else 'FAIL']
              for k in ['line_coverage','branch_coverage','behavior_coverage']]
    values += [['Missing lines',coverage_detail['missing_lines'],'Không xóa/pragma để tăng coverage','Thông tin'],
               ['Missing branches',coverage_detail['missing_branches'],'Chỉ module04.2, không cộng suite cũ','Thông tin']]
    values += [[key,len(ids),', '.join(ids[:12]),'EXECUTED' if ids else 'NOT_COVERED'] for key,ids in behavior.items()]
    sheet('Coverage',['Chỉ mục / yêu cầu','Giá trị / số ca','Bằng chứng / test ID','Trạng thái'],values,[38,40,100,24])
    failures = []
    for r in questions:
        if not include_failure(r): continue
        failures.append([r['test_id'],r['dataset'],r['question'],r['expected_label'],r['actual_label'],
            r['expected_business_route'],r['candidate_route'],r['reason_code'],
            'Model/nhãn/thành phần' if r['policy_pass'] else 'Policy/scope',
            'Nhân cần đối chiếu model/mẫu' if r['policy_pass'] else 'Huyền cần đối chiếu contract/scope',
            r['mismatches'],str(path.parent/'results.json')])
    for r in policy_rows:
        if not r['passed']: failures.append([r['test_id'],'POLICY',str(r['question'])[:400],str(r['expected']),
            str(r['actual']),None,None,r['actual_error'],'Policy/contract','Huyền cần kiểm chứng',
            r['mismatches'],str(path.parent/'policy-results.json')])
    sheet('Ca_sai',['Test_ID','Bộ','Câu hỏi','Nhãn/kỳ vọng','Thực tế','Nhánh kỳ vọng','Nhánh đề xuất',
        'Lý do','Nhóm cần điều tra','Đầu mối đối chiếu','Sai lệch chi tiết','Log'],failures,[20,24,85,26,26,20,20,38,30,42,95,80])
    wb.save(path)
    opened = load_workbook(path)
    assert len(opened.sheetnames) == 6 and opened['Cau_hoi_moi'].max_row == 81
    assert all(cell.data_type != 'f' for ws in opened for row in ws for cell in row)
    opened.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/s5_wbs043_20261113/run01')
    args = parser.parse_args(); output = args.output.resolve()
    if output.exists(): raise FileExistsError('Keep prior evidence; choose a new --output')
    import numpy as np
    from src.retrieval_orchestration.intent_library import load_library
    new = load_business(); old = regression_cases()
    libdir = ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    fit = ROOT/json.loads((ROOT/'outputs/s5_intent_scorer_20261112/fit-location.json').read_text(encoding='utf-8'))['output']
    library = load_library(libdir)
    fitted = json.loads((fit/'summary.json').read_text(encoding='utf-8'))
    assert fitted['labels'] == LABELS
    params = np.load(fit/'parameters.npz', allow_pickle=False)
    watched = [Path(__file__), BUSINESS, POLICY, ROOT/'docs/sprint5/intent-labels.v1.json',
        ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl',fit/'parameters.npz',fit/'summary.json']
    watched += list((ROOT/'backend/src/retrieval_orchestration').glob('intent_*.py'))
    watched += [libdir/name for name in ['manifest.json','library.jsonl','vectors.npy','label-schema.json','dataset-manifest.json']]
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    output.mkdir(parents=True)
    write_json(output/'business-frozen.json',new); write_json(output/'policy-frozen.json',policy_cases())
    write_json(output/'method.json',dict(frozen_before_inference=True,threshold=.9,acceptance_gates=GATES,
        behavior_requirements=REQUIREMENTS,source_hashes=hashes,model=library.manifest['model'],
        library_version=library.manifest['library_version'],gold_authored_without_implementation=True,
        authoring_context='Separate context read label contract only; no runtime or prior test/model output.',
        human_blind_evaluation=False,regression_set_previously_seen=True,scope_fixtures_not_resolver_benchmark=True,
        runtime_policy_changed=False,model_or_examples_changed=False,provider_called=False,ui_tested=False,
        encoder_device='cpu',encoder_batch_size=4,
        python=sys.version,packages={p:importlib.metadata.version(p) for p in ['coverage','numpy','openpyxl','torch','sentence-transformers']}))
    policy_rows,detail,metrics = measured_policy(output)
    print(f'Policy: {sum(r["passed"] for r in policy_rows)}/{len(policy_rows)}; coverage {metrics}',flush=True)
    write_json(output/'policy-results.json',policy_rows)
    try:
        questions, inference = evaluate_questions(new,old,library,params,library.manifest['model'],output)
    except Exception as exc:
        write_json(output/'inference-error.json',dict(error_type=type(exc).__name__,message=str(exc)))
        questions=[]; inference=dict(error_type=type(exc).__name__,fresh_model_inference=False)
    write_json(output/'results.json',questions)
    fresh = [r for r in questions if r['dataset']=='NEW']
    labeled = [r for r in fresh if r['label_pass'] is not None]
    regression = [r for r in questions if r['dataset']=='REGRESSION_032' and r['expected_label'] is not None]
    behavior = {key:[] for key in REQUIREMENTS}
    for row in policy_rows+questions:
        for key in row['requirement_ids']:
            if key in behavior: behavior[key].append(row['test_id'])
    ratio = lambda rows,key:sum(r[key] is True for r in rows)/len(rows) if rows else None
    metrics.update(behavior_coverage=sum(bool(ids) for ids in behavior.values())/len(behavior),
        new_question_success=ratio(fresh,'passed') if len(fresh)==80 else None,
        regression_success=ratio(regression,'passed') if len(regression)==47 else None,
        new_label_accuracy=ratio(labeled,'label_pass') if len(labeled)==70 else None,
        new_candidate_route_accuracy=ratio(labeled,'candidate_route_pass') if len(labeled)==70 else None)
    unchanged = all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==value for path,value in hashes.items())
    if not unchanged: raise RuntimeError('Inputs changed; reject evaluation')
    summary = dict(task='S5-WBS04.3',created_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
        model=library.manifest['model'],metrics=metrics,verdict=acceptance_verdict(metrics),inference=inference,
        counts=dict(policy=len(policy_rows),new=len(fresh),new_labeled=len(labeled),regression_labeled=len(regression)),
        business_sha256=hashes[str(BUSINESS.relative_to(ROOT))],inputs_unchanged=unchanged,
        policy_default='FALLBACK_ONLY',actual_searches_claimed=False,provider_called=False,ui_tested=False)
    write_json(output/'summary.json',summary);write_json(output/'behavior-coverage.json',behavior)
    if questions:
        write_workbook(output/'S5_WBS04_3_ROUTER_ACCEPTANCE_20261113.xlsx',summary,questions,policy_rows,detail,behavior)
    else:
        # Export every unavailable question explicitly instead of dropping failed execution from Excel.
        unavailable=[dict(c,dataset=dataset,actual_label=None,actual_components=[],candidate_route=None,
            actual_decision='NOT_RUN',actual_route=None,reason_code='INFERENCE_ERROR',v7_reason_code=None,
            cosine_ranking=None,classifier_ranking=None,passed=False,policy_pass=False,
            mismatches=['Real model could not run; see inference-error.json'])
            for dataset,cases in [('NEW',new),('REGRESSION_032',old)] for c in cases]
        write_workbook(output/'S5_WBS04_3_ROUTER_ACCEPTANCE_20261113.xlsx',summary,unavailable,policy_rows,detail,behavior)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return 0 if summary['verdict']['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
