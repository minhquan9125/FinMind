"""Replay frozen v3 evidence and independently recompute final-check scores.

Rule replay checks reproducibility, not independent semantic correctness.
Gold-label agreement is reported separately from numerical reconstruction.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_request_objectives import resolve_objectives
from src.retrieval_orchestration.intent_composition import requests

PARENT = ROOT / 'outputs/s5_intent_composition_20261112'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_sources(method):
    for name, digest in method['source_hashes'].items():
        assert sha(ROOT / name) == digest, name


def main():
    run = PARENT / 'objectives-v3'
    check_sources(read(run / 'method.json'))
    head = read(PARENT / 'results.json')
    cases, traces = read(PARENT / 'cases.json'), read(PARENT / 'traces.json')
    raw = np.asarray(read(PARENT / 'raw-probabilities.json'))
    labels = sorted(head['linear']['development']['metrics']['per_label'])
    results = read(run / 'results.json')
    metrics = read(run / 'summary.json')['metrics']
    count = 0
    for dataset, rows in results.items():
        if dataset == 'previous_new_check':
            source = read(PARENT / 'new-check/results.json')
            by_id = {r['id']: r for r in source}
            inputs = []
            for row in rows:
                old = by_id[row['id']]
                base = [next(g['score'] for g in old['base_ranking']['groups']
                             if g['intent_label'] == label) for label in labels]
                inputs.append((base, old['component_probabilities'], old['parts'],
                               old['base_ranking'], old['question'], old['gold']))
        else:
            source = {r['id']: r for r in head['linear'][dataset]['cases']}
            indices = [i for i, c in enumerate(cases) if c['evaluation_set'] == dataset]
            assert [cases[i]['id'] for i in indices] == [r['id'] for r in rows]
            inputs = [(raw[i], traces[i]['component_probabilities'], traces[i]['parts'],
                       source[cases[i]['id']]['ranking'], cases[i]['text'], cases[i]['intent_label'])
                      for i in indices]
        hits = 0
        for row, (base, parts, texts, ranking, question, gold) in zip(rows, inputs):
            expected = resolve_objectives(base, parts, labels, texts)
            assert row['resolution'] == expected
            assert row['question'] == question and row['gold'] == gold
            assert row['base_ranking'] == ranking
            assert row['final_label'] == expected['intent_label']
            assert expected['confidence'] is None and not expected['runtime_enabled']
            hits += bool(gold and gold == row['final_label'])
            count += 1
        assert hits == metrics[dataset]['correct']

    final = PARENT / 'final-check-v3-utf8'
    check_sources(read(final / 'method.json'))
    scorer = ROOT / 'outputs/s5_intent_scorer_20261112'
    fit = ROOT / read(scorer / 'fit-location.json')['output']
    parameters = np.load(fit / 'parameters.npz', allow_pickle=False)
    texts = read(final / 'texts.json')
    vectors = np.load(final / 'vectors.npy', allow_pickle=False)
    assert vectors.shape == (len(texts), 1024) and np.isfinite(vectors).all()
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4, rtol=0)
    lookup = dict(zip(texts, vectors.astype(np.float64)))

    def probability(text):
        logits = np.einsum('ij,j->i', parameters['coefficients'], lookup[text]) + parameters['intercepts']
        values = np.exp(logits - logits.max())
        return values / values.sum()

    original = ROOT / 'outputs/s5_wbs033_20261110/intent-library-v1'
    old_rows = [json.loads(line) for line in (original / 'library.jsonl').read_text(encoding='utf-8').splitlines()]
    old_vectors = np.load(original / 'vectors.npy', allow_pickle=False).astype(np.float64)
    frozen_cases = read(final / 'cases.json')
    final_rows = read(final / 'results.json')
    assert len(frozen_cases) == len(final_rows) == 28
    correct = dict(original=0, linear=0, consensus=0)
    maximum = 0.0
    regressed = []
    for case, row in zip(frozen_cases, final_rows):
        assert (case['id'], case['text'], case['intent_label']) == (row['id'], row['question'], row['gold'])
        assert requests(case['text']) == row['parts']
        base = probability(row['question'])
        parts = [] if row['parts'] == [row['question']] else [probability(t) for t in row['parts']]
        assert np.allclose(parts, row['component_probabilities'], atol=1e-12, rtol=0)
        expected = resolve_objectives(base, parts, labels, row['parts'])
        assert expected == row['resolution'] and row['final_label'] == expected['intent_label']
        order = sorted(range(len(labels)), key=lambda j: (-base[j], labels[j]))
        assert [labels[j] for j in order] == [g['intent_label'] for g in row['base_ranking']['groups']]
        for group in row['base_ranking']['groups']:
            maximum = max(maximum, abs(base[labels.index(group['intent_label'])] - group['score']))
        q = lookup[row['question']]
        cosines = np.einsum('ij,j->i', old_vectors, q) / (np.linalg.norm(old_vectors, axis=1) * np.linalg.norm(q))
        scores = {label: max(cosines[i] for i, item in enumerate(old_rows) if item['intent_label'] == label)
                  for label in labels}
        original_order = sorted(labels, key=lambda label: (-scores[label], label))
        assert original_order == [g['intent_label'] for g in row['original_ranking']['groups']]
        for group in row['original_ranking']['groups']:
            maximum = max(maximum, abs(scores[group['intent_label']] - group['score']))
        correct['original'] += original_order[0] == row['gold']
        correct['linear'] += labels[order[0]] == row['gold']
        correct['consensus'] += expected['intent_label'] == row['gold']
        if labels[order[0]] == row['gold'] != expected['intent_label']:
            regressed.append(row['id'])
        count += 1
    assert maximum < 1e-10
    summary = read(final / 'summary.json')
    assert correct == {k: v['correct'] for k, v in summary['metrics'].items()}
    assert regressed == summary['linear_correct_to_wrong']

    invalid = PARENT / 'final-check-v3'
    note = read(invalid / 'invalid-input.json')
    producer = invalid / 'producer-script-corrupted.py'
    producer_key = 'backend/scripts/check_s5_intent_objectives_final.py'
    assert sha(producer) == note['producer_snapshot_sha256']
    assert sha(producer) == read(invalid / 'method.json')['source_hashes'][producer_key]
    assert note['status'] == 'INVALID_INPUT_NOT_QUALITY_EVALUATION'
    # The failed run froze exactly the same head/rules as the UTF-8 repair.
    bad_hashes = read(invalid / 'method.json')['source_hashes']
    good_hashes = read(final / 'method.json')['source_hashes']
    for name, digest in bad_hashes.items():
        if name != producer_key:
            assert digest == good_hashes[name] == sha(ROOT / name), name
    proof = dict(status='PASS', decisions_replayed=count, final_check_correct=correct,
                 max_score_difference=maximum, raw_rankings_preserved=True,
                 frozen_sources_unchanged=True, no_refit=True, confidence_not_fabricated=True,
                 invalid_encoding_attempt_retained_and_excluded=True,
                 semantic_rule_replay_is_not_independent_label_review=True)
    (run / 'audit.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
