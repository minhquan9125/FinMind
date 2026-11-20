"""Fit an eleven-class artifact using grouped LIBRARY folds, never development."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_scoring import family_folds, family_weights
from src.retrieval_orchestration.intent_v2_dataset import read_rows, validate_dataset

CACHE = ROOT / 'outputs/s5_intent_v2_20261113/vector-cache'
DATA = ROOT / 'docs/sprint5/intent-v2'
SCHEMA = ROOT / 'docs/sprint5/intent-labels.v2.json'
OUT = CACHE.parent / 'artifact-v2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def fit(output=OUT):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    frozen = json.loads((CACHE / 'completed.json').read_text(encoding='utf-8'))
    if frozen['status'] != 'PASS':
        raise ValueError('INCOMPLETE_VECTOR_CACHE')
    watched = [(ROOT / n, h) for n, h in frozen['input_hashes'].items()]
    watched += [(CACHE / n, h) for n, h in frozen['files'].items()]
    for path, digest in watched:
        if sha(path) != digest:
            raise ValueError('FROZEN_INPUT_CHANGED: ' + str(path))
    validate_dataset(DATA, SCHEMA)
    rows = read_rows(CACHE / 'library.jsonl')
    x = np.load(CACHE / 'library-vectors.npy', allow_pickle=False).astype(np.float64)
    y = np.array([r['intent_label'] for r in rows])
    labels, folds, weights = sorted(set(y)), family_folds(rows), family_weights(rows)
    output.mkdir(parents=True)
    configuration = dict(solver='lbfgs', l1_ratio=0.0, max_iter=2000, tol=1e-8)
    write(output / 'method.json', dict(status='FROZEN_BEFORE_FIT', C_grid=[0.1, 1, 10],
        folds=4, grouped_by='family_id', family_balanced_weights=True, configuration=configuration,
        development_used_for_fit_or_selection=False, calibrated=False,
        runner_sha256=sha(__file__), source_hashes=frozen['input_hashes'],
        cache_manifest_sha256=sha(CACHE / 'completed.json'),
        sklearn=importlib.metadata.version('scikit-learn')))
    candidates = []
    for c in [0.1, 1, 10]:
        predicted = np.empty(len(rows), dtype=y.dtype)
        for fold in range(4):
            train, val = np.flatnonzero(folds != fold), np.flatnonzero(folds == fold)
            if {rows[i]['family_id'] for i in train} & {rows[i]['family_id'] for i in val}:
                raise ValueError('FAMILY_LEAKAGE')
            model = LogisticRegression(C=c, **configuration)
            with warnings.catch_warnings():
                warnings.simplefilter('error', ConvergenceWarning)
                model.fit(x[train], y[train], sample_weight=family_weights([rows[i] for i in train]))
            predicted[val] = model.predict(x[val])
        candidates.append(dict(C=c, macro_f1=float(f1_score(y, predicted, labels=labels,
            average='macro', sample_weight=weights)), accuracy=float(np.average(y == predicted, weights=weights))))
    chosen = min(candidates, key=lambda r: (-r['macro_f1'], -r['accuracy'], r['C']))
    model = LogisticRegression(C=chosen['C'], **configuration)
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        model.fit(x, y, sample_weight=weights)
    if list(model.classes_) != labels:
        raise ValueError('CLASS_ORDER_MISMATCH')
    np.savez(output / 'classifier.npz', coefficients=model.coef_, intercepts=model.intercept_)
    write(output / 'fit.json', dict(selection=chosen, candidates=candidates, configuration=configuration,
        labels=labels, library_rows=len(rows), seed_families=len({r['family_id'] for r in rows}),
        development_used_for_fit_or_selection=False, calibrated=False, iterations=model.n_iter_.tolist()))
    library = output / 'library'
    library.mkdir()
    for name, source in [('library.jsonl', DATA / 'library.jsonl'), ('label-schema.json', SCHEMA),
                         ('dataset-manifest.json', DATA / 'manifest.json')]:
        (library / name).write_bytes(source.read_bytes())
    (library / 'vectors.npy').write_bytes((CACHE / 'library-vectors.npy').read_bytes())
    dataset = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
    model_info = json.loads((CACHE / 'method.json').read_text(encoding='utf-8'))['model']
    model_info.update(dtype='float32', normalization='L2')
    write(library / 'manifest.json', dict(format_version=1, status='READY',
        approval_status='OWNER_AUTHORIZED_PENDING_TEAM_REVIEW', library_version='intent-library-v2-draft1',
        dataset_version=dataset['dataset_version'], label_schema_version=dataset['label_schema_version'],
        model=model_info, row_count=len(rows), row_ids=[r['id'] for r in rows], test_rows_embedded=0,
        files={n: sha(library / n) for n in ['library.jsonl', 'label-schema.json', 'dataset-manifest.json', 'vectors.npy']}))
    for path, digest in watched:
        if sha(path) != digest:
            raise ValueError('INPUT_CHANGED_DURING_FIT')
    write(output / 'manifest.json', dict(format_version='intent-classifier-v2', status='READY_FOR_REVIEW',
        approval_status='OWNER_AUTHORIZED_PENDING_TEAM_REVIEW', classifier_version='intent-linear-v2-draft1',
        labels=labels, runtime_enabled=False, calibrated=False,
        files={n: sha(output / n) for n in ['library/manifest.json', 'classifier.npz', 'fit.json']}))
    print(json.dumps(dict(output=str(output), selection=chosen, candidates=candidates), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    fit(parser.parse_args().output)
