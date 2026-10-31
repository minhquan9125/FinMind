"""Contract JSON có kiểm tra nguồn và điều kiện xuất quan hệ."""
import json
import hashlib
import math
import re
import unicodedata
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_VERSION = '2.1.0'
SCHEMA = json.loads(Path(__file__).with_name('contract.schema.json').read_text('utf-8'))
_validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
_chunk_validator = Draft202012Validator({'$ref': '#/$defs/chunk', '$defs': SCHEMA['$defs']}, format_checker=FormatChecker())
_legacy_schema = json.loads(Path(__file__).with_name('contract.v1.schema.json').read_text('utf-8'))
_legacy_validator = Draft202012Validator(_legacy_schema, format_checker=FormatChecker())
_directions = {
    'OWNS_SHARES': ({'Company', 'Person'}, {'Company'}),
    'HAS_SUBSIDIARY': ({'Company'}, {'Company'}),
    'HAS_ASSOCIATE': ({'Company'}, {'Company'}),
    'COOPERATES_WITH': ({'Company'}, {'Company'}),
    'HOLDS_ROLE': ({'Person'}, {'Company'}),
    'APPOINTS': ({'Company'}, {'Person'}),
    'DISMISSES': ({'Company'}, {'Person'}),
    'INVOLVES': ({'Event'}, {'Company', 'Person'})}
_attributes = {'OWNS_SHARES': ['ownership_percent', 'holding_basis'],
    'COOPERATES_WITH': ['cooperation_scope'],
    'HAS_SUBSIDIARY': ['consolidation_basis'], 'HAS_ASSOCIATE': ['accounting_basis'],
    'HOLDS_ROLE': ['position'], 'APPOINTS': ['position'], 'DISMISSES': ['position'],
    'INVOLVES': ['participant_role']}

def _require(condition, message):
    if not condition:
        raise ValueError(message)

def _nonblank(value):
    return isinstance(value, str) and bool(value.strip())

def _index(records, key, identical=False):
    result = {}
    for record in records:
        ident = key(record)
        _require(all(_nonblank(x) for x in ident) if isinstance(ident, tuple) else _nonblank(ident), 'Blank ID')
        _require(ident not in result or identical and result[ident] == record, 'Duplicate ID')
        result[ident] = record
    return result

def _day(value):
    if value is not None:
        _require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'Invalid day')
        date.fromisoformat(value)

