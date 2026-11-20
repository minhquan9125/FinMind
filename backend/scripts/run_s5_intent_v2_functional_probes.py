"""Call the public classifier with real BGE-M3 on fixed functional regression probes."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_v2_classifier import classify_intent, LABELS
from src.retrieval_orchestration.intent_v2_dataset import read_rows
from build_s5_intent_v2 import OUT, CACHE, sha, write
from evaluate_s5_intent_v2 import summarize_resolution


def run(corpus, output):
    corpus, output = Path(corpus).resolve(), Path(output)
    if output.exists():
        raise FileExistsError(output)
    rows = read_rows(corpus)
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('INVALID_PROBE_IDS')
    for row in rows:
        components = row['component_intents']
        if row['intent_label'] not in LABELS or not row['text'].strip():
            raise ValueError('INVALID_PROBE_GOLD')
        if row['intent_label'] == 'MIXED' and (len(set(components)) < 2 or not set(components) <= LABELS - {'MIXED'}):
            raise ValueError('INVALID_PROBE_COMPONENTS')
        if row['intent_label'] != 'MIXED' and components:
            raise ValueError('INVALID_PROBE_COMPONENTS')
    output.mkdir(parents=True)
    sources = [Path(__file__), ROOT / 'backend/src/retrieval_orchestration/intent_v2_rules.py',
               ROOT / 'backend/src/retrieval_orchestration/intent_v2_classifier.py',
               ROOT / 'backend/src/documents/embeddings.py',
               ROOT / 'backend/scripts/evaluate_s5_intent_v2.py', corpus]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    write(output / 'method.json', dict(status='FROZEN_BEFORE_REAL_MODEL_RUN',
        source_hashes=hashes, artifact_manifest_sha256=sha(OUT / 'manifest.json'),
        probe_count=len(rows), blind_acceptance=False, no_fit=True, no_latency_acceptance=True,
        python=platform.python_version(), packages={p: importlib.metadata.version(p)
            for p in ['numpy', 'torch', 'sentence-transformers']}))
    (output / 'cases.jsonl').write_bytes(corpus.read_bytes())
    encoder = get_embedding_service()
    expected = json.loads((OUT / 'library/manifest.json').read_text())['model']
    if encoder.model_name != expected['name'] or encoder.revision != expected['revision']:
        raise ValueError('MODEL_OR_REVISION_MISMATCH')
    print('Loading existing BGE-M3 cache; real API calls, no query-vector cache.', flush=True)
    results = []
    for i, row in enumerate(rows):
        result = classify_intent(row['text'], embedder=encoder, artifact_path=OUT)
        results.append(dict(id=row['id'], gold=row['intent_label'], **result))
        if (i + 1) % 8 == 0:
            print('REAL_FUNCTIONAL_PROBES', i + 1, '/', len(rows), flush=True)
    for path, digest in hashes.items():
        if sha(ROOT / path) != digest:
            raise ValueError('SOURCE_CHANGED_DURING_REAL_MODEL_RUN: ' + path)
    resolutions = [r['resolution'] for r in results]
    metrics = summarize_resolution(rows, resolutions)
    wrong_status = metrics['status_mismatch_ids']
    ok = metrics['complete_classification_correct_count'] == len(rows) and not wrong_status
    write(output / 'results.json', results)
    write(output / 'summary.json', dict(status='PASS' if ok else 'FAIL', metrics=metrics,
        wrong_status_ids=wrong_status, real_model=True, query_vectors_recomputed=True,
        blind_acceptance=False, timing_not_measured=True))
    print(json.dumps(dict(status='PASS' if ok else 'FAIL', correct=metrics['complete_classification_correct_count'],
        cases=len(rows), wrong_status_ids=wrong_status), indent=2), flush=True)
    return ok


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=CACHE.parent / 'fix1/functional-probes-r2.jsonl')
    parser.add_argument('--output', type=Path, default=CACHE.parent / 'fix1/real-model')
    args = parser.parse_args()
    raise SystemExit(0 if run(args.corpus, args.output) else 1)
