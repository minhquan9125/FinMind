"""Frozen financial-value guard evaluation; retain raw rankings by reference."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_numeric_requests import requests, resolve_objectives
from src.retrieval_orchestration.intent_scoring import classifier_probabilities, rankings
from run_s5_intent_reviewfix import saved_vectors, read, write
from run_s5_intent_consensus import stats

PARENT = ROOT / 'outputs/s5_intent_reviewfix_20261112'
SCORER = ROOT / 'outputs/s5_intent_scorer_20261112'
OUT = ROOT / 'outputs/s5_intent_numeric_20261112/run01'
PROBES = ROOT / 'docs/sprint5/intent-numeric-probes.json'


def inputs():
    previous = read(PARENT / 'run02/results.json')
    cases, sources = [], {}
    for group, rows in previous.items():
        for row in rows:
            sources[(group, row['id'])] = row
            cases.append(dict(id=row['id'], question=row['question'], gold=row['gold'],
                              evaluation_set=group, prior_label=row['final_label']))
    cases += [dict(row, evaluation_set='additional_checks') for row in read(PROBES)]
    return cases, sources


def vectors():
    lookup, caches = saved_vectors()
    pair = (PARENT / 'run01/new-texts.json', PARENT / 'run01/new-vectors.npy')
    lookup.update(zip(read(pair[0]), np.load(pair[1], allow_pickle=False)))
    return lookup, caches + [pair]


def main():
    if OUT.exists():
        raise FileExistsError('Do not overwrite the frozen evaluation')
    cases, sources = inputs()
    parts = [requests(row['question']) for row in cases]
    lookup, caches = vectors()
    needed = sorted(({row['question'] for row in cases} | {q for spans in parts for q in spans}) - lookup.keys())
    fit = ROOT / read(SCORER / 'fit-location.json')['output']
    params = np.load(fit / 'parameters.npz', allow_pickle=False)
    labels = read(fit / 'summary.json')['labels']
    model = read(SCORER / 'method.json')['model']
    watched = [Path(__file__), PROBES, ROOT / 'docs/sprint5/S5-WBS04.1-numeric-plan.md',
               ROOT / 'backend/src/retrieval_orchestration/intent_numeric_requests.py',
               ROOT / 'backend/src/retrieval_orchestration/intent_request_review.py',
               ROOT / 'docs/sprint5/intent-labels.v1.json', PARENT / 'run02/results.json',
               fit / 'parameters.npz']
    watched += [p for pair in caches for p in pair]
    watched += [SCORER / name for name in ['evaluation-cases.json', 'evaluation-vectors.npy', 'training.jsonl', 'training-vectors.npy']]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    OUT.mkdir(parents=True)
    write(OUT / 'method.json', dict(status='FROZEN_BEFORE_EVALUATION', source_hashes=hashes,
          model=model, no_fit=True, existing_cases_seen=True, review_probes=15,
          regression_rows=293, additional_rows=20, independent_blind_test=False,
          confidence=None, runtime_enabled=False))
    write(OUT / 'cases.json', cases)
    write(OUT / 'parts.json', parts)
    write(OUT / 'new-texts.json', needed)
    if needed:
        from src.documents.embeddings import get_embedding_service
        encoder = get_embedding_service()
        assert (encoder.model_name, encoder.revision) == (model['name'], model['revision'])
        print(f'Embedding {len(needed)} new texts for 20 fixed checks; no refit.', flush=True)
        new = np.asarray(encoder.embed_texts(needed), dtype=np.float32)
        assert new.shape == (len(needed), 1024) and np.isfinite(new).all()
        np.save(OUT / 'new-vectors.npy', new, allow_pickle=False)
        lookup.update(zip(needed, new))
    results, changes = {}, {}
    for case, spans in zip(cases, parts):
        group, question = case['evaluation_set'], case['question']
        prior = sources.get((group, case['id']))
        if prior:
            ranking = prior['base_ranking']
            base = [next(g['score'] for g in ranking['groups'] if g['intent_label'] == label) for label in labels]
        else:
            base = classifier_probabilities(np.stack([lookup[question]]), params['coefficients'], params['intercepts'])[0]
            ranking = rankings([question], [base], labels, 'intent-linear-v1', 'CLASSIFIER_PROBABILITY_UNCALIBRATED', model)[0]
        component = classifier_probabilities(np.stack([lookup[q] for q in spans]), params['coefficients'], params['intercepts']) if spans != [question] else []
        decision = resolve_objectives(base, component, labels, spans)
        row = dict(id=case['id'], question=question, gold=case['gold'], parts=spans,
                   prior_label=case.get('prior_label'), final_label=decision['intent_label'],
                   resolution=decision, component_probabilities=np.asarray(component).tolist())
        if prior:
            row['base_ranking_ref'] = dict(path='outputs/s5_intent_reviewfix_20261112/run02/results.json',
                                          evaluation_set=group, id=case['id'])
            transition = changes.setdefault(group, dict(fixed=[], regressed=[]))
            if case['gold']:
                before, after = prior['final_label'] == case['gold'], row['final_label'] == case['gold']
                if not before and after: transition['fixed'].append(case['id'])
                if before and not after: transition['regressed'].append(case['id'])
        else:
            row['base_ranking'] = ranking
        results.setdefault(group, []).append(row)
    for name, digest in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    metrics = {group: stats(rows, labels) for group, rows in results.items()}
    target = next(r for r in results['review_probes'] if r['id'] == 'REVIEW-03')
    passes = target['final_label'] == 'NUMERIC' and not any(c['regressed'] for c in changes.values())
    summary = dict(status='COMPLETED_OFFLINE', metrics=metrics, changes_against_v4=changes,
                   target_REVIEW03=target['resolution'], passes_gate=passes,
                   calibrated=False, confidence=None, router_integrated=False)
    write(OUT / 'results.json', results)
    write(OUT / 'summary.json', summary)
    print(json.dumps(dict(correct={k: v['correct'] for k, v in metrics.items()}, changes=changes, passes_gate=passes), indent=2))


if __name__ == '__main__':
    main()
