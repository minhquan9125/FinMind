"""Read the shared WBS17 XLSX without Excel, macros, or workbook mutations.

Only stored cell values and legacy notes are inputs. Formula cells used as inputs
are rejected rather than trusting possibly stale cached calculations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


def _target(base, target):
    name = posixpath.normpath(posixpath.join(posixpath.dirname(base), target)) if not target.startswith('/') else target.lstrip('/')
    if not name.startswith('xl/') or '..' in PurePosixPath(name).parts:
        raise ValueError('Invalid workbook relationship')
    return name


def _relationships(z, base):
    p = PurePosixPath(base)
    rels = str(p.parent/'_rels'/(p.name+'.rels'))
    if rels not in z.namelist():
        return {}
    return {r.attrib['Id']: r for r in ET.fromstring(z.read(rels))}


def _note_json(text, locator=False):
    text = text.split('\n', 1)[1].lstrip() if locator else text.lstrip()
    if not text:
        return None
    return json.JSONDecoder().raw_decode(text)[0]


def load_workbook_suite(path, *, case_ids=None):
    path = Path(path)
    with ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(t.text or '' for t in si.findall('.//s:t', NS))
                      for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        sheets = ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS)
        master = next(s for s in sheets if s.attrib['name'] == 'Test_Cases_Master')
        rels = _relationships(z, 'xl/workbook.xml')
        sheet_path = _target('xl/workbook.xml', rels[master.attrib[REL]].attrib['Target'])
        cells = {}
        for cell in ET.fromstring(z.read(sheet_path)).findall('.//s:c', NS):
            ref = cell.attrib['r']
            # Lookup formulas on the other sheets are deliberately not evaluated.
            if cell.find('s:f', NS) is not None:
                cells[ref] = None
                continue
            v = cell.find('s:v', NS)
            value = v.text if v is not None else ''
            if cell.get('t') == 's':
                value = shared[int(value)]
            elif cell.get('t') == 'inlineStr':
                value = ''.join(t.text or '' for t in cell.findall('.//s:t', NS))
            cells[ref] = value
        notes = {}
        for rel in _relationships(z, sheet_path).values():
            if rel.get('Type', '').endswith('/comments'):
                root = ET.fromstring(z.read(_target(sheet_path, rel.attrib['Target'])))
                notes.update({c.attrib['ref']: ''.join(t.text or '' for t in c.findall('.//s:t', NS))
                              for c in root.findall('s:commentList/s:comment', NS)})
    def value(ref):
        v = cells.get(ref, '')
        if v is None:
            raise ValueError('Formula input is not supported: '+ref)
        return v
    if value('A6') != 'Test_ID' or value('B6') != 'Question':
        raise ValueError('Unsupported shared workbook layout')
    scope = {'corpus_version_id': value('Q8'), 'index_version_id': value('Q9'),
             'graph_version_ids': value('Q10').splitlines()}
    if not all(scope.values()):
        raise ValueError('Missing pinned scope')
    cases = []
    rows = sorted(int(r[1:]) for r in cells if re.fullmatch(r'A\d+', r) and value(r).startswith('TC_'))
    for row in rows:
        v = lambda col: value(f'{col}{row}')
        setup = v('H')
        if setup not in {'READY_RETRIEVAL', 'READY_FIXTURE', 'SETUP_REQUIRED'}:
            raise ValueError('Invalid setup status')
        # A live runner must never execute controlled fault fixtures by accident.
        ready = setup == 'READY_RETRIEVAL'
        raw = _note_json(notes.get(f'E{row}', '{}'))
        sources = _note_json(notes[f'F{row}'], locator=True) if f'F{row}' in notes else []
        sources = sources if isinstance(sources, list) else [sources] if sources else []
        runtime, scope_note = v('M'), v('L')
        doc_ids = {s['document_id'] for s in sources if s.get('document_id')}
        chunks = {s['chunk_id'] for s in sources if s.get('chunk_id')}
        doc_match = re.search(r'Document: ('+UUID+r')', runtime)
        chunk_match = re.search(r'Chunk: ([0-9a-f, -]+)', runtime)
        if doc_match:
            doc_ids.add(doc_match.group(1))
        if chunk_match:
            chunks.update(re.findall(UUID, chunk_match.group(1)))
        expected = {'route': v('D') or 'CLARIFY', 'status': 'OK',
                    'decision': v('N'), 'chunk_ids': sorted(chunks), 'document_ids': sorted(doc_ids),
                    'relations': []}
        if ready and v('D') in {'GRAPH', 'BOTH'}:
            version = re.search(r'Graph READY: ([\w-]+)', runtime)
            if not version or version.group(1) not in scope['graph_version_ids']:
                raise ValueError('Missing or unpinned graph version')
            if not isinstance(raw, dict) or not all(raw.get(k) for k in ('subject_id', 'object_id', 'relation_type')):
                raise ValueError('Ready graph case lacks canonical relation')
            expected['relations'] = [{k: raw[k] for k in ('subject_id', 'object_id', 'relation_type')} |
                {'as_of': raw['temporal']['as_of'], 'graph_version_id': version.group(1),
                 'attributes': raw.get('attributes', {})}]
        company = re.match(r'^([A-Z]{3,5});', scope_note)
        year = re.search(r'\b20\d{2}\b', scope_note)
        b1_context = {'companies': [company.group(1)] if company else [],
                      'periods': [year.group()] if year else []}
        cases.append({'case_id': v('A'), 'question': v('B'), 'group': v('C'),
            'readiness': 'READY' if ready else 'NOT_READY',
            'blocked_reason': None if ready else v('I') or setup,
            'gold': {'status': 'DRAFT', 'reviewer': None, 'reviewed_at': None, 'complete': False},
            'context': {}, 'b1_context': b1_context, 'expected': expected,
            'workbook': {'row': row, 'setup_status': setup, 'scope_note': scope_note,
                         'runtime_ref': runtime, 'ground_truth_answer': v('G'),
                         'expected_raw': raw, 'source_refs': sources}})
    if case_ids:
        missing = set(case_ids)-{c['case_id'] for c in cases}
        if missing:
            raise ValueError('Unknown case IDs: '+', '.join(sorted(missing)))
        cases = [c for c in cases if c['case_id'] in case_ids]
    return {'schema_version': 'wbs17-shared-workbook-v1', 'scope': scope, 'cases': cases,
            'minimum_repeats': max(5, int(value('Q13'))),
            'workbook_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'workbook_name': path.name,
            'note': 'XLSX values/notes preserved; no human test-gold approval inferred from source approval.'}
