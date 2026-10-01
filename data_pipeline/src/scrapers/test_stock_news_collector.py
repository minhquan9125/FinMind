"""Offline regressions: run python -B -m unittest discover -s data_pipeline/src/scrapers."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stock_news_collector as collector
import news_sources as sources


def article(number=1):
    return {'id': str(number), 'url': f'https://cafef.vn/co-phieu-{1000000000 + number}.chn',
            'source': 'cafef', 'title': 'Cổ phiếu FPT tăng giá', 'description': '',
            'content': 'Nội dung bài viết.', 'published_at': None}


class NewsTests(unittest.TestCase):
    def test_urls_and_off_topic_filter(self):
        self.assertIsNotNone(collector.clean_url('https://cafef.vn/du-lieu/FPT-12345/cong-bo.chn?utm=x'))
        self.assertIsNone(collector.clean_url('https://cafef.vn/thi-truong-chung-khoan.chn'))
        self.assertIsNone(collector.clean_url('https://evil.example/bai-viet/tin/123'))
        self.assertFalse(sources.relevant({'title': 'Một bức tranh Việt Nam lập kỷ lục đấu giá'}))
        self.assertTrue(sources.relevant({'title': 'Fed giảm lãi suất'}))

    def test_fireant_pagination_news_only(self):
        pages = [
            [{'postID': 1, 'type': 1, 'title': 'Bức tranh kỷ lục'},
             {'postID': 2, 'type': 0, 'title': 'Cổ phiếu tôi đang mua'}],
            [{'postID': 3, 'type': 1, 'title': 'VN-Index tăng điểm'}], []]
        with patch.object(sources, 'fireant_json', side_effect=pages) as api:
            items = list(sources.fireant_candidates(max_pages=3))
        self.assertEqual([i['provider_id'] for i in items], ['3'])
        self.assertEqual(api.call_args_list[1].args[1]['offset'], 50)

    def test_symbol_tab_association_without_ticker_in_title(self):
        rows = [{'postID': 9, 'type': 1, 'title': 'Một doanh nghiệp tăng vốn'}]
        with patch.object(sources, 'fireant_json', side_effect=[rows, []]):
            items = list(sources.fireant_candidates('FPT'))
        self.assertEqual(items[0]['matched_symbols'], ['FPT'])

    def test_cafef_malformed_rss_fallback(self):
        from types import SimpleNamespace
        responses = [SimpleNamespace(content=b'<invalid>'), SimpleNamespace(
            text='<h3><a href="/co-phieu-12345678901.chn">Cổ phiếu tăng giá</a></h3>')]
        with patch.object(sources, 'get', side_effect=responses):
            self.assertEqual(len(list(sources.cafef_candidates())), 1)

    def test_cafef_disclosure_uses_news_headline_body_and_attachment(self):
        from types import SimpleNamespace
        url = 'https://cafef.vn/du-lieu/fpt-12345/cong-bo.chn'
        response = SimpleNamespace(url=url, text='''<meta property="og:title" content="FPT: Phát hành cổ phiếu">
            <h1>Công ty FPT (HOSE)</h1><div id="newscontent"><p>FPT công bố kết quả phát hành.</p>
            <a href="https://cafefnew.mediacdn.vn/report.pdf">Báo cáo</a></div>''')
        with patch.object(collector, 'get', return_value=response):
            result = collector.fetch_article(url)
        self.assertEqual(result['title'], 'FPT: Phát hành cổ phiếu')
        self.assertIn('công bố kết quả', result['content'])
        self.assertEqual(result['attachments'], ['https://cafefnew.mediacdn.vn/report.pdf'])

    def test_fill_after_failure_merge_and_repeat(self):
        with tempfile.TemporaryDirectory(dir=collector.DEFAULT_OUTPUT.parent) as folder:
            output = Path(folder) / 'news.json'
            candidates = [{'url': article(n)['url']} for n in (1, 2, 3)]
            discovery = lambda symbol, pages: iter(candidates)
            with patch.object(collector, 'cafef_candidates', discovery), \
                 patch.object(collector, 'fetch_article', side_effect=[None, article(2), article(3)]), \
                 patch.object(collector.time, 'sleep'):
                # Failure is visible to automation, but still fills the quota and saves successes.
                self.assertEqual(collector.main(['--limit', '2', '--output', str(output)]), 1)
            data = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(len(data['articles']), 2)
            self.assertEqual(data['last_run']['results'][0]['accepted'], 2)
            with patch.object(collector, 'cafef_candidates', lambda s, p: iter(candidates[1:])), \
                 patch.object(collector, 'fetch_article') as fetch:
                self.assertEqual(collector.main(['--symbols', 'FPT', '--only-symbols', '--limit', '2', '--output', str(output)]), 0)
                fetch.assert_not_called()
            self.assertEqual(len(json.loads(output.read_text(encoding='utf-8'))['articles']), 2)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['articles'][0]['scopes'], ['FPT', 'market'])
            self.assertEqual([p.name for p in Path(folder).iterdir()], ['news.json'])

    def test_corrupt_output_and_concurrent_writer_preserved(self):
        with tempfile.TemporaryDirectory(dir=collector.DEFAULT_OUTPUT.parent) as folder:
            output = Path(folder) / 'news.json'
            output.write_text('{broken', encoding='utf-8')
            self.assertEqual(collector.main(['--output', str(output)]), 1)
            self.assertEqual(output.read_text(encoding='utf-8'), '{broken')
            with collector.output_lock(output):
                self.assertEqual(collector.main(['--output', str(output)]), 1)
            self.assertFalse(output.with_suffix('.json.lock').exists())

    def test_split_migration_preserves_existing_and_is_repeatable(self):
        with tempfile.TemporaryDirectory(dir=collector.DEFAULT_OUTPUT.parent) as folder:
            root = Path(folder)
            legacy = root / 'stock_news.json'
            outputs = {s: root / (s + '_news.json') for s in ('cafef', 'fireant')}
            fireant = {**article(2), 'source': 'fireant', 'url': 'https://fireant.vn/bai-viet/tin/42'}
            collector.write_payload(legacy, {'articles': [article(1), fireant]})
            collector.write_payload(outputs['cafef'], {'articles': [article(3)]})
            collector.migrate_legacy(legacy, outputs)
            self.assertFalse(legacy.exists())
            self.assertEqual(len(collector.read_articles(outputs['cafef'], 'cafef')), 2)
            self.assertEqual(len(collector.read_articles(outputs['fireant'], 'fireant')), 1)
            before = {s: p.read_bytes() for s, p in outputs.items()}
            collector.migrate_legacy(legacy, outputs)
            self.assertEqual(before, {s: p.read_bytes() for s, p in outputs.items()})

    def test_invalid_migration_preserves_all_files(self):
        with tempfile.TemporaryDirectory(dir=collector.DEFAULT_OUTPUT.parent) as folder:
            root = Path(folder)
            legacy = root / 'stock_news.json'
            outputs = {s: root / (s + '_news.json') for s in ('cafef', 'fireant')}
            collector.write_payload(legacy, {'articles': [article()]})
            outputs['fireant'].write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                collector.migrate_legacy(legacy, outputs)
            self.assertTrue(legacy.exists())
            self.assertFalse(outputs['cafef'].exists())
            self.assertEqual(outputs['fireant'].read_text(encoding='utf-8'), '{broken')

    def test_all_sources_separate_and_single_source_keeps_other_file(self):
        with tempfile.TemporaryDirectory(dir=collector.DEFAULT_OUTPUT.parent) as folder:
            root = Path(folder)
            fireant = {**article(2), 'source': 'fireant', 'url': 'https://fireant.vn/bai-viet/tin/42'}
            with patch.object(collector, 'cafef_candidates', lambda s, p: iter([article()])), \
                 patch.object(collector, 'fireant_candidates', lambda s, p: iter([fireant])), \
                 patch.object(collector, 'fetch_article', side_effect=[article(), fireant]), \
                 patch.object(collector.time, 'sleep'):
                self.assertEqual(collector.main(['--source', 'all', '--limit', '1', '--output', str(root / 'news.json')]), 0)
            cafef_path, fireant_path = root / 'news_cafef.json', root / 'news_fireant.json'
            self.assertEqual(len(collector.read_articles(cafef_path, 'cafef')), 1)
            self.assertEqual(len(collector.read_articles(fireant_path, 'fireant')), 1)
            fireant_bytes = fireant_path.read_bytes()
            with patch.object(collector, 'cafef_candidates', lambda s, p: iter([article()])):
                self.assertEqual(collector.main(['--source', 'cafef', '--limit', '1', '--output', str(cafef_path)]), 0)
            self.assertEqual(fireant_bytes, fireant_path.read_bytes())
            self.assertEqual({p.name for p in root.iterdir()}, {'news_cafef.json', 'news_fireant.json'})


if __name__ == '__main__':
    unittest.main()
