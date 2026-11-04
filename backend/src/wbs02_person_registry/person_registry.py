"""Persistent Person identity and review queue for WBS02 envelopes."""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from collections import defaultdict
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import validate_envelope
from .entities import _key, normalize
from .person_role_rules import extract_record, name_spans


SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE person (
    entity_id TEXT PRIMARY KEY, identity_key TEXT NOT NULL UNIQUE,
    canonical_name TEXT NOT NULL, aliases TEXT NOT NULL
);
CREATE TABLE source (
    source_id TEXT PRIMARY KEY, pin TEXT NOT NULL, text TEXT NOT NULL
);
CREATE TABLE mention (
    mention_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(source_id),
    start INTEGER NOT NULL, end INTEGER NOT NULL, raw_name TEXT NOT NULL,
    hints TEXT NOT NULL, UNIQUE(source_id, start, end)
);
CREATE TABLE decision (
    seq INTEGER PRIMARY KEY, mention_id TEXT NOT NULL REFERENCES mention(mention_id),
    action TEXT NOT NULL CHECK (action IN ('new','link','reject','reopen','seed')),
    person_id TEXT REFERENCES person(entity_id), details TEXT NOT NULL
);
CREATE INDEX decision_mention ON decision(mention_id, seq);
CREATE VIEW latest AS SELECT d.* FROM decision d JOIN (
    SELECT mention_id, MAX(seq) AS seq FROM decision GROUP BY mention_id
) m USING (mention_id, seq);
PRAGMA user_version = 1;
PRAGMA application_id = 1346720338;
COMMIT;
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def open_store(path, create=False):
    path = Path(path).resolve()
    mode = 'rwc' if create else 'rw'
    conn = sqlite3.connect(f'{path.as_uri()}?mode={mode}', uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        if create and version == 0:
            require(not conn.execute('SELECT 1 FROM sqlite_master LIMIT 1').fetchone(), 'Database is not an empty Person store')
            try:
                conn.executescript(SCHEMA)
            except sqlite3.OperationalError:
                # Another process may have completed initialization under the write lock.
                conn.rollback()
                if conn.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise
        require(conn.execute('PRAGMA user_version').fetchone()[0] == 1
                and conn.execute('PRAGMA application_id').fetchone()[0] == 1346720338, 'Unsupported Person store')
        return conn
    except BaseException:
        conn.close()
        raise


@contextmanager
def transaction(conn, write=False):
    with conn:
        conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield


def source_rows(payload):
    validate_envelope(payload)
    documents = {d['document_id']: d for d in payload['documents']}
    rows = {}
    for chunk in payload['chunks']:
        key = chunk['document_id'], chunk['chunk_id']
        doc = documents[key[0]]
        pin = {k: chunk[k] for k in ('document_id', 'document_version', 'chunk_id', 'locator')}
        pin.update(corpus_id=payload['corpus_id'], dataset_version=payload['dataset_version'],
                   source_uri=doc.get('source_uri', doc.get('source_path')), source_sha256=doc['source_sha256'],
                   content_hash=digest(chunk['text']))
        sid = digest(packed([pin[k] for k in ('corpus_id', 'document_id', 'document_version', 'chunk_id')]))
        rows[key] = sid, pin, chunk['text']
    return rows


def check_source(conn, row):
    sid, pin, text = row
    saved = conn.execute('SELECT pin, text FROM source WHERE source_id=?', (sid,)).fetchone()
    if saved is not None:
        original = json.loads(saved['pin'])
        # An index rebuild can change its source URI while retaining the identical snapshot.
        release_fields = {'dataset_version', 'source_uri'} if original['dataset_version'] != pin['dataset_version'] else set()
        require(saved['text'] == text and all(original.get(k) == pin.get(k) for k in (original.keys() | pin.keys()) - release_fields),
                'Conflicting text or locator for pinned snapshot')
    return saved is not None


def put_source(conn, row):
    if not check_source(conn, row):
        sid, pin, text = row
        conn.execute('INSERT INTO source VALUES (?,?,?)', (sid, packed(pin), text))


def put_mention(conn, row, start, end, hints):
    sid, _, text = row
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Invalid Person span')
    raw = text[start:end]
    require(nonblank(raw), 'Blank Person span')
    mid = 'pm:' + digest(packed([sid, start, end]))
    count = conn.execute('INSERT OR IGNORE INTO mention VALUES (?,?,?,?,?,?)',
                         (mid, sid, start, end, raw, packed(hints))).rowcount
    if not count and hints:
        saved = conn.execute('SELECT hints FROM mention WHERE mention_id=?', (mid,)).fetchone()['hints']
        merged = packed({**hints, **json.loads(saved)})
        if merged != saved:
            conn.execute('UPDATE mention SET hints=? WHERE mention_id=?', (merged, mid))
    return mid, count


def observations(payload, sources, company_map=None, proposals=None):
    """Collect review candidates from real source spans and optional WBS02 proposals."""
    company_map = {} if company_map is None else company_map
    require(isinstance(company_map, dict) and all(nonblank(k) and nonblank(v) for k, v in company_map.items()),
            'Company map must map document_id to canonical Company ID')
    require(proposals is None or isinstance(proposals, list), 'Proposals must be a list')
    found = defaultdict(dict)
    people = {e['entity_id'] for e in payload['entities'] if e['entity_type'] == 'Person'}
    supplied = [m for m in payload['mentions'] if m['entity_id'] in people]
    for proposal in (proposals or []):
        require(isinstance(proposal, dict) and proposal.get('entity_type') == 'Person', 'Expected a Person proposal')
        supplied.append(proposal)
    for item in supplied:
        key = item.get('document_id'), item.get('chunk_id')
        require(key in sources, 'Unknown proposal chunk')
        start, end = item.get('start'), item.get('end')
        _, pin, text = sources[key]
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(text) and nonblank(text[start:end]), 'Invalid proposal span')
        require(item.get('document_version', pin['document_version']) == pin['document_version'], 'Proposal snapshot version mismatch')
        require(item.get('content_hash', pin['content_hash']) == pin['content_hash'], 'Proposal source hash mismatch')
        context = item.get('context', {})
        require(isinstance(context, dict) and all(nonblank(v) for v in context.values()), 'Invalid proposal context')
        hints = dict(context)
        previous = found[key].get((start, end), {})
        require(all(k not in previous or previous[k] == v for k, v in hints.items()), 'Conflicting Person proposal context')
        found[key][start, end] = {**previous, **hints}
    for key, (_, pin, text) in sources.items():
        issuer = company_map.get(key[0])
        body_start = pin['locator'].get('text_start', 0)
        body = text[body_start:]
        spans = found[key]
        for start, end in name_spans(body):
            span = start + body_start, end + body_start
            if not any(a < span[1] and b > span[0] for a, b in spans):
                spans[span] = {'issuer_company_id': issuer} if issuer else {}
        if issuer:
            header = re.match(r'([A-Z0-9]{2,8}) \| Báo cáo thường niên ', text)
            rules = extract_record({'text': body, 'document_id': key[0], 'page': pin['locator']['page']},
                                   symbol=header.group(1) if header else issuer, source_kind='annual_report')
            for candidate in rules['candidates']:
                name = candidate['name_span']
                span = name['start'] + body_start, name['end'] + body_start
                if span in spans:
                    spans[span].setdefault('company_id', issuer)
                    spans[span].setdefault('position', candidate['position_raw'])
    return found


