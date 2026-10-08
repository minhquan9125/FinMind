"""Offline regressions: run python -B -m unittest discover -s tests -t .."""
import json
import tempfile
from tests.helpers import TEST_TMP
import unittest
from pathlib import Path
from unittest.mock import patch

from news import stock_news_collector as collector
from news import news_sources as sources
from news import news_storage as storage


def article(number=1):
    return {'id': str(number), 'url': f'https://cafef.vn/co-phieu-{1000000000 + number}.chn',
            'source': 'cafef', 'title': 'Cổ phiếu FPT tăng giá', 'description': '',
            'content': 'Nội dung bài viết.', 'published_at': None,
            'crawled_at': '2026-09-30T18:00:00+00:00'}


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

    def run_mocked(self, root, day='01-10-2026', symbols=(), fail=False):
        def discovery(symbol, pages):
            return iter([{'url': article(n)['url'], 'matched_symbols': [symbol] if symbol else []}
                         for n in (1, 2)])
        fireant = {**article(3), 'source': 'fireant', 'url': 'https://fireant.vn/bai-viet/tin/42'}
        with patch.object(collector, 'cafef_candidates', discovery), \
             patch.object(collector, 'fireant_candidates', lambda s, p: iter([fireant])), \
             patch.object(collector, 'fetch_article', side_effect=lambda url, candidate: (
                 fireant.copy() if 'fireant' in url else
                 None if fail and url == article(1)['url'] else
                 article(1 if url == article(1)['url'] else 2))), \
             patch.object(collector, 'crawl_day', return_value=day), \
             patch.object(collector.time, 'sleep'):
            return collector.main(['--source', 'all', '--limit', '1', '--output', str(root)] +
                                  (['--symbols', *symbols] if symbols else []))

    def test_daily_routing_repeat_new_day_and_new_symbol(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            self.assertEqual(self.run_mocked(root, symbols=('FPT', 'HPG')), 0)
            paths=list(root.rglob('*.json'))
            self.assertEqual(len(paths), 6)
            for source in ('cafef', 'fireant'):
                for scope in ('market', 'FPT', 'HPG'):
                    path=storage.daily_path(root, source, scope, '01-10-2026')
                    rows=collector.read_articles(path, source)
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(next(iter(rows.values()))['scopes'], [scope])
            self.assertEqual(self.run_mocked(root, symbols=('FPT', 'HPG')), 0)
            self.assertEqual(len(list(root.rglob('*.json'))), 6)
            old={p:p.read_bytes() for p in paths}
            self.assertEqual(self.run_mocked(root, day='02-10-2026', symbols=('VCB',)), 0)
            self.assertEqual(len(list(root.rglob('*.json'))), 10)
            self.assertEqual(old, {p:p.read_bytes() for p in paths})
            self.assertFalse(list(root.rglob('*.lock')))
            self.assertFalse(list(root.rglob('*.tmp')))

    def test_fill_after_failure_preserves_success(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            self.assertEqual(self.run_mocked(root, fail=True), 1)
            rows=collector.read_articles(storage.daily_path(root,'cafef','market','01-10-2026'))
            self.assertEqual(list(rows), [article(2)['url']])

    def test_corrupt_output_and_concurrent_writer_preserved(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            output=storage.daily_path(root,'cafef','market','01-10-2026')
            output.parent.mkdir(parents=True)
            output.write_text('{broken',encoding='utf-8')
            self.assertEqual(self.run_mocked(root), 1)
            self.assertEqual(output.read_text(encoding='utf-8'), '{broken')
            output.unlink()
            with collector.output_lock(output):
                self.assertEqual(self.run_mocked(root), 1)
            self.assertFalse(output.with_suffix('.json.lock').exists())

    def test_migration_multiscope_preserves_records_and_repeat(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            legacy=root/'old.json'
            trial=root/'news_trial.json'
            row={**article(), 'scopes':['FPT','HPG','market'], 'matched_symbols':['FPT','HPG']}
            collector.write_payload(legacy, {'articles':[row]})
            collector.write_payload(trial, {'articles':[article(2)]})
            migrate=lambda: storage.migrate_daily(root,[legacy,trial],collector.read_articles,
                                                  collector.write_payload,collector.output_lock)
            migrate()
            self.assertFalse(legacy.exists())
            self.assertFalse(trial.exists())
            for scope in ('market','FPT','HPG'):
                rows=collector.read_articles(storage.daily_path(root,'cafef',scope,'01-10-2026'))
                self.assertEqual(rows[row['url']],row)
            self.assertEqual(len(collector.read_articles(storage.daily_path(root,'cafef','market','01-10-2026'))),2)
            before={p:p.read_bytes() for p in root.rglob('*.json')}
            migrate()
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*.json')})

    def test_invalid_migration_preserves_inputs_and_destinations(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            legacy=root/'old.json'
            collector.write_payload(legacy,{'articles':[article()]})
            target=storage.daily_path(root,'cafef','market','01-10-2026')
            target.parent.mkdir(parents=True)
            target.write_text('{broken',encoding='utf-8')
            with self.assertRaises(ValueError):
                storage.migrate_daily(root,[legacy],collector.read_articles,collector.write_payload,collector.output_lock)
            self.assertTrue(legacy.exists())
            self.assertEqual(target.read_text(encoding='utf-8'),'{broken')

    def test_vietnam_day_boundary_and_path_validation(self):
        self.assertEqual(storage.crawl_day('2026-09-30T16:59:59Z'),'30-09-2026')
        self.assertEqual(storage.crawl_day('2026-09-30T17:00:00Z'),'01-10-2026')
        with self.assertRaises(ValueError):
            storage.daily_path(storage.SCRAPERS,'cafef','../../escape','01-10-2026')
        with self.assertRaises(ValueError):
            storage.crawl_day('2026-10-01T00:00:00')


if __name__ == '__main__':
    unittest.main()
