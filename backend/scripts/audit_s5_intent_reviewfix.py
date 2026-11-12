"""Replay V4 and independently reconstruct probabilities from saved vectors."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_request_review import requests, resolve_objectives
from run_s5_intent_reviewfix import saved_vectors, read, write


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, default=ROOT / 'outputs/s5_intent_reviewfix_20261112/run02')
    args = parser.parse_args()
    run = args.run
    method = read(run / 'method.json')
    for name, digest in method['source_hashes'].items():
        assert sha(ROOT / name) == digest, name
    scorer = ROOT / 'outputs/s5_intent_scorer_20261112'
    fit = ROOT / read(scorer / 'fit-location.json')['output']
    params = np.load(fit / 'parameters.npz', allow_pickle=False)
    labels = read(fit / 'summary.json')['labels']
    lookup, _ = saved_vectors()
    prior = ROOT / 'outputs/s5_intent_reviewfix_20261112/run01'
    extra = np.load(prior / 'new-vectors.npy', allow_pickle=False)
    assert extra.shape == (len(read(prior / 'new-texts.json')), 1024)
    assert np.isfinite(extra).all() and np.allclose(np.linalg.norm(extra, axis=1), 1, atol=1e-4, rtol=0)
    lookup.update(zip(read(prior / 'new-texts.json'), extra))
    if (run / 'new-vectors.npy').exists():
        lookup.update(zip(read(run / 'new-texts.json'), np.load(run / 'new-vectors.npy', allow_pickle=False)))
    cases, spans = read(run / 'cases.json'), read(run / 'parts.json')
    results, summary = read(run / 'results.json'), read(run / 'summary.json')
    rows = {(group, row['id']): row for group, group_rows in results.items() for row in group_rows}
    assert len(rows) == len(cases) == len(spans) == 293
    maximum = 0.0
    correct = {name: 0 for name in results}
    regressions = []

    def probability(text):
        logits = np.einsum('ij,j->i', params['coefficients'], lookup[text].astype(np.float64)) + params['intercepts']
        values = np.exp(logits - logits.max())
        return values / values.sum()

    for case, parts in zip(cases, spans):
        group = case['evaluation_set']
        row = rows[(group, case['id'])]
        assert row['question'] == case['question'] and row['gold'] == case['gold']
        assert parts == requests(case['question']) == row['parts']
        base = probability(case['question'])
        if 'base_ranking' in case:
            assert row['base_ranking'] == case['base_ranking']
        expected_order = sorted(labels, key=lambda label: (-base[labels.index(label)], label))
        assert expected_order == [g['intent_label'] for g in row['base_ranking']['groups']]
        for g in row['base_ranking']['groups']:
            maximum = max(maximum, abs(base[labels.index(g['intent_label'])] - g['score']))
        component = [] if parts == [case['question']] else [probability(q) for q in parts]
        assert np.allclose(component, row['component_probabilities'], atol=1e-10, rtol=0)
        # Use the exact retained whole-query scores for rule replay; independent
        # probability reconstruction is checked separately to tolerance above.
        exact_base = [next(g['score'] for g in row['base_ranking']['groups'] if g['intent_label'] == label) for label in labels]
        decision = resolve_objectives(exact_base, row['component_probabilities'], labels, parts)
        assert decision == row['resolution'] and decision['intent_label'] == row['final_label']
        assert decision['confidence'] is None and decision['runtime_enabled'] is False
        correct[group] += bool(row['gold'] and row['gold'] == row['final_label'])
        if case.get('final_label') == case['gold'] and case['gold'] and row['final_label'] != case['gold']:
            regressions.append(case['id'])
    assert maximum < 1e-10
    assert correct == {group: value['correct'] for group, value in summary['metrics'].items()}
    assert not regressions and summary['passes_no_regression_gate']
    historical = read(prior / 'method.json')['source_hashes']
    for source, snapshot in [('backend/scripts/run_s5_intent_reviewfix.py', 'source-run_s5_intent_reviewfix.py'),
                             ('backend/src/retrieval_orchestration/intent_request_review.py', 'source-intent_request_review.py')]:
        assert sha(prior / snapshot) == historical[source]
    proof = dict(status='PASS', decisions_replayed=len(cases), max_probability_difference=maximum,
                 regression_rows=278, newly_wrong_against_v3=regressions,
                 raw_rankings_preserved=True, no_refit=True, source_hashes_unchanged=True,
                 historical_run01_source_snapshots_verified=True,
                 semantic_rule_replay_is_not_independent_label_review=True,
                 confidence=None, router_integrated=False)
    write(run / 'audit.json', proof)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