def ingest(conn, payload, company_map=None, proposals=None):
    sources = source_rows(payload)
    found = observations(payload, sources, company_map, proposals)
    added = 0
    with transaction(conn, write=True):
        for key, row in sources.items():
            put_source(conn, row)
            for (start, end), hints in found[key].items():
                _, count = put_mention(conn, row, start, end, hints)
                added += count
    return {'documents': len(payload['documents']), 'chunks': len(sources), 'added': added, **status(conn)}


def quote_ref(row, start, end):
    _, pin, text = row
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Invalid evidence span')
    return {**pin, 'start': start, 'end': end, 'quote': text[start:end]}


def check_ref(ref, sources):
    row = sources.get((ref['document_id'], ref['chunk_id']))
    require(row is not None, 'Seed proof chunk missing')
    actual = quote_ref(row, ref['start'], ref['end'])
    require(all(ref.get(k) == actual[k] for k in ('document_version', 'source_uri', 'content_hash', 'quote'))
            and ref.get('pdf_page') == actual['locator']['page'], 'Seed proof does not match pinned source')
    return row


def add_decision(conn, mid, action, eid, details):
    if eid is not None:
        overlap = conn.execute('SELECT 1 FROM mention target JOIN mention other USING(source_id) '
                               'JOIN latest l ON l.mention_id=other.mention_id WHERE target.mention_id=? '
                               'AND other.mention_id<>target.mention_id AND other.start<target.end AND other.end>target.start '
                               'AND l.person_id IS NOT NULL LIMIT 1', (mid,)).fetchone()
        require(overlap is None, 'Approved Person spans overlap in the same source chunk')
    details = dict(details, reviewed_at=datetime.now(timezone.utc).isoformat())
    conn.execute('INSERT INTO decision(mention_id,action,person_id,details) VALUES (?,?,?,?)',
                 (mid, action, eid, packed(details)))