def validate_chunk(chunk):
    """Giữ locator PDF cũ hoặc kiểm hash/span của chunk DB; không sửa đầu vào."""
    try:
        json.dumps(chunk, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as error:
        raise ValueError('Non-JSON or nonfinite chunk') from error
    error = next(_chunk_validator.iter_errors(chunk), None)
    if error:
        raise ValueError('Chunk schema: ' + error.message[:180])
    _require(all(_nonblank(chunk[k]) for k in ('document_id', 'document_version', 'chunk_id')), 'Blank chunk identity')
    loc = chunk['locator']
    _require(type(loc['page']) is int and loc['page'] >= 1, 'Physical page')
    if loc.get('kind') == 'db_text_span':
        _require(all(type(loc[k]) is int for k in ('section_index', 'char_start', 'char_end', 'text_start')), 'Integer DB offsets')
        _require(loc['char_start'] < loc['char_end'], 'DB span order')
        _require(loc['text_start'] + loc['char_end'] - loc['char_start'] == len(chunk['text']), 'DB body span/text mapping')
        actual = hashlib.sha256(chunk['text'].encode('utf-8')).hexdigest()
        _require(actual == loc['content_hash'], 'DB chunk content hash')
    else:
        box = loc['bbox']
        _require(chunk['chunk_id'] == loc['block_id'], 'Block identity')
        _require(all(type(x) is int or type(x) is float and math.isfinite(x) for x in box)
                 and box[0] <= box[2] and box[1] <= box[3], 'Invalid bbox')
    return chunk

def validate_envelope(payload):
    """Kiểm cấu trúc/nhất quán nguồn; không xác nhận sự thật ngoài đời."""
    try:
        json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as error:
        raise ValueError('Non-JSON or nonfinite input') from error
    error = next(_validator.iter_errors(payload), None)
    if error:
        raise ValueError('Schema: ' + error.message[:180])
    _require(_nonblank(payload['corpus_id']) and _nonblank(payload['dataset_version']), 'Blank corpus/version')
    documents = _index(payload['documents'], lambda x: x['document_id'])
    chunks = _index(payload['chunks'], lambda x: (x['document_id'], x['chunk_id']), True)
    entities = _index(payload['entities'], lambda x: x['entity_id'])
    _index(payload['mentions'], lambda x: x['mention_id'])
    _index(payload['relations'], lambda x: x['relation_id'])
    for d in documents.values():
        if d.get('source_kind') == 'db':
            _require(_nonblank(d['source_uri']), 'Blank DB source URI')
            _require(d['index_version_id'] == payload['dataset_version'], 'DB index/dataset version')
            continue
        _require(d['document_id'] == 'doc:' + d['source_sha256'], 'Document SHA identity')
        _require(d['document_version'] == d['extraction_sha256'], 'Extraction version')
        _require(_nonblank(d['source_path']) and _nonblank(d['extraction_path']), 'Blank source path')
    for c in chunks.values():
        validate_chunk(c)
        d = documents.get(c['document_id'])
        _require(d is not None and c['document_version'] == d['document_version'], 'Chunk document/version')
        _require((c['locator'].get('kind') == 'db_text_span') == (d.get('source_kind') == 'db'), 'Chunk/document source profile')
    for e in entities.values():
        _require(e['resolution_status'] != 'resolved' or _nonblank(e['identity_key']), 'Resolved identity key required')
        if e['entity_type'] == 'Event':
            a = e['attributes']
            _require(_nonblank(a.get('event_type')) and 'occurred_at' in a, 'Event attributes')
            _day(a['occurred_at'])
    for m in payload['mentions']:
        c = chunks.get((m['document_id'], m['chunk_id']))
        _require(m['entity_id'] in entities and c is not None, 'Mention reference')
        _require(type(m['start']) is int and type(m['end']) is int, 'Integer span')
        _require(0 <= m['start'] < m['end'] <= len(c['text'])
                 and c['text'][m['start']:m['end']] == m['raw_name'], 'Mention span')
    cooperation_keys = set()
    for r in payload['relations']:
        subject, target = entities.get(r['subject_id']), entities.get(r['object_id'])
        _require(subject is not None and target is not None and r['subject_id'] != r['object_id'], 'Relation endpoints')
        domains, ranges = _directions[r['relation_type']]
        _require(subject['entity_type'] in domains and target['entity_type'] in ranges, 'Relation direction')
        for ev in r['evidence']:
            c = chunks.get((ev['document_id'], ev['chunk_id']))
            _require(c is not None and _nonblank(ev['quote']) and ev['quote'] in c['text'], 'Evidence source/quote')
        t, a = r['temporal'], r['attributes']
        stamp = r['review']['reviewed_at']
        if stamp is not None:
            _require(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', stamp), 'Review timestamp with timezone required')
            datetime.fromisoformat(stamp)
        for value in t.values():
            _day(value)
        _require(not(t['valid_from'] and t['valid_to']) or t['valid_from'] <= t['valid_to'], 'Reversed interval')
        if r['relation_type'] == 'COOPERATES_WITH':
            _require(r['subject_id'] < r['object_id'], 'Cooperation uses sorted Company IDs; do not store reverse edge')
            scope = a.get('cooperation_scope')
            _require(scope is None or _nonblank(scope), 'Invalid cooperation scope')
            scope_key = ' '.join(unicodedata.normalize('NFC', scope).casefold().split()) if scope is not None else None
            key = (r['subject_id'], r['object_id'], scope_key, t['as_of'], t['valid_from'], t['valid_to'])
            _require(key not in cooperation_keys, 'Duplicate cooperation pair/scope/period; merge evidence')
            cooperation_keys.add(key)
        if 'ownership_percent' in a:
            p = a['ownership_percent']
            _require(type(p) is str and re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', p), 'Decimal percent string')
            _require(Decimal(p).is_finite() and Decimal(p) <= 100, 'Ownership range')
        if 'holding_basis' in a:
            _require(a['holding_basis'] in ('direct', 'indirect'), 'Holding basis')
        if r['review']['status'] != 'APPROVED':
            continue
        _require(not r.get('negated', False) and not r.get('conditional', False), 'Negated/conditional approval')
        _require(a.get('assertion_status') not in ('NEGATED', 'PLANNED', 'CONDITIONAL', 'UNCERTAIN'), 'Unconfirmed approval')
        _require(all(e['attributes'].get('assertion_status') not in ('NEGATED', 'PLANNED', 'CONDITIONAL', 'UNCERTAIN') for e in (subject, target)), 'Unconfirmed endpoint approval')
        _require(subject['resolution_status'] == target['resolution_status'] == 'resolved', 'Unresolved endpoints')
        _require(_nonblank(r['review']['reviewer']) and _nonblank(r['review']['reviewed_at']), 'Review attribution')
        _require(t['as_of'] is not None or t['valid_from'] is not None, 'Approved temporal basis')
        for field in _attributes[r['relation_type']]:
            _require(_nonblank(a.get(field)), 'Missing attribute: ' + field)
    return payload

def publishable_relations(payload):
    validate_envelope(payload)
    return [r for r in payload['relations'] if r['review']['status'] == 'APPROVED']

def migrate_v1(payload):
    """Chỉ đổi schema version/review labels; giữ ID, nguồn và trạng thái duyệt."""
    error = next(_legacy_validator.iter_errors(payload), None)
    if error:
        raise ValueError('Expected schema 1.0.0: ' + error.message[:180])
    result = deepcopy(payload)
    result['schema_version'] = '2.0.0'
    mapping = {'candidate': 'PENDING', 'approved': 'APPROVED', 'rejected': 'REJECTED'}
    for relation in result['relations']:
        relation['review']['status'] = mapping[relation['review']['status']]
    return validate_envelope(result)
