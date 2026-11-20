"""WBS09: join extractor envelopes into one reviewed graph version.

Flow: contract envelopes (company / person-role / event extractors) ->
merge_envelopes (09.1 + 09.2) -> WBS06 ApprovalGate -> Sprint4GraphStore batch ->
reconcile Neo4j edges against the approved set -> publish only if every check
passes (09.3). Extractors, review store and graph store are reused, not rewritten.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unicodedata

from ..sprint4_runtime.contracts import validate_envelope
from .sprint4_store import _json

# Attributes that make two facts different statements rather than a conflict:
# two roles for one person at one company are both true.
IDENTITY_ATTRIBUTES = {
    'HOLDS_ROLE': ('position',), 'APPOINTS': ('position',), 'DISMISSES': ('position',),
    'COOPERATES_WITH': ('cooperation_scope',), 'INVOLVES': ('participant_role',),
}


def _sha(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _norm(value):
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split()) if isinstance(value, str) else value


def _fact_key(relation):
    attrs = relation['attributes']
    return _json([relation['relation_type'], relation['subject_id'], relation['object_id'],
                  relation['temporal'],
                  [_norm(attrs.get(k)) for k in IDENTITY_ATTRIBUTES.get(relation['relation_type'], ())]])


def _statement(relation):
    """Everything a relation claims, without its sources and review record."""
    return {k: relation[k] for k in ('relation_type', 'subject_id', 'object_id', 'attributes', 'temporal')}


def _union(records, key, label):
    merged = {}
    for record in records:
        ident = key(record)
        if ident in merged and merged[ident] != record:
            raise ValueError(f'{label} {ident} differs between envelopes')
        merged[ident] = record
    return merged


IDENTITY_FIELDS = ('entity_type', 'canonical_name', 'identity_key', 'resolution_status', 'attributes')


def _merge_entities(entities):
    """Same entity_id must mean the same identity. Aliases are per-document surface
    forms (e.g. TCB in the 2024 vs 2025 report), so they are unioned, not compared."""
    merged, conflicts = {}, set()
    for entity in entities:
        old = merged.get(entity['entity_id'])
        if old is None:
            merged[entity['entity_id']] = dict(entity, aliases=sorted(set(entity['aliases'])))
            continue
        if any(old[k] != entity[k] for k in IDENTITY_FIELDS):
            conflicts.add(entity['entity_id'])
        old['aliases'] = sorted(set(old['aliases']) | set(entity['aliases']))
    return merged, conflicts


def merge_envelopes(envelopes):
    """09.1 + 09.2: one envelope of APPROVED relations for one corpus/index, plus a report.

    Approved relations are never edited (WBS06 binds approval to their digest).
    Duplicates keep the smallest relation_id on the graph; the others stay listed
    in the report with their own sources. Disagreements go to WBS06, not to Neo4j.
    """
    if not envelopes:
        raise ValueError('At least one envelope is required')
    for payload in envelopes:
        validate_envelope(payload)
    scopes = {(p['schema_version'], p['corpus_id'], p['dataset_version']) for p in envelopes}
    if len(scopes) != 1:
        raise ValueError('Envelopes mix corpus/index versions; build one graph version per scope')
    schema_version, corpus_id, dataset_version = scopes.pop()

    documents = _union((d for p in envelopes for d in p['documents']), lambda d: d['document_id'], 'Document')
    chunks = _union((c for p in envelopes for c in p['chunks']),
                    lambda c: (c['document_id'], c['chunk_id']), 'Chunk')
    entities, entity_conflicts = _merge_entities(e for p in envelopes for e in p['entities'])

    report = {'input_relations': 0, 'not_approved': 0, 'conflicts': [], 'merged': []}
    by_id = {}
    for payload in envelopes:
        for relation in payload['relations']:
            report['input_relations'] += 1
            if relation['review']['status'] != 'APPROVED':
                report['not_approved'] += 1
                continue
            by_id.setdefault(relation['relation_id'], []).append(relation)

    candidates = []
    for rid, copies in sorted(by_id.items()):
        if len({_json(r) for r in copies}) > 1:
            # One extraction ID carrying two statements (e.g. two report years) is not mergeable.
            report['conflicts'].append({'reason': 'RELATION_ID_COLLISION', 'relation_ids': [rid],
                                        'statements': [_statement(r) for r in copies]})
            continue
        candidates.append(copies[0])

    groups = {}
    for relation in candidates:
        groups.setdefault(_fact_key(relation), []).append(relation)
    relations = []
    for _, group in sorted(groups.items()):
        ids = sorted(r['relation_id'] for r in group)
        if any(r['subject_id'] in entity_conflicts or r['object_id'] in entity_conflicts for r in group):
            report['conflicts'].append({'reason': 'ENTITY_CONFLICT', 'relation_ids': ids,
                                        'statements': [_statement(r) for r in group]})
            continue
        if len({_json(r['attributes']) for r in group}) > 1:
            report['conflicts'].append({'reason': 'ATTRIBUTE_MISMATCH', 'relation_ids': ids,
                                        'statements': [_statement(r) for r in group]})
            continue
        keep = min(group, key=lambda r: r['relation_id'])
        if len(group) > 1:
            report['merged'].append({'kept': keep['relation_id'], 'relation_ids': ids,
                                     'evidence': {r['relation_id']: r['evidence'] for r in group}})
        relations.append(keep)

    used_entities = sorted({i for r in relations for i in (r['subject_id'], r['object_id'])})
    used_sources = {(e['document_id'], e['chunk_id']) for r in relations for e in r['evidence']}
    envelope = {
        'schema_version': schema_version, 'corpus_id': corpus_id, 'dataset_version': dataset_version,
        'documents': [documents[d] for d in sorted({d for d, _ in used_sources})],
        'chunks': [chunks[k] for k in sorted(used_sources)],
        'entities': [entities[i] for i in used_entities],
        'mentions': [], 'relations': relations,
    }
    validate_envelope(envelope)
    report['loaded_relation_ids'] = sorted(r['relation_id'] for r in relations)
    return envelope, report


def _loaded_relation_ids(store, graph_version_id):
    with store.driver.session(database=store.database) as session:
        rows = session.run('''MATCH ()-[r:GRAPH_RELATION {graph_version_id: $id}]->()
                              RETURN r.relation_id AS relation_id''', id=graph_version_id)
        return sorted(row['relation_id'] for row in rows)


def build_graph_version(store, envelopes, *, graph_version_id, approve, now=None):
    """09.3: WBS06 gate -> one WBS08 batch -> reconcile -> publish only if all checks pass.

    approve(envelope) returns a WBS06 ApprovalGate (graph_review.gate.build_gate) for
    graph_version_id, which is also the review-store graph ID. It is called on every
    original envelope, unmodified, so each APPROVED relation is matched against the
    review store exactly as reviewed; the merged batch only adds unioned aliases and
    carries those same relations unchanged. Returns the receipt.
    """
    envelope, report = merge_envelopes(envelopes)
    manifest = sorted(_sha(p) for p in envelopes)
    # One batch per build; same inputs -> same batch_id -> WBS08 no-op on rerun.
    batch_id = 'wbs09:' + _sha(manifest)[:32]
    expected = set(report['loaded_relation_ids'])
    receipt = {
        'graph_version_id': graph_version_id, 'batch_id': batch_id,
        'corpus_id': envelope['corpus_id'], 'index_version_id': envelope['dataset_version'],
        'contract_version': envelope['schema_version'], 'input_manifest': manifest,
        'counts': {'input_relations': report['input_relations'], 'not_approved': report['not_approved'],
                   'loaded': len(expected), 'merged_groups': len(report['merged']),
                   'conflicts': len(report['conflicts'])},
        'checks': {}, 'status': 'BUILDING', 'blocked_reason': None,
        'conflicts_for_wbs06': report['conflicts'], 'merged': report['merged'],
        'missing_in_envelopes': [],
        'built_at': (now or datetime.now(timezone.utc)).isoformat(),
    }
    checks = receipt['checks']
    try:
        gates = [approve(payload) for payload in envelopes]
        for gate in gates:
            gate.validate(graph_version_id)
        allowed = set().union(*(gate.allowed_relation_ids for gate in gates))
        if not expected <= allowed:
            raise PermissionError('WBS06: unapproved or stale relations cannot enter Neo4j')
    except PermissionError as exc:
        receipt['blocked_reason'] = str(exc)
        checks['wbs06_gate'] = False
        return receipt
    checks['wbs06_gate'] = True
    accounted = expected | {i for m in report['merged'] for i in m['relation_ids']} | {
        i for c in report['conflicts'] for i in c['relation_ids']}
    receipt['missing_in_envelopes'] = sorted(allowed - accounted)
    checks['review_store_fully_exported'] = not receipt['missing_in_envelopes']
    if not checks['review_store_fully_exported']:
        return receipt
    batch = store.ingest_batch(envelope, graph_version_id=graph_version_id, batch_id=batch_id)
    checks['neo4j_edges_match_approved'] = set(_loaded_relation_ids(store, graph_version_id)) == expected
    checks['batch_count_matches'] = batch.relation_count == len(expected)
    if all(checks.values()):
        store.publish(graph_version_id, expected_batch_ids=[batch_id])
        receipt['status'] = 'READY'
    return receipt
