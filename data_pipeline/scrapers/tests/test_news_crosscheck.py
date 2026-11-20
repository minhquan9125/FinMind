import json
import tempfile
from tests.helpers import TEST_TMP
import unittest
from pathlib import Path
from unittest.mock import patch

from news import news_crosscheck as check
from news.news_storage import SCRAPERS, daily_path
from news.stock_news_collector import write_payload, read_articles
from tests.test_stock_news_collector import article


def row(source, number=1, content=None):
    result = article(number)
    result.update(source=source, content=content or 'VCB cong bo ket qua kinh doanh doanh thu tang truong trong quy ba nam 2026.')
    if source == 'fireant':
        result['url'] = f'https://fireant.vn/bai-viet/tin/{number}'
    return result


class CrossCheckTests(unittest.TestCase):
    def test_similarity_requires_body_and_preserves_numbers(self):
        a=row('cafef')
        b=row('fireant')
        self.assertEqual(check.article_similarity(a,b),1)
        self.assertEqual(check.article_similarity(a,{**b,'content':''}),0)
        self.assertLess(check.article_similarity(a,row('fireant',content='TPB phat hanh trai phieu ky han muoi nam voi lai suat co dinh.')),0.8)
        self.assertNotEqual(check.tokens('10,5%'),check.tokens('15,5%'))
        self.assertEqual(check.tokens('LỢI NHUẬN'),check.tokens('lợi nhuận'))

    def test_both_sources_scope_isolation_cross_day_and_reset(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            paths={}
            for source, scope, day in [('cafef','VCB','01-10-2026'),('fireant','VCB','02-10-2026'),
                                       ('cafef','TPB','01-10-2026'),('cafef','market','01-10-2026')]:
                path=daily_path(root,source,scope,day)
                path.parent.mkdir(parents=True,exist_ok=True)
                write_payload(path,{'articles':[row(source)],'last_run':{'unchanged':True}})
                paths[(source,scope)]=path
            check.crosscheck_news(root)
            for key,path in paths.items():
                data=json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(data['articles'][0]['marker'],'check' if key[1]=='VCB' else 'uncheck')
                self.assertEqual(data['last_run'],{'unchanged':True})
            before={p:p.read_bytes() for p in paths.values()}
            check.crosscheck_news(root)
            self.assertEqual(before,{p:p.read_bytes() for p in paths.values()})
            paths[('fireant','VCB')].unlink()
            check.crosscheck_news(root,['VCB'])
            self.assertEqual(next(iter(read_articles(paths[('cafef','VCB')]).values()))['marker'],'uncheck')

    def test_threshold_is_strictly_greater_than_80_percent(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            for source in ('cafef','fireant'):
                path=daily_path(root,source,'market','01-10-2026')
                path.parent.mkdir(parents=True,exist_ok=True)
                write_payload(path,{'articles':[row(source)]})
            with patch.object(check,'prepared_similarity',return_value=0.8):
                self.assertEqual(check.crosscheck_news(root)[0]['check'],0)
            with patch.object(check,'prepared_similarity',return_value=0.80001):
                self.assertEqual(check.crosscheck_news(root)[0]['check'],2)

    def test_new_only_adds_new_urls_instead_of_counting_saved(self):
        from news.stock_news_collector import main
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root=Path(folder)
            path=daily_path(root,'cafef','market','01-10-2026')
            path.parent.mkdir(parents=True)
            write_payload(path,{'articles':[article(1)]})
            with patch('news.stock_news_collector.crawl_day',return_value='01-10-2026'), \
                 patch('news.stock_news_collector.cafef_candidates',return_value=iter([article(1),article(2)])), \
                 patch('news.stock_news_collector.fetch_article',return_value=article(2)) as fetch, \
                 patch('news.stock_news_collector.time.sleep'):
                self.assertEqual(main(['--output',str(root),'--new-only','--limit','1']),0)
                self.assertEqual(fetch.call_count,1)
            self.assertEqual(len(read_articles(path)),2)


if __name__ == '__main__':
    unittest.main()
