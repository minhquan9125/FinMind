"""Evaluate frozen S5 intent rankings without modifying examples or router behavior."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher, RANKING_POLICY, summarize_evaluation


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8', newline='\n')


def capture_evaluation_inputs(library_dir, test_path):
    """Bind disk fingerprints to the exact in-memory artifact used for ranking."""
    library_dir, test_path = Path(library_dir), Path(test_path)
    manifest_raw = (library_dir / 'manifest.json').read_bytes()
    library = load_library(library_dir)
    if json.loads(manifest_raw) != library.manifest:
        raise ValueError('LIBRARY_CHANGED_DURING_CAPTURE')
    snapshot_raw = (library_dir / 'dataset-manifest.json').read_bytes()
    schema_raw = (library_dir / 'label-schema.json').read_bytes()
    for name, raw in [('dataset-manifest.json', snapshot_raw), ('label-schema.json', schema_raw)]:
        if hashlib.sha256(raw).hexdigest() != library.manifest['files'][name]:
            raise ValueError('LIBRARY_CHANGED_DURING_CAPTURE')
    raw = test_path.read_bytes()
    snapshot = json.loads(snapshot_raw)
    if hashlib.sha256(raw).hexdigest() != snapshot['files']['test.jsonl']['sha256']:
        raise ValueError('TEST_SET_DIFFERS_FROM_REVIEWED_SNAPSHOT')
    return dict(library=library, schema=json.loads(schema_raw), test_raw=raw,
                cases=[json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()],
                library_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())


def assert_library_unchanged(directory, manifest_sha256):
    directory = Path(directory)
    if hashlib.sha256((directory / 'manifest.json').read_bytes()).hexdigest() != manifest_sha256:
        raise ValueError('LIBRARY_CHANGED_DURING_EVALUATION')
    load_library(directory)
    if hashlib.sha256((directory / 'manifest.json').read_bytes()).hexdigest() != manifest_sha256:
        raise ValueError('LIBRARY_CHANGED_DURING_EVALUATION')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=ROOT / 'outputs/s5_wbs033_20261110/intent-library-v1')
    parser.add_argument('--dataset', type=Path, default=ROOT / 'docs/sprint5/intent-dataset-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/s5_wbs041_20261110/run01')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    from validate_s5_intent_dataset import validate_dataset
    errors, _ = validate_dataset(args.dataset)
    if errors:
        raise ValueError(f'DATASET_VALIDATION_FAILED: {errors}')
    frozen = capture_evaluation_inputs(args.library, args.dataset / 'test.jsonl')
    library, schema, raw, cases = (frozen[key] for key in ('library', 'schema', 'test_raw', 'cases'))
    test_hash = hashlib.sha256(raw).hexdigest()
    labels = [item['id'] for item in schema['labels']]
    from src.documents.embeddings import get_embedding_service
    matcher = IntentMatcher(library, get_embedding_service())
    # Freeze method and inputs on disk before observing real-model scores.
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'test-input.jsonl').write_bytes(raw)
    method = dict(task_id='S5-WBS04.1', evaluation_id=args.output.name,
                  created_at=datetime.now(timezone.utc).isoformat(), ranking_policy=RANKING_POLICY,
                  group_score='MAX_COSINE_OVER_EXAMPLES_WITH_SAME_LABEL',
                  tie_break='score descending, label ascending, example ID ascending',
                  top_groups_returned=len(labels), top_examples_returned=5,
                  labeled_metrics=['top1_accuracy', 'top3_recall', 'macro_f1'],
                  unlabeled_policy='RANK_ONLY_EXCLUDED_FROM_ACCURACY_NO_THRESHOLD_OR_FALLBACK',
                  test_sha256=test_hash,
                  library_manifest_sha256=frozen['library_manifest_sha256'],
                  model=library.manifest['model'], library_version=library.manifest['library_version'],
                  dataset_version=library.manifest['dataset_version'],
                  frozen_before_inference=True, library_examples_modified=False,
                  test_is_blind_evaluation=False)
    write_json(args.output / 'method.json', method)
    print(f'Ranking {len(cases)} frozen test questions with {RANKING_POLICY}; no library writes.', flush=True)
    started = time.perf_counter()
    rankings = matcher.match_many([r['text'] for r in cases], top_groups=len(labels), top_examples=5)
    elapsed = time.perf_counter() - started
    summary = summarize_evaluation(cases, rankings, labels)
    records = []
    for case, ranking in zip(cases, rankings):
        record = dict(id=case['id'], expected_label=case['intent_label'],
                      annotation_status=case['annotation_status'], scope_status=case['scope_status'],
                      linguistic_form=case['linguistic_form'], ranking=ranking)
        records.append(record)
    (args.output / 'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n' for r in records),
                                             encoding='utf-8', newline='\n')
    summary.update(evaluation_id=args.output.name, ranking_policy=RANKING_POLICY,
                   total_cases=len(cases), batch_embedding_and_ranking_seconds=elapsed,
                   latency_note='One whole batch including lazy model load; not per-request response latency.',
                   unlabeled_status_counts=dict(Counter(r['annotation_status'] for r in cases if r['intent_label'] is None)),
                   route_or_threshold_implemented=False)
    for field in ('linguistic_form', 'scope_status'):
        summary['by_' + field] = {}
        for value in sorted({c[field] for c in cases}):
            indices = [i for i, c in enumerate(cases) if c[field] == value]
            part = summarize_evaluation([cases[i] for i in indices], [rankings[i] for i in indices], labels)
            summary['by_' + field][value] = {k: part[k] for k in ('labeled_cases', 'unlabeled_cases', 'top1_accuracy', 'top3_recall')}
    # Abort instead of publishing a successful summary with changed provenance.
    assert_library_unchanged(args.library, frozen['library_manifest_sha256'])
    summary.update(status='COMPLETED', library_unchanged=True)
    write_json(args.output / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
