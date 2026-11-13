"""Validate versioned intent data before encoding or fitting; no model/service I/O."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata


def normalized_text(text):
    folded = unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
    return ' '.join(re.findall(r'[a-z0-9]+', ''.join(c for c in folded if not unicodedata.combining(c))))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def validate_rows(rows, schema):
    labels = {entry['id']: set(entry['subtypes']) for entry in schema['labels']}
    ids, texts, families = set(), {}, {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('INVALID_ROW')
        ident, text, label = (row.get(key) for key in ('id', 'text', 'intent_label'))
        family, split = row.get('family_id'), row.get('split')
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError('INVALID_OR_DUPLICATE_ID')
        ids.add(ident)
        if not isinstance(text, str) or not normalized_text(text):
            raise ValueError('EMPTY_TEXT')
        if not isinstance(label, str) or label not in labels or row.get('subtype') not in labels[label]:
            raise ValueError('INVALID_LABEL_OR_SUBTYPE')
        if split not in {'LIBRARY', 'DEVELOPMENT', 'REGRESSION'} or not isinstance(family, str) or not family:
            raise ValueError('INVALID_SPLIT_OR_FAMILY')
        if row.get('linguistic_form') not in {'ACCENTED', 'UNACCENTED', 'ABBREVIATED', 'TYPO'}:
            raise ValueError('INVALID_LINGUISTIC_FORM')
        components = row.get('component_intents')
        if not isinstance(components, list) or any(not isinstance(c, str) for c in components):
            raise ValueError('INVALID_COMPONENTS')
        if label == 'MIXED':
            if len(set(components)) < 2 or len(set(components)) != len(components) or not set(components) <= labels.keys() - {'MIXED'}:
                raise ValueError('INVALID_MIXED_COMPONENTS')
        elif components:
            raise ValueError('NON_MIXED_COMPONENTS')
        key = normalized_text(text)
        annotation = (split, label, family)
        if key in texts and texts[key] != annotation:
            raise ValueError('TEXT_LEAKAGE_OR_CONFLICT: ' + ident)
        if family in families and families[family] != (split, label):
            raise ValueError('FAMILY_LEAKAGE_OR_CONFLICT: ' + ident)
        texts[key], families[family] = annotation, (split, label)


def validate_dataset(directory, schema_path):
    directory, schema_path = Path(directory), Path(schema_path)
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if schema['label_schema_version'] != manifest['label_schema_version']:
        raise ValueError('SCHEMA_VERSION_MISMATCH')
    if hashlib.sha256(schema_path.read_bytes()).hexdigest() != manifest['label_schema_sha256']:
        raise ValueError('SCHEMA_CHECKSUM_MISMATCH')
    sets = {}
    for split, name in [('LIBRARY', 'library.jsonl'), ('DEVELOPMENT', 'development.jsonl')]:
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['files'][name]['sha256']:
            raise ValueError('DATASET_CHECKSUM_MISMATCH: ' + name)
        sets[split] = read_rows(path)
        if len(sets[split]) != manifest['files'][name]['rows'] or any(r['split'] != split for r in sets[split]):
            raise ValueError('ROW_COUNT_OR_SPLIT_MISMATCH')
    validate_rows(sets['LIBRARY'] + sets['DEVELOPMENT'], schema)
    by_label, by_subtype = defaultdict(set), defaultdict(set)
    for row in sets['LIBRARY']:
        by_label[row['intent_label']].add(row['family_id'])
        by_subtype[row['intent_label'], row['subtype']].add(row['family_id'])
    for entry in schema['labels']:
        label = entry['id']
        if len(by_label[label]) < 20 or sum(r['intent_label'] == label for r in sets['DEVELOPMENT']) < 10:
            raise ValueError('INSUFFICIENT_LABEL_COVERAGE: ' + label)
        if any(len(by_subtype[label, subtype]) < 3 for subtype in entry['subtypes']):
            raise ValueError('INSUFFICIENT_SUBTYPE_COVERAGE: ' + label)
    return dict(library_rows=len(sets['LIBRARY']), development_rows=len(sets['DEVELOPMENT']),
                library_seed_families=sum(map(len, by_label.values())),
                families_per_label={k: len(v) for k, v in sorted(by_label.items())},
                blind_acceptance_available=False, approval_status=manifest['approval_status'])
