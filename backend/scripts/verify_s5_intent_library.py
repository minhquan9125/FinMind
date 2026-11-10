"""Read back all vectors; optionally re-encode three library rows with the real model."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_library import load_library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=ROOT / 'outputs/s5_wbs033_20261110/intent-library-v1')
    parser.add_argument('--reencode', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    artifact = load_library(args.library)
    norms = np.linalg.norm(artifact.vectors, axis=1)
    result = dict(status='PASS', task_id='S5-WBS03.3', library_version=artifact.manifest['library_version'],
                  dataset_version=artifact.manifest['dataset_version'], model=artifact.manifest['model'],
                  shape=list(artifact.vectors.shape), dtype=str(artifact.vectors.dtype),
                  counts=dict(Counter(r['intent_label'] for r in artifact.rows)),
                  norm_min=float(norms.min()), norm_max=float(norms.max()),
                  all_finite=bool(np.isfinite(artifact.vectors).all()), checksums_passed=True,
                  test_rows_embedded=artifact.manifest['test_rows_embedded'],
                  vectors_sha256=hashlib.sha256((args.library / 'vectors.npy').read_bytes()).hexdigest(),
                  reencoding=dict(executed=False), classification_accuracy_measured=False)
    if args.reencode:
        from src.documents.embeddings import get_embedding_service
        embedder = get_embedding_service()
        load_library(args.library, expected_model=embedder.model_name, expected_revision=embedder.revision)
        indices = sorted({0, len(artifact.rows) // 2, len(artifact.rows) - 1})
        regenerated = np.asarray(embedder.embed_texts([artifact.rows[i]['text'] for i in indices]), dtype=np.float32)
        stored = artifact.vectors[indices]
        same = regenerated.shape == stored.shape and np.allclose(regenerated, stored, atol=1e-5, rtol=1e-5)
        if not same:
            raise ValueError('REAL_MODEL_REENCODING_MISMATCH')
        result['reencoding'] = dict(executed=True, row_ids=[artifact.rows[i]['id'] for i in indices],
                                    max_absolute_difference=float(np.abs(regenerated - stored).max()),
                                    atol=1e-5, rtol=1e-5, passed=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