def seed(conn, registry, payload):
    sources = source_rows(payload)
    require(isinstance(registry, list), 'Seed registry must be a list')
    added = 0
    with transaction(conn, write=True):
        for person in registry:
            require(person.get('entity_type') == 'Person' and person.get('verified') is True, 'Unverified Person seed')
            eid, identity, name = (person.get(k) for k in ('entity_id', 'identity_key', 'canonical_name'))
            require(all(nonblank(x) for x in (eid, identity, name)) and eid.startswith('PER-'), 'Invalid seed identity')
            aliases, refs = person.get('aliases'), person.get('source_refs')
            require(isinstance(aliases, list) and all(nonblank(x) for x in aliases), 'Invalid seed aliases')
            require(isinstance(refs, list) and len({r['role']['document_id'] for r in refs}) >= 2, 'Seed requires two distinct verified source documents')
            company_id, position = (person.get('context', {}).get(k) for k in ('company_id', 'position'))
            require(nonblank(company_id) and nonblank(position) and nonblank(person.get('verification_basis')), 'Seed context and rationale required')
            existing = conn.execute('SELECT identity_key,canonical_name,aliases FROM person WHERE entity_id=?', (eid,)).fetchone()
            values = identity, name, packed(aliases)
            require(existing is None or tuple(existing) == values, 'Seed Person ID conflicts with stored identity')
            conn.execute('INSERT OR IGNORE INTO person VALUES (?,?,?,?)', (eid, *values))
            for entry in refs:
                role, identity_ref = entry['role'], entry['identity_evidence']
                row = check_ref(role, sources)
                identity_row = check_ref(identity_ref, sources)
                require(identity_ref['document_id'] == role['document_id'], 'Seed role and biography documents differ')
                offset = role['quote'].find(name)
                require(offset >= 0 and role['quote'].count(name) == 1, 'Seed requires a unique exact name span in the role quote')
                put_source(conn, row)
                put_source(conn, identity_row)
                start = role['start'] + offset
                mid, _ = put_mention(conn, row, start, start + len(name), {})
                previous = conn.execute('SELECT person_id FROM decision WHERE mention_id=? ORDER BY seq LIMIT 1', (mid,)).fetchone()
                if previous is not None:
                    require(previous['person_id'] == eid, 'Seed mention already has a different decision')
                    continue  # Replay must not undo later review or reopening.
                details = dict(reviewer='WBS02 source audit', reason=person['verification_basis'],
                               company_id=company_id, position=position, report_year=entry.get('report_year'),
                               evidence=quote_ref(row, role['start'], role['end']),
                               identity_evidence=quote_ref(identity_row, identity_ref['start'], identity_ref['end']))
                add_decision(conn, mid, 'seed', eid, details)
                added += 1
    return {'approved_added': added, **status(conn)}


