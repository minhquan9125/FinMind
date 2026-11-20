"""Offline tests for event analysis, scope separation and source preservation."""
import hashlib
import json
import tempfile
from tests.helpers import TEST_TMP
import unittest
from pathlib import Path

from news import analyze_uncheck_events as analysis
from news.news_storage import SCRAPERS, daily_path


def article(source, title='FPT có thêm cổ đông', body=None, date='2026-09-29T10:00:00+07:00'):
    return {'source': source, 'url': f'https://{source}.vn/article-1', 'title': title,
            'content': body or 'FPT ghi nhận 181.748 cổ đông sau khi phân phối 171,4 triệu cổ phiếu. Nhà đầu tư nhỏ lẻ tăng mạnh trong năm nay.',
            'published_at': date, 'marker': 'uncheck'}


class EventTests(unittest.TestCase):
    def save(self, root, source, scope, day, row):
        path = daily_path(root, source, scope, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'articles': [row]}, ensure_ascii=False), encoding='utf-8')
        return path

    def test_rewritten_titles_and_preserve_input(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            a = article('cafef', body='FPT có 181.748 cổ đông. Tập đoàn đã phát hành 171,4 triệu cổ phiếu. Nhà đầu tư cá nhân tăng nhanh nhờ chia cổ phiếu thưởng cho cổ đông.')
            b = article('fireant', title='FPT: Số cổ đông tăng lên 181.748 người', body='Sau phát hành 171,4 triệu cổ phiếu, số cổ đông FPT đạt 181.748 người. Cổ đông cá nhân tăng nhanh trong tập đoàn công nghệ.')
            paths = [self.save(root, 'cafef', 'FPT', '01-10-2026', a),
                     self.save(root, 'fireant', 'FPT', '01-10-2026', b)]
            before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            report = analysis.analyze(root)
            self.assertEqual(report['summary']['unique_uncheck_articles_with_rewritten_candidates'], 2)
            self.assertEqual(report['candidates'][0]['status'], 'possible_rewritten_event')
            self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})

    def test_same_title_disclosure_separate_and_dedup_days(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            a = article('cafef', 'FPT: Thông báo số lượng cổ phiếu có quyền biểu quyết', 'FPT thông báo cổ phiếu có quyền biểu quyết. Các tập tin đính kèm báo cáo chi tiết danh sách toàn bộ cổ đông và ngày thực hiện theo HOSE.')
            b = article('fireant', a['title'], 'FPT thông báo cổ phiếu có quyền biểu quyết.')
            for day in ('01-10-2026', '02-10-2026'):
                self.save(root, 'cafef', 'FPT', day, a)
            self.save(root, 'fireant', 'FPT', '01-10-2026', b)
            report = analysis.analyze(root)
            self.assertEqual(report['summary']['uncheck_records'], 3)
            self.assertEqual(report['summary']['unique_uncheck_articles'], 2)
            self.assertEqual(report['summary']['unique_candidate_pairs'], 1)
            self.assertEqual(report['candidates'][0]['status'], 'same_title_low_body_overlap')
            self.assertEqual(report['summary']['unique_uncheck_articles_with_rewritten_candidates'], 0)

    def test_date_window_and_scope_isolation(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            self.save(root, 'cafef', 'FPT', '01-10-2026', article('cafef'))
            self.save(root, 'fireant', 'HPG', '01-10-2026', article('fireant'))
            self.assertEqual(analysis.analyze(root)['summary']['unique_candidate_pairs'], 0)
            self.save(root, 'fireant', 'FPT', '01-10-2026', article('fireant', body='FPT có thêm cổ đông trong tháng này.', date='2026-08-01T10:00:00+07:00'))
            self.assertEqual(analysis.analyze(root)['summary']['unique_candidate_pairs'], 0)

    def test_different_resolution_not_same_event(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            self.save(root, 'cafef', 'TPB', '01-10-2026', article('cafef', 'TPB nghị quyết số 35/2026 phát hành trái phiếu'))
            self.save(root, 'fireant', 'TPB', '01-10-2026', article('fireant', 'TPB nghị quyết số 37/2026 phát hành trái phiếu'))
            self.assertEqual(analysis.analyze(root)['summary']['unique_candidate_pairs'], 0)

    def test_naive_time_and_number_anchors(self):
        self.assertEqual(analysis.published('2026-09-29T10:00:00'), analysis.published('2026-09-29T03:00:00Z'))
        self.assertIsNone(analysis.published('bad date'))
        self.assertEqual(analysis.specific_numbers('2026 29 181.748 171,4'), {'181.748', '171,4'})

    def test_missing_date_and_same_topic_insufficient(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder:
            root = Path(folder)
            self.save(root, 'cafef', 'FPT', '01-10-2026', article('cafef', 'FPT chia cổ tức năm nay', 'FPT chia cổ tức tiền mặt cho người nắm giữ.'))
            self.save(root, 'fireant', 'FPT', '01-10-2026', article('fireant', 'FPT chuẩn bị trả cổ tức', 'FPT trả cổ tức bằng cổ phiếu vào năm sau.', date=None))
            self.assertEqual(analysis.analyze(root)['summary']['unique_candidate_pairs'], 0)


if __name__ == '__main__':
    unittest.main()
