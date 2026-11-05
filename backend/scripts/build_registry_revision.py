"""Build a company-registry revision from its base file and a reviewed change list.

python -X utf8 backend/scripts/build_registry_revision.py backend/src/sprint4_runtime/company.registry.20261104.r2.changes.json
"""

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sprint4_runtime.entities import _registry, text_view


def identity_key(name):
    return 'name:' + ' '.join(re.sub(r'[^\w\s]', ' ', unicodedata.normalize('NFC', name).casefold()).split())


def apply_changes(base, changes):
    """Return the new registry rows; refuse an alias that already names another entity."""
    rows = json.loads(json.dumps(base))
    by_id = {row['entity_id']: row for row in rows}
    for change in changes['add_aliases']:
        row = by_id[change['entity_id']]
        row['aliases'] += [alias for alias in change['aliases'] if alias not in row['aliases']]
    for change in changes['remove_aliases']:
        row = by_id[change['entity_id']]
        row['aliases'] = [alias for alias in row['aliases'] if alias not in change['aliases']]
    key = lambda alias: text_view(alias)[0].strip()
    owners = {}
    for row in rows:
        for alias in [row['canonical_name'], *row['aliases']]:
            owners.setdefault(key(alias), set()).add(row['entity_id'])
    for entry in changes['add_entities']:
        ident = identity_key(entry['canonical_name'])
        entity_id = 'CMP-' + hashlib.sha256(('finmind-registry-r2|' + ident).encode()).hexdigest()[:20]
        if entity_id in by_id:
            raise ValueError('Entity already exists: ' + entity_id)
        row = {'entity_id': entity_id, 'entity_type': 'Company', 'canonical_name': entry['canonical_name'],
               'aliases': [entry['canonical_name'], *entry['aliases']], 'ticker_aliases': [],
               'identity_key': ident, 'verified': True}
        for alias in row['aliases']:
            if owners.get(key(alias), set()) - {entity_id}:
                raise ValueError('Alias already names another entity: ' + alias)
            owners.setdefault(key(alias), set()).add(entity_id)
        rows.append(row)
        by_id[entity_id] = row
    _registry(rows)  # the shared resolver's own validation
    return rows


def main():
    changes_path = Path(sys.argv[1])
    changes = json.loads(changes_path.read_text('utf-8'))
    base = json.loads((changes_path.parent / changes['base']).read_text('utf-8'))
    rows = apply_changes(base, changes)
    target = changes_path.parent / changes['result']
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(f'{target}: {len(rows)} rows')


if __name__ == '__main__':
    main()
