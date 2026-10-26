import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.src.vector_retrieval.sources import SnapshotResolver, SnapshotError


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def fixture():
    text = 'CTCP FPT | Tiền và tương đương tiền: 123 (đơn vị chưa xác minh)'
    locator = dict(source_table='financial_reports', source_id='report1', row_keys=['r1'],
                   reconstruction=dict(source_chunk_id='original-source-uuid', document_id='original-doc-uuid'))
    chunk = dict(source_chunk_id='original-source-uuid', chunk_index=0, text=text,
                 content_hash=hashlib.sha256(text.encode()).hexdigest(), locator=locator)
    payload = dict(schema_version='finmind-source-corpus-v2', document_count=1, chunk_count=1,
                   documents=[dict(document_id='original-doc-uuid', chunks=[chunk])])
    return dict(manifest_sha256=hashlib.sha256(canonical(payload)).hexdigest(), manifest=payload)


class SnapshotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'manifest.json'
        self.data = fixture()

    def load(self, data=None, repin=False):
        data = copy.deepcopy(self.data if data is None else data)
        if repin:
            data['manifest_sha256'] = hashlib.sha256(canonical(data['manifest'])).hexdigest()
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
        return SnapshotResolver(self.path, data['manifest_sha256'])

    def row(self):
        c = self.data['manifest']['documents'][0]['chunks'][0]
        return dict(chunk_id='stored-db-uuid', document_id='stored-db-doc', chunk_index=0,
                    content_hash=c['content_hash'], locator_json=copy.deepcopy(c['locator']), title='stored title')

    async def test_real_nested_envelope_and_distinct_db_ids(self):
        resolver = self.load()
        row = self.row()
        original = copy.deepcopy(row)
        output = await resolver(None, [row])
        self.assertEqual(row, original)
        for key in ('chunk_id', 'document_id', 'title'):
            self.assertEqual(output[0][key], row[key])
        self.assertEqual(output[0]['text'], self.data['manifest']['documents'][0]['chunks'][0]['text'])
        self.assertEqual(output[0]['source_provenance']['mode'], 'FROZEN_SNAPSHOT')
        self.assertEqual(resolver.provenance['manifest_sha256'], self.data['manifest_sha256'])

    async def test_string_locator_whitespace_hash_order_empty(self):
        resolver = self.load()
        a, b = self.row(), self.row()
        a['chunk_id'], b['chunk_id'] = 'a', 'b'
        a['content_hash'] += ' '
        a['locator_json'] = json.dumps(a['locator_json'])
        self.assertEqual([r['chunk_id'] for r in await resolver(None, [b, a])], ['b', 'a'])
        self.assertEqual(await resolver(None, []), [])

    async def test_atomic_failure_and_all_db_identity_checks(self):
        resolver = self.load()
        for field, value in [('content_hash','0'*64),('chunk_index',1),('chunk_index',False),
                             ('locator_json',{}),('locator_json','{}')]:
            row = self.row(); row[field] = value
            before = copy.deepcopy(row)
            with self.subTest(field=field, value=value), self.assertRaises(SnapshotError):
                await resolver(None, [self.row(), row])
            self.assertEqual(row, before)
        row = self.row(); row['locator_json']['extra']='changed'
        with self.assertRaises(SnapshotError): await resolver(None,[row])
        row = self.row(); row['locator_json']['reconstruction']['source_chunk_id']='absent'
        with self.assertRaises(SnapshotError): await resolver(None,[row])

    def test_hash_pin_not_self_attested(self):
        self.load()
        for pin in ('0'*64, self.data['manifest_sha256'].upper(), None, 'bad'):
            with self.subTest(pin=pin), self.assertRaises(SnapshotError): SnapshotResolver(self.path,pin)
        data=copy.deepcopy(self.data); data['manifest']['extra']='tamper'
        with self.assertRaises(SnapshotError): self.load(data)

    def test_counts_duplicates_locator_and_text_rejected_even_if_repinned(self):
        mutations = [lambda p:p.update(document_count=2),lambda p:p.update(chunk_count=2),
                     lambda p:p.update(document_count=True),lambda p:p.update(documents=None),
                     lambda p:p.update(schema_version='other'),
                     lambda p:p['documents'][0]['chunks'].append(copy.deepcopy(p['documents'][0]['chunks'][0])),
                     lambda p:p['documents'][0]['chunks'][0].update(text='tampered'),
                     lambda p:p['documents'][0]['chunks'][0].update(chunk_index=False),
                     lambda p:p['documents'][0]['chunks'][0]['locator']['reconstruction'].update(source_chunk_id='wrong')]
        for mutate in mutations:
            data=copy.deepcopy(self.data); mutate(data['manifest'])
            with self.subTest(mutate=mutate), self.assertRaises(SnapshotError): self.load(data,repin=True)

    def test_bounded_read_bad_json_and_safe_errors(self):
        self.load()
        with patch('backend.src.vector_retrieval.sources.MAX_BYTES',1), self.assertRaises(SnapshotError):
            SnapshotResolver(self.path,self.data['manifest_sha256'])
        for raw in ('{bad','{"manifest":NaN}','{"a":1,"a":2}'):
            self.path.write_text(raw,encoding='utf8')
            with self.assertRaises(SnapshotError): SnapshotResolver(self.path,self.data['manifest_sha256'])
        self.path.unlink()
        with self.assertRaises(SnapshotError) as error: SnapshotResolver(self.path,self.data['manifest_sha256'])
        self.assertNotIn(str(self.path),str(error.exception))
