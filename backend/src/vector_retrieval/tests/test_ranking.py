import unittest
import math
from backend.src.vector_retrieval.ranking import tokenize, BM25Index, rrf

class TestTokenize(unittest.TestCase):
    def test_basic_normalization(self):
        text = "Đây là một ví dụ: CÁC ký tự Đ và dấu nhé!"
        # Expected: lowercased, NFKC, diacritics removed, 'đ' -> 'd'
        expected = ['day', 'la', 'mot', 'vi', 'du', 'cac', 'ky', 'tu', 'd', 'va', 'dau', 'nhe']
        self.assertEqual(tokenize(text), expected)

    def test_non_string_raises(self):
        with self.assertRaises(TypeError):
            tokenize(123)

class TestBM25Index(unittest.TestCase):
    def setUp(self):
        # Simple corpus for deterministic scores
        self.docs = {
            'a': ['foo', 'bar'],
            'b': ['foo', 'foo']
        }
        self.index = BM25Index(self.docs)

    def test_basic_scoring_order(self):
        results = self.index.search('foo')
        # Expected order: 'b' (higher tf) then 'a'
        self.assertEqual([cid for cid, _ in results], ['b', 'a'])
        # Verify approximate scores using the BM25 formula
        n = 2
        df = 2
        idf = math.log1p((n - df + 0.5) / (df + 0.5))
        k1 = 1.5
        b = 0.75
        avg_len = 2.0
        # doc a
        tf_a = 1
        len_a = 2
        norm_a = k1 * (1 - b + b * len_a / avg_len)
        score_a = idf * tf_a * (k1 + 1) / (tf_a + norm_a)
        # doc b
        tf_b = 2
        len_b = 2
        norm_b = k1 * (1 - b + b * len_b / avg_len)
        score_b = idf * tf_b * (k1 + 1) / (tf_b + norm_b)
        # Compare with returned scores (allow tiny rounding diff)
        self.assertAlmostEqual(results[0][1], score_b, places=6)
        self.assertAlmostEqual(results[1][1], score_a, places=6)

    def test_allowed_ids_filter(self):
        results = self.index.search('foo', allowed_ids={'a'})
        self.assertEqual(results, [('a', results[0][1])])
        self.assertEqual(results[0][0], 'a')

    def test_limit_parameter(self):
        # Request a limit larger than available docs – should return all
        results = self.index.search('foo', limit=10)
        self.assertEqual(len(results), 2)
        # Invalid limit type raises
        with self.assertRaises(ValueError):
            self.index.search('foo', limit='5')

    def test_invalid_documents_structure(self):
        with self.assertRaises(TypeError):
            BM25Index(['not', 'a', 'dict'])
        with self.assertRaises(ValueError):
            BM25Index({123: ['token']})
        with self.assertRaises(ValueError):
            BM25Index({'c': [123]})

class TestRRF(unittest.TestCase):
    def test_basic_fusion_order(self):
        dense = [('a', 0.9), ('b', 0.8)]
        lexical = [('b', 0.5), ('c', 0.4)]
        fused = rrf(dense, lexical, limit=3, k=60.0, dense_weight=1.0, lexical_weight=1.0)
        # Expected order: b (rank 2 dense + rank 1 lexical), a (rank 1 dense), c (rank 2 lexical)
        self.assertEqual([r['chunk_id'] for r in fused], ['b', 'a', 'c'])
        # Verify scores are positive and monotonic decreasing
        scores = [r['rrf_score'] for r in fused]
        self.assertTrue(all(s > 0 for s in scores))
        self.assertTrue(scores[0] > scores[1] > scores[2])

    def test_limit_enforcement(self):
        dense = [('x' + str(i), 1.0) for i in range(5)]
        lexical = []
        fused = rrf(dense, lexical, limit=3)
        self.assertEqual(len(fused), 3)
        self.assertEqual([r['chunk_id'] for r in fused], ['x0', 'x1', 'x2'])

    def test_duplicate_ids_ignored(self):
        dense = [('dup', 0.9), ('dup', 0.8), ('unique', 0.5)]
        lexical = [('dup', 0.7), ('unique', 0.6)]
        fused = rrf(dense, lexical, limit=10)
        # 'dup' should appear once with the first dense rank (1) and lexical rank (1)
        dup_entry = next(r for r in fused if r['chunk_id'] == 'dup')
        self.assertEqual(dup_entry['dense_rank'], 1)
        self.assertEqual(dup_entry['bm25_rank'], 1)
        # Ensure scores reflect only one occurrence per branch
        expected_score = 1.0 / (60.0 + 1) + 1.0 / (60.0 + 1)
        self.assertAlmostEqual(dup_entry['rrf_score'], expected_score, places=6)

    def test_invalid_inputs_raise(self):
        with self.assertRaises(TypeError):
            rrf('not a list', [], limit=5)
        with self.assertRaises(ValueError):
            rrf([], [], dense_weight=0, lexical_weight=0)
        with self.assertRaises(ValueError):
            rrf([('id',)], [], limit=5)  # malformed item
        with self.assertRaises(TypeError):
            rrf([('id', 0.1)], None)

if __name__ == '__main__':
    unittest.main()


class CoordinatorBoundaryChecks(unittest.TestCase):
    def test_empty_documents_and_unknown_query(self):
        for documents in ({}, {'empty': []}):
            self.assertEqual(BM25Index(documents).search('assets'), [])
        self.assertEqual(BM25Index({'a': ['assets']}).search('missing'), [])

    def test_scope_before_limit_and_global_statistics(self):
        index = BM25Index({'a': ['assets'] * 5, 'b': ['assets'], 'c': ['other']})
        full = dict(index.search('assets'))
        self.assertEqual(index.search('assets', limit=1, allowed_ids={'b'}), [('b', full['b'])])
        self.assertEqual(index.search('assets', allowed_ids=set()), [])
        self.assertEqual(index.search('assets assets'), index.search('assets'))

    def test_canonical_unicode_and_identifiers(self):
        import unicodedata
        text = '\u0110\u1ed3ng FPT 2026-Q2 LNST'
        self.assertEqual(tokenize(text), tokenize(unicodedata.normalize('NFD', text)))
        self.assertEqual(tokenize(text), ['dong', 'fpt', '2026', 'q2', 'lnst'])

    def test_ties_and_disabled_branch(self):
        index = BM25Index({'b': ['x'], 'a': ['x']})
        self.assertEqual([x[0] for x in index.search('x')], ['a', 'b'])
        self.assertEqual([r['chunk_id'] for r in rrf([('b', .8)], [('a', 1)], dense_weight=0)], ['a'])
        self.assertEqual(rrf([], []), [])
        self.assertEqual([r['chunk_id'] for r in rrf([('b', .8)], [('a', 1)])], ['a', 'b'])

    def test_invalid_numbers_never_enter_scores(self):
        for value in (float('nan'), float('inf'), True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): BM25Index({}, k1=value)
                with self.assertRaises(ValueError): rrf([], [], k=value)
                with self.assertRaises(ValueError): rrf([('a', value)], [])
        for limit in (0, -1, True, 1.5, 10001):
            with self.assertRaises(ValueError): BM25Index({}).search('x', limit=limit)
            with self.assertRaises(ValueError): rrf([], [], limit=limit)