def review(conn, mention_id, action, reviewer, reason, *, person_id=None, canonical_name=None,
           company_id=None, position=None, as_of=None, valid_from=None, valid_to=None, report_year=None,
           evidence_start=None, evidence_end=None, expected_revision=0):
    require(nonblank(reviewer) and nonblank(reason), 'Reviewer and rationale required')
    require(action in {'new', 'link', 'reject', 'reopen'}, 'Unknown review action')
    require((evidence_start is None) == (evidence_end is None), 'Provide both evidence offsets')
    require(type(expected_revision) is int and expected_revision >= 0, 'Invalid decision revision')
    dates = [date.fromisoformat(d) if d is not None else None for d in (as_of, valid_from, valid_to)]
    require(all(d is None or d.isoformat() == raw for d, raw in zip(dates, (as_of, valid_from, valid_to))), 'Dates must use YYYY-MM-DD')
    require(not (dates[1] and dates[2]) or dates[1] <= dates[2], 'Invalid role date interval')
    require(report_year is None or type(report_year) is int and 1900 <= report_year <= 9999, 'Invalid report year')
    with transaction(conn, write=True):
        row = conn.execute('SELECT m.*,s.pin,s.text,l.action,l.seq FROM mention m JOIN source s USING(source_id) '
                           'LEFT JOIN latest l USING(mention_id) WHERE mention_id=?', (mention_id,)).fetchone()
        require(row is not None, 'Unknown Person mention')
        require((row['seq'] or 0) == expected_revision, 'Stale decision revision: reload pending or export before review')
        is_pending = row['action'] in (None, 'reopen')
        require(is_pending == (action != 'reopen'), 'Decision conflict: reopen a reviewed mention before changing it')
        if action in {'new', 'link'}:
            require(nonblank(company_id) and nonblank(position), 'Confirmed company and position required')
        if action == 'new':
            require(nonblank(canonical_name) and person_id is None, 'New identity requires a canonical name only')
            person_id = 'PER-' + uuid.uuid4().hex
            conn.execute('INSERT INTO person VALUES (?,?,?,?)', (person_id, 'person:' + person_id, canonical_name.strip(), '[]'))
        elif action == 'link':
            require(canonical_name is None and conn.execute('SELECT 1 FROM person WHERE entity_id=?', (person_id,)).fetchone(), 'Unknown canonical Person ID')
        else:
            require(all(v is None for v in (person_id, canonical_name, company_id, position, as_of, valid_from, valid_to, report_year)), 'Unexpected identity/context on reject or reopen')
        start = 0 if evidence_start is None else evidence_start
        end = len(row['text']) if evidence_end is None else evidence_end
        ref = quote_ref((row['source_id'], json.loads(row['pin']), row['text']), start, end)
        require(start <= row['start'] < row['end'] <= end, 'Review evidence must cover the mention')
        details = dict(reviewer=reviewer.strip(), reason=reason.strip(), company_id=company_id, position=position,
                       report_year=report_year, as_of=as_of, valid_from=valid_from, valid_to=valid_to, evidence=ref)
        add_decision(conn, mention_id, action, person_id, details)
    return person_id


def status(conn):
    row = conn.execute("SELECT COUNT(*) AS mentions, COUNT(CASE WHEN l.person_id IS NOT NULL THEN 1 END) AS approved, "
                       "COUNT(CASE WHEN l.action IS NULL OR l.action='reopen' THEN 1 END) AS pending, "
                       "COUNT(CASE WHEN l.action='reject' THEN 1 END) AS rejected FROM mention LEFT JOIN latest l USING(mention_id)").fetchone()
    return {**dict(row), 'persons': conn.execute('SELECT COUNT(*) FROM person').fetchone()[0]}


