"""Offline integration tests for the single-command news workflow."""
import contextlib
import io
import json
import tempfile
from tests.helpers import TEST_TMP
import unittest
from pathlib import Path
from unittest.mock import patch

from news import run_news_pipeline as pipeline
from news.news_storage import SCRAPERS, daily_path


def article(source):
    return {'source': source, 'url': 'https://cafef.vn/co-phieu-12345678901.chn' if source == 'cafef'
            else 'https://fireant.vn/bai-viet/tin/123', 'title': 'Cổ phiếu FPT tăng trưởng',
            'content': 'Cổ phiếu FPT tăng trưởng doanh thu và lợi nhuận trong quý ba năm nay.',
            'crawled_at': '2026-10-01T01:00:00Z', 'published_at': '2026-10-01T08:00:00+07:00'}


class PipelineTests(unittest.TestCase):
    def run_mocked(self, root, fail_fireant=False):
        with patch('news.stock_news_collector.cafef_candidates', side_effect=lambda *a: iter([article('cafef')])), \
             patch('news.stock_news_collector.fireant_candidates', side_effect=lambda *a: iter([] if fail_fireant else [article('fireant')])), \
             patch('news.stock_news_collector.fetch_article', side_effect=lambda url, candidate: dict(candidate)), \
             patch('news.stock_news_collector.crawl_day', return_value='01-10-2026'), \
             patch('news.stock_news_collector.time.sleep'), contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            return pipeline.run_pipeline(['FPT'], limit=1, root=root)

    def test_complete_flow_and_repeat_report(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            code, report = self.run_mocked(root)
            self.assertEqual(code, 0)
            self.assertEqual(report['summary']['successful_collection_groups'], 4)
            self.assertEqual(report['summary']['new_article_records'], 4)
            self.assertEqual(report['summary']['created_files'], 4)
            self.assertEqual(report['summary']['crosschecked_records'], 4)
            self.assertEqual(report['summary']['check_records'], 4)
            self.assertEqual(report['event_analysis']['status'], 'ok')
            self.assertTrue((root / 'pipeline_reports/events.md').exists())
            code, second = self.run_mocked(root)
            self.assertEqual(code, 0)
            self.assertEqual(second['summary']['created_files'], 0)
            self.assertEqual(second['summary']['new_article_records'], 0)
            self.assertEqual(second['summary']['accepted_articles'], 4)
            saved = json.loads((root / 'pipeline_reports/latest.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['summary'], second['summary'])

    def test_partial_crawl_still_analyzes_and_reports(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            code, report = self.run_mocked(Path(folder), fail_fireant=True)
            self.assertEqual(code, 1)
            self.assertEqual(report['summary']['successful_collection_groups'], 2)
            self.assertEqual(report['summary']['uncheck_records'], 2)
            self.assertEqual(report['summary']['saved_files'], 2)
            self.assertEqual(report['event_analysis']['status'], 'ok')
            self.assertEqual(report['summary']['analyzed_uncheck_articles'], 1)

    def test_crosscheck_failure_is_not_success(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            with patch('news.news_crosscheck.crosscheck_news', side_effect=ValueError('crosscheck unavailable')):
                code, report = self.run_mocked(Path(folder))
            self.assertEqual(code, 1)
            self.assertEqual(report['collector']['crosscheck']['status'], 'failed')
            self.assertEqual(report['summary']['crosschecked_records'], 0)

    def test_analysis_failure_replaces_stale_report(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            self.run_mocked(root)
            with patch('news.analyze_uncheck_events.analyze', side_effect=ValueError('invalid data')):
                code, report = self.run_mocked(root)
            self.assertEqual(code, 1)
            self.assertIsNone(report['summary']['analyzed_uncheck_articles'])
            saved = json.loads((root / 'pipeline_reports/events.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['status'], 'failed')

    def test_prompt_default_limit_and_symbol_validation(self):
        self.assertEqual(pipeline.parse_symbols(' fpt,HPG;fpt '), ['FPT', 'HPG'])
        for invalid in ('', '../../outside', 'FPT ???'):
            with self.assertRaises(ValueError):
                pipeline.parse_symbols(invalid)
        with patch('builtins.input', return_value='VCB'), \
             patch.object(pipeline, 'run_pipeline', return_value=(0, {})) as run:
            self.assertEqual(pipeline.main([]), 0)
            self.assertEqual(run.call_args.args, (['VCB'], 10))


if __name__ == '__main__':
    unittest.main()
