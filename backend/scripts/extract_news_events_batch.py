"""Read-only WBS16 handoff: extract a bounded, explicit NEWS article batch.

Input articles are JSON array rows from news_articles. Optional candidates are a
JSON object keyed by article_id; they are validated against the saved body.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.documents.news_event_extractor import extract_batch, rule_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--articles', required=True, help='JSON array of explicitly selected news_articles rows')
    parser.add_argument('--candidates', help='Optional JSON object: article_id -> candidate list')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    articles = json.loads(Path(args.articles).read_text(encoding='utf-8'))
    if not isinstance(articles, list):
        parser.error('--articles must be a JSON array')
    supplied = json.loads(Path(args.candidates).read_text(encoding='utf-8')) if args.candidates else {}
    if not isinstance(supplied, dict):
        parser.error('--candidates must be a JSON object')
    def propose(article):
        return supplied.get(str(article['article_id']), rule_candidates(article))
    result = extract_batch(manifest, articles, propose)
    target = Path(args.out)
    if target.exists():
        raise FileExistsError(f'Output already exists: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'articles': len(result['article_results']), 'events': len(result['events']),
                      'review': sum(r['status'] == 'REVIEW' for r in result['article_results']),
                      'out': str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
