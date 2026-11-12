"""Replay previously seen cases with frozen NEWS/read-clause logic, no refit."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_news_requests import requests, resolve_objectives
from src.retrieval_orchestration.intent_scoring import classifier_probabilities
from run_s5_intent_numeric import vectors as prior_vectors, SCORER
from run_s5_intent_reviewfix import read, write
from run_s5_intent_consensus import stats

PARENT = ROOT / 'outputs/s5_intent_numeric_20261112/run01'
OUT = ROOT / 'outputs/s5_intent_news_20261112/run01'


def inputs():
    previous = read(PARENT / 'results.json')
    sources = {(group, row['id']): row for group, rows in previous.items() for row in rows}
    cases = [dict(id=row['id'], question=row['question'], gold=row['gold'],
                  evaluation_set=group, prior_label=row['final_label'])
             for (group, _), row in sources.items()]
    return cases, sources


def raw_ranking(row):
    while 'base_ranking_ref' in row:
        ref = row['base_ranking_ref']
        row = next(r for r in read(ROOT / ref['path'])[ref['evaluation_set']] if r['id'] == ref['id'])
    return row['base_ranking']


def vectors():
    lookup, caches = prior_vectors()
    pair = (PARENT / 'new-texts.json', PARENT / 'new-vectors.npy')
    lookup.update(zip(read(pair[0]), np.load(pair[1], allow_pickle=False)))
    return lookup, caches + [pair]


def main():
    if OUT.exists():
        raise FileExistsError('Keep frozen results; choose a new version for further changes')
    cases, sources = inputs()
    spans = [requests(row['question']) for row in cases]
    lookup, caches = vectors()
    needed = sorted({q for parts in spans for q in parts} - lookup.keys())
    fit = ROOT / read(SCORER / 'fit-location.json')['output']
    params = np.load(fit / 'parameters.npz', allow_pickle=False)
    labels = read(fit / 'summary.json')['labels']
    model = read(SCORER / 'method.json')['model']
    watched = [Path(__file__), ROOT / 'backend/scripts/audit_s5_intent_news.py',
               ROOT / 'docs/sprint5/S5-WBS04.1-news-mixed-plan.md',
               ROOT / 'docs/sprint5/intent-labels.v1.json', PARENT / 'results.json',
               ROOT / 'outputs/s5_intent_reviewfix_20261112/run02/results.json', fit / 'parameters.npz']
    watched += sorted((ROOT / 'backend/src/retrieval_orchestration').glob('intent_*.py'))
    watched += [p for pair in caches for p in pair]
    watched += [SCORER / name for name in ['training.jsonl', 'training-vectors.npy', 'evaluation-cases.json', 'evaluation-vectors.npy']]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    OUT.mkdir(parents=True)
    write(OUT / 'method.json', dict(status='FROZEN_BEFORE_EVALUATION', source_hashes=hashes,
          model=model, no_fit=True, seen_regression_rows=313, independent_blind_test=False,
          confidence=None, runtime_enabled=False))
    write(OUT / 'cases.json', cases)
    write(OUT / 'parts.json', spans)
    write(OUT / 'new-texts.json', needed)
    if needed:
        from src.documents.embeddings import get_embedding_service
        encoder = get_embedding_service()
        assert (encoder.model_name, encoder.revision) == (model['name'], model['revision'])
        print(f'Embedding {len(needed)} newly split texts; same BGE-M3 and classifier.', flush=True)
        new = np.asarray(encoder.embed_texts(needed), dtype=np.float32)
    else:
        new = np.empty((0, 1024), dtype=np.float32)
    assert new.shape == (len(needed), 1024) and np.isfinite(new).all()
    np.save(OUT / 'new-vectors.npy', new, allow_pickle=False)
    lookup.update(zip(needed, new))
    results, fixed, regressed = {}, [], []
    for case, parts in zip(cases, spans):
        group, question = case['evaluation_set'], case['question']
        prior = sources[group, case['id']]
        ranking = raw_ranking(prior)
        base = [next(g['score'] for g in ranking['groups'] if g['intent_label'] == label) for label in labels]
        component = classifier_probabilities(np.stack([lookup[q] for q in parts]), params['coefficients'], params['intercepts']) if parts != [question] else []
        decision = resolve_objectives(base, component, labels, parts)
        row = dict(case, parts=parts, final_label=decision['intent_label'], resolution=decision,
                   component_probabilities=np.asarray(component).tolist(),
                   base_ranking_ref=dict(path=PARENT.relative_to(ROOT).as_posix() + '/results.json', evaluation_set=group, id=case['id']))
        results.setdefault(group, []).append(row)
        if case['gold']:
            before, after = prior['final_label'] == case['gold'], row['final_label'] == case['gold']
            if not before and after: fixed.append(dict(evaluation_set=group, id=case['id']))
            if before and not after: regressed.append(dict(evaluation_set=group, id=case['id']))
    for name, digest in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    metrics = {group: stats(rows, labels) for group, rows in results.items()}
    targets = [row for row in results['additional_checks'] if row['id'] in {'NV-13', 'NV-19', 'NV-20'}]
    passes = all(row['final_label'] == row['gold'] for row in targets) and len(targets) == 3 and not regressed
    summary = dict(status='COMPLETED_OFFLINE', metrics=metrics, fixed=fixed, regressed=regressed,
                   passes_gate=passes, confidence=None, calibrated=False, router_integrated=False)
    write(OUT / 'results.json', results)
    write(OUT / 'summary.json', summary)
    print(json.dumps(dict(correct={k: v['correct'] for k, v in metrics.items()}, fixed=fixed, regressed=regressed, passes_gate=passes), indent=2))


if __name__ == '__main__':
    main()
