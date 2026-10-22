"""Link source metric names to the user's reviewed catalogue; never convert values.

Catalogue retention does not certify the API's source unit, scope or method.
This module is deliberately separate from the source chunker and frozen indices.
"""
import json
from pathlib import Path
import re
import unicodedata

DATA = Path(__file__).with_name('data') / 'reviewed_metric_links_v1.json'
RETAINED = frozenset({'Giữ', 'Giữ có điều kiện'})


def normalized_name(value):
    text = unicodedata.normalize('NFD', str(value or '').lower().replace('đ', 'd'))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return ' '.join(re.sub('[^a-z0-9]+', ' ', text).split())


def match_metric(source, criteria, override=None):
    """Return a reviewable link, refusing ambiguity and non-retained definitions."""
    if (source.get('industry_scope') not in {'BANK', 'TECH'}
            or source.get('section') not in {'BALANCE_SHEET', 'INCOME_STATEMENT', 'CASH_FLOW', 'RATIO'}
            or not source.get('code')):
        raise ValueError('Metric linking requires a supported industry, section and source code')
    candidates = []
    for target in criteria:
        if target['industry'] != source['industry_scope']:
            continue
        statement = {'BALANCE_SHEET': 'balance_sheet', 'INCOME_STATEMENT': 'income_statement',
                     'CASH_FLOW': 'cash_flow'}.get(source['section'])
        if override:
            matches = target['metric_id'] == override
        else:
            if statement and target['statement'] != statement:
                continue
            labels = [target['original_name'], target['chosen_name'], *target['aliases']]
            name = normalized_name(source.get('canonical_name'))
            matches = (normalized_name(source['code']) == normalized_name(target['metric_id'].split('.', 1)[-1])
                       or bool(name and name in {normalized_name(v) for v in labels if v}))
        if matches:
            candidates.append(target)
    # An explicit override must not silently fall back to an unrelated name match.
    retained = [c for c in candidates if c['review_decision'] in RETAINED and c['kind'] != 'derived']
    if len(retained) == 1:
        selected = retained[0]
        status = 'linked_with_conditions' if selected['review_decision'] == 'Giữ có điều kiện' else 'linked'
    else:
        selected = None
        status = 'ambiguous' if len(retained) > 1 else 'not_retained' if candidates else 'no_match'
    return {'status': status, 'target': selected,
            'candidates': [{'metric_id': c['metric_id'], 'name': c['chosen_name'],
                            'decision': c['review_decision'], 'sheet': c['sheet'], 'row': c['row']}
                           for c in candidates],
            'match_basis': 'explicit_concept_crosswalk' if override else 'exact_normalized_code_or_label',
            'source_unit_verified': False, 'value_conversion_allowed': False,
            'source_context_verified': False}


def load_metric_links(path=DATA):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data['schema_version'] != 'reviewed-metric-links-v1':
        raise ValueError('Unsupported reviewed metric link schema')
    links = {}
    for row in data['links']:
        key = (row['industry_scope'], row['section'], row['code'])
        if key in links:
            raise ValueError('Duplicate reviewed source metric identity')
        if row.get('target') and row['target']['review_decision'] not in RETAINED:
            raise ValueError('Non-retained catalogue metric cannot be activated')
        if row.get('target') and row['target']['kind'] == 'derived':
            raise ValueError('A derived metric cannot replace a reported source observation')
        links[key] = row
    return links


def get_metric_link(industry, section, code, *, links=None):
    """Look up BANK/TECH mapping without selecting by company or mutating numbers."""
    return (load_metric_links() if links is None else links).get((industry, section, code))
