"""Audit relation cues in already verified WBS03 envelopes, without DB access.

The counts are diagnostics, not precision/recall or approved relation labels.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sprint4_runtime.relation_extractor import (  # noqa: E402
    _ASSOC, _CONDITIONAL, _COOP, _HISTORICAL, _NEGATE, _OWN,
    _PLANNED, _SUB, _sentences,
)


CUES = {
    'subsidiary': _SUB,
    'associate': _ASSOC,
    'ownership': _OWN,
    'cooperation': _COOP,
}
BLOCKERS = (_NEGATE, _PLANNED, _CONDITIONAL, _HISTORICAL)


def audit(input_dir, sample_limit):
    files = sorted(input_dir.glob('*.candidates.json'))
    if not files:
        raise ValueError(f'No WBS03 candidate JSON files in {input_dir}')
    counts = Counter()
    samples = defaultdict(list)
    total_chunks = total_relations = 0
    for path in files:
        envelope = json.loads(path.read_text(encoding='utf-8'))
        document = envelope['documents'][0]
        total_chunks += len(envelope['chunks'])
        total_relations += len(envelope['relations'])
        entities = {e['entity_id']: e for e in envelope['entities']}
        mentions_by_chunk = defaultdict(list)
        for mention in envelope['mentions']:
            if entities[mention['entity_id']]['entity_type'] == 'Company':
                mentions_by_chunk[mention['chunk_id']].append(mention)
        for chunk in envelope['chunks']:
            company_mentions = mentions_by_chunk[chunk['chunk_id']]
            for start, end, sentence in _sentences(chunk['text']):
                cues = [name for name, pattern in CUES.items() if pattern.search(sentence)]
                if not cues:
                    continue
                present = [m for m in company_mentions if start <= m['start'] < m['end'] <= end]
                resolved = [m for m in present
                            if entities[m['entity_id']]['resolution_status'] == 'resolved']
                blocked = any(pattern.search(sentence) for pattern in BLOCKERS)
                if not present:
                    reason = 'no_company_mention'
                elif not resolved:
                    reason = 'unresolved_only'
                elif len(resolved) == 1:
                    reason = 'one_resolved_mention'
                else:
                    reason = 'multiple_resolved_mentions'
                for cue in cues:
                    key = (cue, reason, 'blocked_wording' if blocked else 'not_blocked')
                    counts[key] += 1
                    if len(samples[key]) < sample_limit:
                        samples[key].append({
                            'document_id': chunk['document_id'],
                            'title': document['title'],
                            'chunk_id': chunk['chunk_id'],
                            'quote': sentence.strip()[:500],
                            'resolved_mentions': [m['raw_name'] for m in resolved[:5]],
                            'unresolved_mentions': [m['raw_name'] for m in present
                                                    if m not in resolved][:5],
                        })
    groups = []
    for key, count in sorted(counts.items()):
        groups.append({'cue': key[0], 'mention_bucket': key[1], 'wording': key[2],
                       'sentence_count': count, 'samples': samples[key]})
    return {'documents': len(files), 'chunks': total_chunks,
            'existing_candidates': total_relations,
            'note': 'Cue sentence counts are diagnostic only; samples are not gold labels.',
            'groups': groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--sample-limit', type=int, default=5)
    args = parser.parse_args()
    if args.sample_limit < 0:
        parser.error('--sample-limit must be nonnegative')
    if args.out.exists():
        parser.error(f'Output already exists: {args.out}')
    try:
        result = audit(args.input_dir, args.sample_limit)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Audit failed: {type(exc).__name__}: {exc}\n')
    print(f"documents={result['documents']} chunks={result['chunks']} "
          f"existing_candidates={result['existing_candidates']} groups={len(result['groups'])} "
          f"output={args.out}")


if __name__ == '__main__':
    main()
