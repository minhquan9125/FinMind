"""Build JSONL from manually authored v2 seed families; never call an encoder."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_v2_dataset import validate_rows, validate_dataset

DATA = ROOT / 'docs/sprint5/intent-v2'
SCHEMA = ROOT / 'docs/sprint5/intent-labels.v2.json'


def unaccented(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.replace('đ', 'd').replace('Đ', 'D'))
                   if not unicodedata.combining(c))


def prepare():
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    sets, counters = {'LIBRARY': [], 'DEVELOPMENT': []}, Counter()
    for filename in ['library-authoring.txt', 'development-authoring.txt']:
        split = label = None
        for line in (DATA / filename).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            header = re.fullmatch(r'\[(LIBRARY|DEVELOPMENT):([A-Z_]+)\]', line)
            if header:
                split, label = header.groups()
                continue
            if split is None:
                raise ValueError('MISSING_SECTION: ' + filename)
            parts = [p.strip() for p in line.split(' | ')]
            if len(parts) not in (2, 3):
                raise ValueError('INVALID_AUTHORING_LINE: ' + line)
            subtype, text = parts[:2]
            components = parts[2].split(',') if len(parts) == 3 else []
            counters[split, label] += 1
            prefix = 'L2' if split == 'LIBRARY' else 'D2'
            family = f'{prefix}-{label}-{counters[split, label]:03}'
            variants = [('ACCENTED', text)]
            if split == 'LIBRARY':
                variants.append(('UNACCENTED', unaccented(text).lower()))
                abbreviated = text
                for phrase, alias in [('lợi nhuận sau thuế', 'LNST'), ('doanh thu', 'DT'),
                                      ('báo cáo tài chính', 'BCTC'), ('báo cáo thường niên', 'BCTN'),
                                      ('Tổng giám đốc', 'TGĐ'), ('Hội đồng quản trị', 'HĐQT')]:
                    abbreviated = re.sub(re.escape(phrase), alias, abbreviated, flags=re.IGNORECASE)
                if abbreviated != text:
                    variants.append(('ABBREVIATED', abbreviated))
                typo = text.replace('cổ phiếu', 'cổ phiêu').replace('doanh nghiệp', 'doanh ngiệp')
                if typo != text and counters[split, label] % 3 == 0:
                    variants.append(('TYPO', typo))
            for index, (form, variant) in enumerate(variants):
                sets[split].append(dict(id=f'{family}-{index}', text=variant, family_id=family,
                    intent_label=label, component_intents=components, subtype=subtype, split=split,
                    linguistic_form=form, annotation_status='LABELED', scope_status='NOT_EVALUATED',
                    source_types=[], operation=subtype, label_schema_version=schema['label_schema_version'],
                    annotation_note='Synthetic intent scenario; no factual answer asserted.'))
    validate_rows(sets['LIBRARY'] + sets['DEVELOPMENT'], schema)
    manifest = dict(dataset_version='s5-intent-dataset-v2-owner-draft1',
        label_schema_version=schema['label_schema_version'], label_schema_sha256=hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
        approval_status='OWNER_AUTHORIZED_PENDING_TEAM_REVIEW', blind_acceptance=False,
        development_provenance='Separately authored by a test agent without reading library; not independent human blind acceptance.',
        variant_policy='All variants of one curated seed stay in the same family and split.', files={})
    for split, name in [('LIBRARY', 'library.jsonl'), ('DEVELOPMENT', 'development.jsonl')]:
        raw = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in sets[split]).encode('utf-8')
        path = DATA / name
        if path.exists() and path.read_bytes() != raw:
            raise FileExistsError('Version the dataset instead of overwriting: ' + str(path))
        path.write_bytes(raw)
        manifest['files'][name] = dict(rows=len(sets[split]), sha256=hashlib.sha256(raw).hexdigest())
    (DATA / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return validate_dataset(DATA, SCHEMA)


if __name__ == '__main__':
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
