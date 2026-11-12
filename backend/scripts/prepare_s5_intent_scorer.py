"""Freeze library-only grouped training and previously seen evaluation vectors."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_scoring import family_weights,family_folds
from src.retrieval_orchestration.intent_library import load_library

OUT=ROOT/'outputs/s5_intent_scorer_20261112'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    original=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    base=load_library(original)
    training=ROOT/'outputs/s5_intent_additive_20261112/add_all'
    metadata=json.loads((training/'manifest.json').read_text())
    for name,digest in metadata['files'].items():
        if sha(training/name)!=digest: raise ValueError('TRAINING_SOURCE_CHANGED')
    rows=read_rows(training/'library.jsonl')
    x=np.load(training/'vectors.npy',allow_pickle=False)
    if (x.shape!=(202,1024) or len(rows)!=202 or rows[:90]!=list(base.rows)
            or x[:90].tobytes()!=base.vectors.tobytes() or not np.isfinite(x).all()
            or not np.allclose(np.linalg.norm(x,axis=1),1,atol=1e-4,rtol=0)):
        raise ValueError('INVALID_TRAINING')
    weights,folds=family_weights(rows),family_folds(rows,4)
    cache=ROOT/'outputs/s5_intent_experiment_20261111/run01'
    lookup=dict(zip(json.loads((cache/'embedded-texts.json').read_text(encoding='utf-8')),
                    np.load(cache/'experiment-vectors.npy',allow_pickle=False)))
    earlier=ROOT/'outputs/s5_intent_additive_20261112/later-check'
    lookup.update(zip([r['text'] for r in read_rows(earlier/'input.jsonl')],np.load(earlier/'query-vectors.npy',allow_pickle=False)))
    data=ROOT/'docs/sprint5/intent-experiment-v2'
    paths=dict(development=data/'development.jsonl',
               regression=ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl',
               known_diagnostic=data/'known-diagnostic.jsonl',previous_check=earlier/'input.jsonl')
    sets={name:read_rows(path) for name,path in paths.items()}
    train_text={r['text'].strip().casefold() for r in rows}
    if train_text&{r['text'].strip().casefold() for cases in sets.values() for r in cases}:
        raise ValueError('TRAIN_EVALUATION_EXACT_OVERLAP')
    OUT.mkdir()
    shutil.copyfile(training/'library.jsonl',OUT/'training.jsonl')
    shutil.copyfile(training/'vectors.npy',OUT/'training-vectors.npy')
    shutil.copyfile(ROOT/'tasks/plan.md',OUT/'plan-snapshot.md')
    np.save(OUT/'weights.npy',weights,allow_pickle=False)
    np.save(OUT/'folds.npy',folds,allow_pickle=False)
    flat=[dict(r,evaluation_set=name) for name,cases in sets.items() for r in cases]
    write(OUT/'evaluation-cases.json',flat)
    np.save(OUT/'evaluation-vectors.npy',np.stack([lookup[r['text']] for r in flat]),allow_pickle=False)
    source=[*original.iterdir(),*(training/name for name in ['manifest.json','library.jsonl','vectors.npy']),
            cache/'embedded-texts.json',cache/'experiment-vectors.npy',earlier/'query-vectors.npy',*paths.values(),
            ROOT/'backend/src/retrieval_orchestration/intent_scoring.py',
            ROOT/'backend/src/retrieval_orchestration/intent_matching.py',Path(__file__)]
    write(OUT/'method.json',dict(status='FROZEN_BEFORE_FIT',date='2026-11-12',model=base.manifest['model'],
        training_rows=len(rows),training_families=len({r['family_id'] for r in rows}),folds=4,
        split_policy='SORT_FAMILIES_WITHIN_LABEL_ROUND_ROBIN_FOLD',
        sample_weight='EQUAL_LABEL_TOTAL_AND_EQUAL_FAMILY_TOTAL_WITHIN_LABEL_MEAN_WEIGHT_ONE',
        candidates=['family_centroid','logistic_regression'],C_grid=[.1,1.,10.],
        solver='lbfgs',l1_ratio=0.,max_iter=2000,tol=1e-8,
        C_selection='POOLED_OOF_MACRO_F1_THEN_ACCURACY_THEN_SMALLER_C',
        eligibility='DEV_TOP1_AND_MACRO_F1_IMPROVE_AND_ZERO_OLD_CORRECT_TO_WRONG',
        evaluation_sets_seen=True,no_test_rows_fitted=True,no_runtime_change=True,
        probability_calibrated=False,legacy_threshold_not_applied_to_candidates=True,
        source_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in source if p.is_file()},
        files={name:sha(OUT/name) for name in ['training.jsonl','training-vectors.npy','plan-snapshot.md',
              'weights.npy','folds.npy','evaluation-cases.json','evaluation-vectors.npy']}))
    print(json.dumps(dict(training_rows=len(rows),families=len({r['family_id'] for r in rows}),
          folds=4,evaluation_rows=len(flat),no_test_rows_fitted=True),indent=2))


if __name__=='__main__':
    main()
