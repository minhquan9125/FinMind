"""Offline contract 2.1 input -> reviewable role candidates and abstention audit."""
import argparse
import json
from pathlib import Path
from src.person_role.extractor import extract, normalize_and_extract


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, help='Envelope with WBS02 entities/mentions')
    p.add_argument('--output-dir', required=True, help='New directory; never overwrites input')
    p.add_argument('--normalize', action='store_true', help='Run supplied WBS02 resolver first')
    p.add_argument('--registry', help='Shared entity registry JSON used with --normalize')
    a = p.parse_args()
    source = json.loads(Path(a.input).read_text(encoding='utf-8-sig'))
    if a.registry and not a.normalize:
        p.error('--registry requires --normalize')
    registry = json.loads(Path(a.registry).read_text(encoding='utf-8-sig')) if a.registry else None
    result, audit = normalize_and_extract(source, registry) if a.normalize else extract(source)
    output = Path(a.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in [('candidates.json', result), ('audit.json', audit)]:
        (output / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'candidate_count': audit['candidate_count'], 'abstentions': len(audit['abstentions']), 'output': str(output)}))


if __name__ == '__main__':
    main()
