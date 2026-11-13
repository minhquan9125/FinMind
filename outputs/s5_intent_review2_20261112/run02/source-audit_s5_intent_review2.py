"""Replay review2 and independently recompute probabilities from frozen vectors."""
import hashlib
import json

import numpy as np

from run_s5_intent_review2 import ROOT, OUT, SCORER, inputs, vectors, raw_ranking, requests, resolve_objectives, explicit_intent
from run_s5_intent_reviewfix import read, write
from run_s5_intent_consensus import stats


def main():
    for name, digest in read(OUT / 'method.json')['source_hashes'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    cases, sources = inputs()
    spans = read(OUT / 'parts.json')
    assert cases == read(OUT / 'cases.json') and len(cases) == len(spans) == 345
    lookup, _ = vectors()
    texts, values = read(OUT / 'new-texts.json'), np.load(OUT / 'new-vectors.npy', allow_pickle=False)
    assert values.shape == (len(texts), 1024) and np.isfinite(values).all()
    assert np.allclose(np.linalg.norm(values, axis=1), 1, atol=1e-4, rtol=0)
    lookup.update(zip(texts, values))
    fit = ROOT / read(SCORER / 'fit-location.json')['output']
    parameters = np.load(fit / 'parameters.npz', allow_pickle=False)
    labels = read(fit / 'summary.json')['labels']
    results, summary = read(OUT / 'results.json'), read(OUT / 'summary.json')
    rows = {(group, row['id']): row for group, group_rows in results.items() for row in group_rows}
    assert len(rows) == len(cases)

    def probability(text):
        logits = np.einsum('ij,j->i', parameters['coefficients'], lookup[text].astype(np.float64)) + parameters['intercepts']
        exps = np.exp(logits - logits.max())
        return exps / exps.sum()

    maximum, fixed, regressed, guard_failures = 0.0, [], [], []
    for case, parts in zip(cases, spans):
        group = case['evaluation_set']
        row, prior = rows[group, case['id']], sources.get((group, case['id']))
        assert (row['question'], row['gold']) == (case['question'], case['gold'])
        assert requests(row['question']) == parts == row['parts']
        ranking = raw_ranking(row)
        if prior:
            assert ranking == raw_ranking(prior)
            assert row['base_ranking_ref'] == dict(path='outputs/s5_intent_news_20261112/run01/results.json', evaluation_set=group, id=case['id'])
        probabilities = probability(row['question'])
        assert sorted(labels, key=lambda label: (-probabilities[labels.index(label)], label)) == [g['intent_label'] for g in ranking['groups']]
        for item in ranking['groups']:
            maximum = max(maximum, abs(probabilities[labels.index(item['intent_label'])] - item['score']))
        component = [] if parts == [row['question']] else [probability(t) for t in parts]
        assert np.allclose(component, row['component_probabilities'], atol=1e-10, rtol=0)
        exact = [next(g['score'] for g in ranking['groups'] if g['intent_label'] == label) for label in labels]
        decision = resolve_objectives(exact, row['component_probabilities'], labels, parts)
        assert decision == row['resolution'] and decision['intent_label'] == row['final_label']
        assert decision['confidence'] is None and decision['runtime_enabled'] is False
        if prior and case['gold']:
            before, after = prior['final_label'] == case['gold'], row['final_label'] == case['gold']
            if not before and after: fixed.append(dict(evaluation_set=group, id=case['id']))
            if before and not after: regressed.append(dict(evaluation_set=group, id=case['id']))
        if case.get('must_not_force'):
            check = explicit_intent(row['question']) != case['must_not_force']
            assert row['non_forcing_check_passed'] == check
            if not check: guard_failures.append(case['id'])
    assert maximum < 1e-10
    assert summary['metrics'] == {group: stats(group_rows, labels) for group, group_rows in results.items()}
    assert (summary['fixed'], summary['regressed'], summary['non_forcing_failures']) == (fixed, regressed, guard_failures)
    assert not regressed and not guard_failures and summary['passes_gate']
    proof = dict(status='PASS', decisions_replayed=345, max_probability_difference=maximum,
                 fixed=fixed, regressed=regressed, non_forcing_failures=guard_failures,
                 no_refit=True, raw_rankings_unchanged=True, source_hashes_unchanged=True,
                 confidence=None, router_integrated=False,
                 non_forcing_checks_do_not_assert_final_label_accuracy=True)
    write(OUT / 'audit.json', proof)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
