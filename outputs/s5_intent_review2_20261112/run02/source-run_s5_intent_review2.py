"""Frozen spelling/consumer review checks on unchanged BGE-M3 and linear head."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_semantic_requests import requests, resolve_objectives, explicit_intent
from src.retrieval_orchestration.intent_scoring import classifier_probabilities, rankings
from run_s5_intent_news import vectors as previous_vectors, SCORER
from run_s5_intent_reviewfix import read, write
from run_s5_intent_consensus import stats

PARENT = ROOT / 'outputs/s5_intent_news_20261112/run01'
BASE = ROOT / 'outputs/s5_intent_review2_20261112'
OUT = BASE / 'run02'


@lru_cache(maxsize=None)
def _rankings_file(path):
    return read(ROOT / path)


def raw_ranking(row):
    while 'base_ranking_ref' in row:
        ref = row['base_ranking_ref']
        row = next(r for r in _rankings_file(ref['path'])[ref['evaluation_set']] if r['id'] == ref['id'])
    return row['base_ranking']


def inputs():
    prior = read(PARENT / 'results.json')
    sources = {(group, r['id']): r for group, rows in prior.items() for r in rows}
    cases = [dict(id=r['id'], question=r['question'], gold=r['gold'], evaluation_set=group,
                  prior_label=r['final_label']) for (group, _), r in sources.items()]
    cases += [dict(row, evaluation_set='review2_probes') for row in read(BASE / 'probes.json')]
    return cases, sources


def vectors():
    lookup, caches = previous_vectors()
    pair = (PARENT / 'new-texts.json', PARENT / 'new-vectors.npy')
    lookup.update(zip(read(pair[0]), np.load(pair[1], allow_pickle=False)))
    caches.append(pair)
    pair = (BASE / 'run01/new-texts.json', BASE / 'run01/new-vectors.npy')
    lookup.update(zip(read(pair[0]), np.load(pair[1], allow_pickle=False)))
    return lookup, caches + [pair]


def main():
    if OUT.exists():
        raise FileExistsError('Keep frozen attempts; never overwrite completed output')
    cases, sources = inputs()
    parts = [requests(row['question']) for row in cases]
    lookup, caches = vectors()
    needed = sorted(({r['question'] for r in cases} | {p for spans in parts for p in spans}) - lookup.keys())
    fit = ROOT / read(SCORER / 'fit-location.json')['output']
    params = np.load(fit / 'parameters.npz', allow_pickle=False)
    labels = read(fit / 'summary.json')['labels']
    model = read(SCORER / 'method.json')['model']
    watched = [Path(__file__), ROOT / 'backend/scripts/audit_s5_intent_review2.py',
               BASE / 'plan.json', BASE / 'probes.json', BASE / 'consumer-source.json',
               BASE / 'consumer-original.py', BASE / 'development-note.json',
               BASE / 'run01/source-intent_semantic_requests.py', PARENT / 'results.json', fit / 'parameters.npz',
               ROOT / 'outputs/s5_intent_numeric_20261112/run01/results.json',
               ROOT / 'outputs/s5_intent_reviewfix_20261112/run02/results.json',
               ROOT / 'docs/sprint5/intent-labels.v1.json']
    watched += sorted((ROOT / 'backend/src/retrieval_orchestration').glob('intent_*.py'))
    watched += [p for pair in caches for p in pair]
    watched += [SCORER / p for p in ['training.jsonl', 'training-vectors.npy', 'evaluation-cases.json', 'evaluation-vectors.npy']]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    OUT.mkdir()
    write(OUT / 'method.json', dict(status='FROZEN_BEFORE_EVALUATION', source_hashes=hashes,
          model=model, no_fit=True, seen_regression_rows=313, additional_probes=32,
          independent_blind_test=False, confidence=None, runtime_enabled=False))
    write(OUT / 'cases.json', cases)
    write(OUT / 'parts.json', parts)
    write(OUT / 'new-texts.json', needed)
    if needed:
        from src.documents.embeddings import get_embedding_service
        encoder = get_embedding_service()
        assert (encoder.model_name, encoder.revision) == (model['name'], model['revision'])
        print(f'Embedding {len(needed)} texts for frozen review checks, no refit.', flush=True)
        new = np.asarray(encoder.embed_texts(needed), dtype=np.float32)
    else:
        new = np.empty((0, 1024), dtype=np.float32)
    assert new.shape == (len(needed), 1024) and np.isfinite(new).all()
    np.save(OUT / 'new-vectors.npy', new, allow_pickle=False)
    lookup.update(zip(needed, new))
    results, fixed, regressed, guard_failures = {}, [], [], []
    for case, spans in zip(cases, parts):
        group, question = case['evaluation_set'], case['question']
        prior = sources.get((group, case['id']))
        if prior:
            ranking = raw_ranking(prior)
            base = [next(g['score'] for g in ranking['groups'] if g['intent_label'] == label) for label in labels]
        else:
            base = classifier_probabilities(np.stack([lookup[question]]), params['coefficients'], params['intercepts'])[0]
            ranking = rankings([question], [base], labels, 'intent-linear-v1', 'CLASSIFIER_PROBABILITY_UNCALIBRATED', model)[0]
        component = classifier_probabilities(np.stack([lookup[t] for t in spans]), params['coefficients'], params['intercepts']) if spans != [question] else []
        decision = resolve_objectives(base, component, labels, spans)
        row = dict(case, parts=spans, final_label=decision['intent_label'], resolution=decision,
                   component_probabilities=np.asarray(component).tolist())
        if prior:
            row['base_ranking_ref'] = dict(path=PARENT.relative_to(ROOT).as_posix() + '/results.json', evaluation_set=group, id=case['id'])
            if case['gold']:
                before, after = prior['final_label'] == case['gold'], row['final_label'] == case['gold']
                if not before and after: fixed.append(dict(evaluation_set=group, id=case['id']))
                if before and not after: regressed.append(dict(evaluation_set=group, id=case['id']))
        else:
            row['base_ranking'] = ranking
        if case.get('must_not_force'):
            row['non_forcing_check_passed'] = explicit_intent(question) != case['must_not_force']
            if not row['non_forcing_check_passed']: guard_failures.append(case['id'])
        results.setdefault(group, []).append(row)
    for name, digest in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    summary = dict(status='COMPLETED_OFFLINE', metrics={group: stats(rows, labels) for group, rows in results.items()},
                   fixed=fixed, regressed=regressed, non_forcing_failures=guard_failures,
                   passes_gate=not regressed and not guard_failures,
                   confidence=None, calibrated=False, router_integrated=False)
    write(OUT / 'results.json', results)
    write(OUT / 'summary.json', summary)
    print(json.dumps(dict(correct={k: (v['correct'], v['labeled']) for k, v in summary['metrics'].items()},
                         fixed=fixed, regressed=regressed, non_forcing_failures=guard_failures,
                         passes_gate=summary['passes_gate']), indent=2))


if __name__ == '__main__':
    main()
