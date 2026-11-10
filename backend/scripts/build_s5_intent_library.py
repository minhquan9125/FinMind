"""Build or verify the approved S5 intent vector library, without database writes."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from src.retrieval_orchestration.intent_library import build_library, load_library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'docs/sprint5/intent-dataset-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/s5_wbs033_20261110/intent-library-v1')
    parser.add_argument('--library-version', default='s5-intent-library-v1')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if args.verify_only:
        artifact = load_library(args.output)
    else:
        from validate_s5_intent_dataset import validate_dataset
        errors, _ = validate_dataset(args.dataset)
        if errors:
            raise ValueError(f'DATASET_VALIDATION_FAILED: {errors}')
        from src.documents.embeddings import get_embedding_service
        from src.core.config import get_settings
        settings = get_settings()
        print('Embedding library.jsonl only; model=' + settings.embedding_model + '@' + settings.embedding_model_revision,
              flush=True)
        artifact = build_library(args.dataset, ROOT / 'docs/sprint5/intent-labels.v1.json', args.output,
                                 get_embedding_service(), library_version=args.library_version,
                                 expected_dimension=settings.embedding_dim)
    print(json.dumps(dict(status=artifact.manifest['status'], row_count=len(artifact.rows),
                          shape=list(artifact.vectors.shape), model=artifact.manifest['model'],
                          library_version=artifact.manifest['library_version'], output=str(args.output)),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
