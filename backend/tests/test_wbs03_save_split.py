"""Per-page split for the DB intake; no database is accessed."""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('save_bctn_relations', SCRIPTS / 'save_bctn_relations.py')
save_bctn_relations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(save_bctn_relations)


class SplitTests(unittest.TestCase):
    def test_relation_on_two_pages_becomes_two_copies(self):
        evidence = [{'document_id': 'd', 'chunk_id': 'c1', 'quote': 'a'},
                    {'document_id': 'd', 'chunk_id': 'c2', 'quote': 'b'},
                    {'document_id': 'd', 'chunk_id': 'c3', 'quote': 'c'}]
        payload = {'chunks': [{'document_id': 'd', 'chunk_id': 'c1', 'locator': {'section_index': 4}},
                              {'document_id': 'd', 'chunk_id': 'c2', 'locator': {'section_index': 9}},
                              {'document_id': 'd', 'chunk_id': 'c3', 'locator': {'section_index': 4}}],
                   'relations': [{'relation_id': 'rel:x', 'evidence': evidence}]}
        groups = save_bctn_relations.split_by_section(payload)
        self.assertEqual(sorted(groups), [('d', 4), ('d', 9)])
        self.assertEqual(groups[('d', 4)]['rel:x']['evidence'], [evidence[0], evidence[2]])
        self.assertEqual(groups[('d', 9)]['rel:x']['evidence'], [evidence[1]])
        self.assertEqual(len(payload['relations'][0]['evidence']), 3)


if __name__ == '__main__':
    unittest.main()