def persons_view(conn):
    people = {}
    for r in conn.execute('SELECT * FROM person ORDER BY entity_id'):
        people[r['entity_id']] = dict(entity_id=r['entity_id'], entity_type='Person', identity_key=r['identity_key'],
            canonical_name=r['canonical_name'], aliases=sorted(set(json.loads(r['aliases']) + [r['canonical_name']])), contexts=[])
    for r in conn.execute('SELECT l.person_id,l.details,m.mention_id,m.raw_name FROM latest l JOIN mention m USING(mention_id) '
                          'WHERE l.person_id IS NOT NULL ORDER BY m.mention_id'):
        person = people[r['person_id']]
        person['contexts'].append({'mention_id': r['mention_id'], **json.loads(r['details'])})
        person['aliases'].append(r['raw_name'])
    for person in people.values():
        person['aliases'] = sorted(set(person['aliases']))
        person['verified'] = bool(person['contexts'])
    return people


def export_registry(conn):
    with transaction(conn):
        persons = list(persons_view(conn).values())
        decisions = [dict(seq=r['seq'], mention_id=r['mention_id'], action=r['action'], person_id=r['person_id'], **json.loads(r['details']))
                     for r in conn.execute('SELECT * FROM decision ORDER BY seq')]
    return {'registry_schema_version': 1, 'persons': persons, 'decisions': decisions}


def pending(conn):
    with transaction(conn):
        aliases = defaultdict(set)
        for person in persons_view(conn).values():
            if person['verified']:
                for alias in person['aliases']:
                    aliases[_key(alias)].add(person['entity_id'])
        items = []
        rows = conn.execute("SELECT m.*,s.pin,s.text,l.seq FROM mention m JOIN source s USING(source_id) "
                            "LEFT JOIN latest l USING(mention_id) WHERE l.action IS NULL OR l.action='reopen' ORDER BY m.mention_id")
        for row in rows:
            ref = quote_ref((row['source_id'], json.loads(row['pin']), row['text']),
                            max(0, row['start'] - 100), min(len(row['text']), row['end'] + 180))
            items.append(dict(mention_id=row['mention_id'], raw_name=row['raw_name'], start=row['start'], end=row['end'],
                              decision_revision=row['seq'] or 0,
                              resolution_status='unresolved', candidate_person_ids=sorted(aliases[_key(row['raw_name'])]),
                              hints=json.loads(row['hints']), source=ref))
    return items


def resolve_payload(conn, payload, company_registry=None, proposals=None):
    sources = source_rows(payload)
    require(not payload['relations'], 'Resolve Person before relation extraction/review')
    require(company_registry is None or isinstance(company_registry, list) and all(r.get('entity_type') == 'Company' for r in company_registry),
            'Provide Company-only registry to the legacy resolver')
    base = payload if payload['entities'] or payload['mentions'] else normalize(payload['chunks'], company_registry)
    entities = {e['entity_id']: e for e in base['entities'] if e['entity_type'] != 'Person'}
    mentions = [m for m in base['mentions'] if m['entity_id'] in entities]
    found = observations(payload, sources, proposals=proposals)
    with transaction(conn):
        people = persons_view(conn)
        for key, row in sources.items():
            sid, _, text = row
            check_source(conn, row)
            decisions = {(m['start'], m['end']): (m['action'], m['person_id']) for m in conn.execute(
                'SELECT m.start,m.end,l.action,l.person_id FROM mention m LEFT JOIN latest l USING(mention_id) WHERE m.source_id=?', (sid,))}
            approved = [span for span, (_, person_id) in decisions.items() if person_id is not None]
            all_spans = set(decisions) | set(found[key])
            for start, end in sorted(all_spans):
                action, person_id = decisions.get((start, end), (None, None))
                if action == 'reject':
                    continue
                if person_id is None and any(a < end and b > start for a, b in approved):
                    continue  # Prefer a reviewed exact span over overlapping detector guesses.
                raw = text[start:end]
                token = digest(packed([sid, start, end]))
                person = people.get(person_id)
                eid = person_id if person else 'ent:' + token
                require(eid not in entities or entities[eid]['entity_type'] == 'Person', 'Person ID collides with another entity type')
                if eid not in entities:
                    entities[eid] = dict(entity_id=eid, entity_type='Person', canonical_name=person['canonical_name'] if person else None,
                                         aliases=[], resolution_status='resolved' if person else 'unresolved',
                                         identity_key=person['identity_key'] if person else None, attributes={})
                entities[eid]['aliases'] = sorted(set(entities[eid]['aliases'] + [raw]))
                mentions.append(dict(mention_id='men:' + token, entity_id=eid, document_id=key[0], chunk_id=key[1],
                                     start=start, end=end, raw_name=raw))
    return validate_envelope({**payload, 'entities': list(entities.values()), 'mentions': mentions})


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig')) if path is not None else None


