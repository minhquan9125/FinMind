"""Rank intent groups for one question using the approved vector library."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question', required=True)
    parser.add_argument('--library', type=Path, default=ROOT / 'outputs/s5_wbs033_20261110/intent-library-v1')
    parser.add_argument('--top-groups', type=int, default=3)
    parser.add_argument('--top-examples', type=int, default=5)
    args = parser.parse_args()
    from src.documents.embeddings import get_embedding_service
    matcher = IntentMatcher(load_library(args.library), get_embedding_service())
    print(json.dumps(matcher.match(args.question, top_groups=args.top_groups, top_examples=args.top_examples),
                     ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
