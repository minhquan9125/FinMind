"""Reconstruct numeric-guard evidence without model loading, fitting or DB."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_numeric_requests import requests, resolve_objectives
from run_s5_intent_numeric import OUT, SCORER, inputs, vectors
from run_s5_intent_reviewfix import read, write


def main():
    for name, digest in read(OUT / 'method.json')['source_hashes'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    cases, sources = inputs()
    assert cases == read(OUT / 'cases.json')
    lookup, _ = vectors()
    new_texts = read(OUT / 'new-texts.json')
    new_vectors = np.load(OUT / 'new-vectors.npy', allow_pickle=False)
    assert new_vectors.shape == (len(new_texts), 1024) and np.isfinite(new_vectors).all()
    assert np.allclose(np.linalg.norm(new_vectors, axis=1), 1, atol=1e-4, rtol=0)
    lookup.update(zip(new_texts, new_vectors))
    fit = ROOT / read(SCORER / 'fit-location.json')['output']
    params = np.load(fit / 'parameters.npz', allow_pickle=False)
    labels = read(fit / 'summary.json')['labels']
    results, summary = read(OUT / 'results.json'), read(OUT / 'summary.json')
    rows = {(group, row['id']): row for group, group_rows in results.items() for row in group_rows}
    spans = read(OUT / 'parts.json')
    assert len(rows) == len(cases) == len(spans) == 313

    def probability(text):
        logits = np.einsum('ij,j->i', params['coefficients'], lookup[text].astype(np.float64)) + params['intercepts']
        exponential = np.exp(logits - logits.max())
        return exponential / exponential.sum()

    maximum = 0.0
    correct = {group: 0 for group in results}
    fixed, regressed = [], []
    for case, parts in zip(cases, spans):
        group = case['evaluation_set']
        row = rows[(group, case['id'])]
        assert (row['question'], row['gold']) == (case['question'], case['gold'])
        assert requests(case['question']) == parts == row['parts']
        prior = sources.get((group, case['id']))
        if prior:
            ref = row['base_ranking_ref']
            assert ref == dict(path='outputs/s5_intent_reviewfix_20261112/run02/results.json', evaluation_set=group, id=case['id'])
            ranking = prior['base_ranking']
        else:
            ranking = row['base_ranking']
        base = probability(row['question'])
        order = sorted(labels, key=lambda label: (-base[labels.index(label)], label))
        assert order == [g['intent_label'] for g in ranking['groups']]
        for item in ranking['groups']:
            maximum = max(maximum, abs(base[labels.index(item['intent_label'])] - item['score']))
        component = [] if parts == [row['question']] else [probability(text) for text in parts]
        assert np.allclose(component, row['component_probabilities'], atol=1e-10, rtol=0)
        exact = [next(g['score'] for g in ranking['groups'] if g['intent_label'] == label) for label in labels]
        decision = resolve_objectives(exact, row['component_probabilities'], labels, parts)
        assert decision == row['resolution'] and decision['intent_label'] == row['final_label']
        assert decision['confidence'] is None and decision['runtime_enabled'] is False
        correct[group] += bool(row['gold'] and row['gold'] == row['final_label'])
        if prior and row['gold']:
            before, after = prior['final_label'] == row['gold'], row['final_label'] == row['gold']
            if not before and after: fixed.append(case['id'])
            if before and not after: regressed.append(case['id'])
    assert maximum < 1e-10
    assert correct == {k: v['correct'] for k, v in summary['metrics'].items()}
    assert not regressed and summary['passes_gate']
    proof = dict(status='PASS', decisions_replayed=313, max_probability_difference=maximum,
                 fixed_against_v4=fixed, regressed_against_v4=regressed,
                 raw_rankings_preserved_by_reference=True, source_hashes_unchanged=True,
                 no_refit=True, confidence=None, router_integrated=False,
                 semantic_rule_replay_is_not_independent_label_review=True)
    write(OUT / 'audit.json', proof)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
