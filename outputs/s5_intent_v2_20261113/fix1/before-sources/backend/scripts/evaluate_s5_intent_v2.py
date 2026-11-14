"""Evaluate frozen development vectors, retaining every raw and resolved result."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier
from src.retrieval_orchestration.intent_v2_dataset import read_rows
from src.retrieval_orchestration.intent_matching import summarize_evaluation
from build_s5_intent_v2 import CACHE, OUT, sha, write


class FrozenEncoder:
    """Exact real BGE vectors, for offline reproducibility; never a latency proxy."""
    def __init__(self, rows, vectors, model):
        self.model_name, self.revision = model['name'], model['revision']
        self.values = {r['text']: v for r, v in zip(rows, vectors)}

    def embed_texts(self, texts):
        return [self.values[text] for text in texts]


def evaluate(output, artifact=OUT, *, legacy=False):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    frozen = json.loads((CACHE / 'completed.json').read_text(encoding='utf-8'))
    for name, digest in frozen['files'].items():
        if sha(CACHE / name) != digest:
            raise ValueError('VECTOR_CACHE_CHECKSUM_MISMATCH')
    output.mkdir(parents=True)
    watched = [ROOT / 'backend/src/retrieval_orchestration' / n for n in
               ['intent_v2_classifier.py', 'intent_v2_rules.py', 'intent_scoring.py',
                'intent_matching.py', 'intent_library.py']]
    paths = [Path(__file__), *watched]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    snapshots = output / 'source-snapshot'
    for path in paths:
        target = snapshots / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    rows_path = CACHE.parent / 'legacy-regression/cases.json' if legacy else CACHE / 'development.jsonl'
    vectors_path = CACHE.parent / 'legacy-regression/query-vectors.npy' if legacy else CACHE / 'development-vectors.npy'
    write(output / 'method.json', dict(status='FROZEN_BEFORE_EVALUATION',
        source_hashes=hashes, artifact_manifest_sha256=sha(artifact / 'manifest.json'),
        development_used_for_fit=False, blind_acceptance=False, cached_vectors_not_latency=True,
        evaluation_set='LEGACY_V2_MAPPED_REGRESSION' if legacy else 'DEVELOPMENT',
        data_files={str(p.relative_to(ROOT).as_posix()): sha(p) for p in [rows_path, vectors_path]},
        goals=dict(top1=0.9, macro_f1=0.85, each_recall=0.8, out_of_scope_false_accept=0)))
    rows = json.loads(rows_path.read_text(encoding='utf-8')) if legacy else read_rows(rows_path)
    vectors = np.load(vectors_path, allow_pickle=False)
    model = json.loads((artifact / 'library/manifest.json').read_text(encoding='utf-8'))['model']
    classifier = IntentClassifier.load(artifact, FrozenEncoder(rows, vectors, model))
    results = [dict(id=r['id'], gold=r['intent_label'], gold_components=r['component_intents'],
                    **classifier.classify(r['text'])) for r in rows]
    metrics = {}
    for name in ['base_ranking', 'reference_ranking', 'resolution']:
        predictions = ([dict(groups=[dict(intent_label=r[name]['intent_label'])]) for r in results]
                       if name == 'resolution' else [r[name] for r in results])
        metrics[name] = summarize_evaluation(rows, predictions, classifier.manifest['labels'])
    restricted = [r['id'] for r in results if r['gold'] == 'OUT_OF_SCOPE'
                  and r['resolution']['intent_label'] not in ['OUT_OF_SCOPE', 'MIXED']]
    mixed = [r for r in results if r['gold'] == 'MIXED']
    metrics['resolution'].update(
        restricted_misclassification_ids=restricted,
        mixed_exact_components=sum(r['resolution']['intent_label'] == 'MIXED'
            and set(r['gold_components']) == set(r['resolution']['component_labels']) for r in mixed),
        mixed_support=len(mixed),
        not_proposed_ids=[r['id'] for r in results if r['resolution']['status'] != 'PROPOSED'],
        routing_not_executed=True)
    for name, digest in hashes.items():
        if sha(ROOT / name) != digest:
            raise ValueError('SOURCE_CHANGED_DURING_EVALUATION')
    write(output / 'results.json', results)
    write(output / 'summary.json', dict(status='DEVELOPMENT_ONLY_NOT_ACCEPTANCE', metrics=metrics,
        results_sha256=sha(output / 'results.json'), method_sha256=sha(output / 'method.json')))
    print(json.dumps({n: {k: v for k, v in m.items() if k not in ['confusion_matrix','per_label']}
                      for n, m in metrics.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, default=OUT)
    parser.add_argument('--legacy', action='store_true')
    args = parser.parse_args()
    evaluate(args.output, args.artifact, legacy=args.legacy)
