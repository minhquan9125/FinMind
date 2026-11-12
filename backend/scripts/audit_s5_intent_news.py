"""Independently recompute saved classifier probabilities and replay decisions."""
import hashlib
import json

import numpy as np

from run_s5_intent_news import ROOT, OUT, SCORER, inputs, vectors, raw_ranking, requests, resolve_objectives
from run_s5_intent_reviewfix import read, write
from run_s5_intent_consensus import stats


def main():
    for name, digest in read(OUT / 'method.json')['source_hashes'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    cases, sources = inputs()
    assert cases == read(OUT / 'cases.json')
    lookup, _ = vectors()
    texts, values = read(OUT / 'new-texts.json'), np.load(OUT / 'new-vectors.npy', allow_pickle=False)
    assert values.shape == (len(texts), 1024) and np.isfinite(values).all()
    assert np.allclose(np.linalg.norm(values, axis=1), 1, atol=1e-4, rtol=0)
    lookup.update(zip(texts, values))
    fit = ROOT / read(SCORER / 'fit-location.json')['output']
    parameters = np.load(fit / 'parameters.npz', allow_pickle=False)
    labels = read(fit / 'summary.json')['labels']
    results, summary = read(OUT / 'results.json'), read(OUT / 'summary.json')
    rows = {(group, r['id']): r for group, group_rows in results.items() for r in group_rows}
    assert len(rows) == len(cases) == 313

    def probability(text):
        logits = np.einsum('ij,j->i', parameters['coefficients'], lookup[text].astype(np.float64)) + parameters['intercepts']
        exps = np.exp(logits - logits.max())
        return exps / exps.sum()

    maximum, fixed, regressed = 0.0, [], []
    for case, saved_parts in zip(cases, read(OUT / 'parts.json')):
        group = case['evaluation_set']
        row, prior = rows[group, case['id']], sources[group, case['id']]
        assert (row['question'], row['gold']) == (case['question'], case['gold'])
        assert requests(row['question']) == saved_parts == row['parts']
        assert row['base_ranking_ref'] == dict(path='outputs/s5_intent_numeric_20261112/run01/results.json', evaluation_set=group, id=case['id'])
        ranking = raw_ranking(row)
        assert ranking == raw_ranking(prior)
        probabilities = probability(row['question'])
        assert sorted(labels, key=lambda label: (-probabilities[labels.index(label)], label)) == [g['intent_label'] for g in ranking['groups']]
        for item in ranking['groups']:
            maximum = max(maximum, abs(probabilities[labels.index(item['intent_label'])] - item['score']))
        component = [] if saved_parts == [row['question']] else [probability(t) for t in saved_parts]
        assert np.allclose(component, row['component_probabilities'], atol=1e-10, rtol=0)
        exact = [next(g['score'] for g in ranking['groups'] if g['intent_label'] == label) for label in labels]
        decision = resolve_objectives(exact, row['component_probabilities'], labels, saved_parts)
        assert decision == row['resolution'] and decision['intent_label'] == row['final_label']
        assert decision['confidence'] is None and decision['runtime_enabled'] is False
        if row['gold']:
            before, after = prior['final_label'] == row['gold'], row['final_label'] == row['gold']
            if not before and after: fixed.append(dict(evaluation_set=group, id=case['id']))
            if before and not after: regressed.append(dict(evaluation_set=group, id=case['id']))
    assert maximum < 1e-10
    assert summary['metrics'] == {group: stats(group_rows, labels) for group, group_rows in results.items()}
    assert summary['fixed'] == fixed and summary['regressed'] == regressed
    assert not regressed and summary['passes_gate']
    proof = dict(status='PASS', decisions_replayed=313, max_probability_difference=maximum,
                 fixed=fixed, regressed=regressed, raw_rankings_unchanged=True,
                 source_hashes_unchanged=True, no_refit=True, confidence=None,
                 router_integrated=False, semantic_rule_replay_is_not_independent_label_review=True)
    write(OUT / 'audit.json', proof)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