def save(path, data):
    with Path(path).open('x', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, help='Explicit local SQLite store path')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    commands.add_parser('status')
    bootstrap = commands.add_parser('seed')
    bootstrap.add_argument('--registry', required=True)
    bootstrap.add_argument('--input', required=True)
    scan = commands.add_parser('ingest')
    scan.add_argument('--input', required=True, help='WBS02 envelope JSON or inbox directory containing only envelope JSON files')
    scan.add_argument('--company-map')
    scan.add_argument('--proposals')
    for name in ('pending', 'export', 'resolve'):
        command = commands.add_parser(name)
        command.add_argument('--output', required=True)
        if name == 'resolve':
            command.add_argument('--input', required=True)
            command.add_argument('--companies')
            command.add_argument('--proposals')
    decide = commands.add_parser('review')
    decide.add_argument('--mention-id', required=True)
    decide.add_argument('--action', choices=('new', 'link', 'reject', 'reopen'), required=True)
    decide.add_argument('--reviewer', required=True)
    decide.add_argument('--reason', required=True)
    for field in ('person-id', 'canonical-name', 'company-id', 'position', 'as-of', 'valid-from', 'valid-to'):
        decide.add_argument('--' + field)
    for field in ('report-year', 'evidence-start', 'evidence-end'):
        decide.add_argument('--' + field, type=int)
    decide.add_argument('--expected-revision', type=int, default=0)
    args = parser.parse_args(argv)
    try:
        with closing(open_store(args.db, create=args.command == 'init')) as conn:
            if args.command == 'seed':
                result = seed(conn, load(args.registry), load(args.input))
            elif args.command == 'ingest':
                path = Path(args.input)
                files = sorted(path.glob('*.json')) if path.is_dir() else [path]
                require(files and (not path.is_dir() or not args.proposals), 'Inbox must contain envelopes and use no shared proposal file')
                mapping = load(args.company_map)
                proposed = load(args.proposals)
                result = {'batches': [dict(file=f.name, **ingest(conn, load(f), mapping, proposed)) for f in files], **status(conn)}
            elif args.command == 'review':
                fields = {k: v for k, v in vars(args).items() if k not in ('db', 'command')}
                result = {'person_id': review(conn, **fields), **status(conn)}
            elif args.command in ('pending', 'export', 'resolve'):
                if args.command == 'pending':
                    data = pending(conn)
                elif args.command == 'export':
                    data = export_registry(conn)
                else:
                    data = resolve_payload(conn, load(args.input), load(args.companies), load(args.proposals))
                save(args.output, data)
                result = {'output': args.output, **status(conn)}
            else:
                result = status(conn)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, AttributeError) as error:
        print(f'Person registry: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
