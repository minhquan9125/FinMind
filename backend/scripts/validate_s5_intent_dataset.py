"""Validate S5-WBS03.2 data offline; never embed test questions or call services."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / 'docs/sprint5/intent-labels.v1.json'
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
LABELS = {item['id'] for item in SCHEMA['labels']}
BASE_LABELS = LABELS - {'MIXED'}
FORMS = {'ACCENTED', 'UNACCENTED', 'ABBREVIATED'}


def normalized(text):
    folded = unicodedata.normalize('NFKD', text.lower().replace('đ', 'd'))
    return ' '.join(re.findall(r'[a-z0-9]+', ''.join(c for c in folded if not unicodedata.combining(c))))


def validate_rows(rows):
    errors, ids, texts, families = [], set(), {}, {}
    required = set(SCHEMA['annotation_fields_proposed']) | {'family_id', 'linguistic_form'}
    for item in rows:
        ident = item.get('id', '<missing>')
        def error(code):
            errors.append(f'{ident}: {code}')
        if required - item.keys():
            error('MISSING_FIELDS')
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            error('DUPLICATE_ID_OR_INVALID_ID')
        ids.add(ident)
        label, status, split = (item.get(k) for k in ('intent_label', 'annotation_status', 'split'))
        if status not in SCHEMA['annotation_statuses'] or (status == 'LABELED' and label not in LABELS) or (status != 'LABELED' and label is not None):
            error('STATUS_LABEL')
        if split not in {'LIBRARY', 'TEST'}:
            error('SPLIT')
        if split == 'LIBRARY' and status != 'LABELED':
            error('LIBRARY_UNLABELED')
        if item.get('label_schema_version') != SCHEMA['label_schema_version']:
            error('SCHEMA_VERSION')
        if item.get('scope_status') not in SCHEMA['scope_statuses']:
            error('SCOPE_STATUS')
        if item.get('linguistic_form') not in FORMS:
            error('LINGUISTIC_FORM')
        sources = item.get('source_types')
        if not isinstance(sources, list) or any(s not in SCHEMA['source_types'] for s in sources) or len(sources) != len(set(sources)):
            error('SOURCE_TYPES')
        components = item.get('component_intents')
        if label == 'MIXED':
            if not isinstance(components, list) or len(set(components)) < 2 or len(components) != len(set(components)) or not set(components) <= BASE_LABELS:
                error('MIXED_COMPONENTS')
        elif components != []:
            error('NON_MIXED_COMPONENTS')
        text = item.get('text')
        if not isinstance(text, str) or not normalized(text):
            error('EMPTY_TEXT')
        else:
            key = normalized(text)
            if key in texts:
                old_split, old_label = texts[key]
                if old_split != split:
                    error('TEXT_LEAKAGE')
                elif old_label != label:
                    error('CONFLICTING_LABEL')
            texts[key] = (split, label)
        family = item.get('family_id')
        if not isinstance(family, str) or not family.strip():
            error('FAMILY_ID')
        elif family in families and families[family] != (split, label):
            error('FAMILY_LEAKAGE_OR_LABEL_CONFLICT')
        families[family] = (split, label)
        if any(not isinstance(item.get(k), str) or not item[k].strip() for k in ('operation', 'annotation_note')):
            error('MISSING_ANNOTATION_REASON')
    return errors


def validate_dataset(directory):
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    rows, errors = [], []
    for split, filename in [('LIBRARY', 'library.jsonl'), ('TEST', 'test.jsonl')]:
        items = [json.loads(line) for line in (directory / filename).read_text(encoding='utf-8').splitlines() if line.strip()]
        if any(item.get('split') != split for item in items):
            errors.append(f'{filename}: FILE_SPLIT_MISMATCH')
        if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != manifest['files'][filename]['sha256']:
            errors.append(f'{filename}: CHECKSUM_MISMATCH')
        if len(items) != manifest['files'][filename]['rows']:
            errors.append(f'{filename}: ROW_COUNT_MISMATCH')
        rows.extend(items)
    errors.extend(validate_rows(rows))
    if hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest() != manifest['label_schema_sha256']:
        errors.append('LABEL_SCHEMA_CHECKSUM_MISMATCH')
    # Definition examples have already been reviewed: do not pass them off as heldout.
    definitions = {normalized(label['example']) for label in SCHEMA['labels']}
    definitions.update(normalized(p[s]['text']) for p in SCHEMA['boundary_examples']['pairs'] for s in ('a', 'b'))
    definitions.update(normalized(item['text']) for item in SCHEMA['annotation_examples']['items'])
    for item in rows:
        if item['split'] == 'TEST' and normalized(item['text']) in definitions:
            errors.append(f"{item['id']}: DEFINITION_EXAMPLE_IN_TEST")
    by_id = {r['id']: r for r in rows}
    for contrast in manifest.get('contrast_sets', []):
        members = [by_id.get(ident) for ident in contrast['ids']]
        if len(members) < 2 or any(m is None or m['split'] != 'TEST' for m in members):
            errors.append(f"{contrast['id']}: INVALID_CONTRAST_MEMBERS")
        elif len({m['intent_label'] for m in members}) < 2:
            errors.append(f"{contrast['id']}: CONTRAST_NEEDS_DIFFERENT_LABELS")
    summary = {}
    for split in ('LIBRARY', 'TEST'):
        subset = [r for r in rows if r['split'] == split]
        counts = Counter(r['intent_label'] for r in subset if r['intent_label'])
        summary[split.lower() + '_rows'] = len(subset)
        summary[split.lower() + '_labels'] = dict(sorted(counts.items()))
        if set(counts) != LABELS:
            errors.append(f'{split}: MISSING_LABEL_COVERAGE')
        for label in LABELS:
            if {r['linguistic_form'] for r in subset if r['intent_label'] == label} != FORMS:
                errors.append(f'{split}/{label}: MISSING_FORM_COVERAGE')
    summary['test_unlabeled_rows'] = sum(r['split'] == 'TEST' and r['intent_label'] is None for r in rows)
    summary['dataset_version'] = manifest['dataset_version']
    summary['approval'] = manifest['approval_status']
    summary['classification_accuracy_measured'] = False
    return errors, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'docs/sprint5/intent-dataset-v1')
    args = parser.parse_args()
    errors, summary = validate_dataset(args.dataset)
    print(json.dumps(dict(valid=not errors, errors=errors, summary=summary), ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
