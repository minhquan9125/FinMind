"""Lệnh chuẩn hóa và kiểm tra cục bộ, không ghi đè tệp có sẵn."""
import argparse
import json
import sys
from pathlib import Path
from .contracts import SCHEMA, validate_envelope, migrate_v1
from .entities import normalize

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result

def _constant(value):
    raise ValueError('Nonfinite JSON value: ' + value)

def _read(path):
    return json.loads(Path(path).read_text('utf-8-sig'), object_pairs_hook=_pairs, parse_constant=_constant)

def _write(path, payload):
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    # Exclusive create protects both source and pre-existing outputs.
    target = Path(path)
    with target.open('x', encoding='utf-8') as f:
        try:
            f.write(text)
        except (OSError, UnicodeError):
            f.close()
            target.unlink(missing_ok=True)
            raise

def main(argv=None):
    parser = argparse.ArgumentParser(description='Resolver BCTN và contract JSON cục bộ')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('normalize', 'validate', 'migrate'):
        p = sub.add_parser(name); p.add_argument('--input', required=True)
        if name in ('normalize', 'migrate'):
            p.add_argument('--output', required=True)
        if name == 'normalize':
            p.add_argument('--registry')
    p = sub.add_parser('schema'); p.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'schema':
            _write(args.output, SCHEMA)
        else:
            data = _read(args.input)
            if args.command == 'migrate':
                _write(args.output, migrate_v1(data))
                print('OK')
                return 0
            validate_envelope(data)
            if args.command == 'normalize':
                if any(data[k] for k in ('entities', 'mentions', 'relations')):
                    raise ValueError('normalize requires empty entities/mentions/relations; use validate for existing results')
                registry = _read(args.registry) if args.registry else None
                result = {**data, **normalize(data['chunks'], registry)}
                validate_envelope(result)
                _write(args.output, result)
        print('OK')
        return 0
    except (ValueError, OSError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
