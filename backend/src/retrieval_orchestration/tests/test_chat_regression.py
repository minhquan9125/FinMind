"""User-reported terminal regressions, exercised through the actual CLI."""
import asyncio
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import hoi


class TerminalRegressionTests(unittest.TestCase):
    def chat(self, *messages):
        output = io.StringIO()
        with patch('builtins.input', side_effect=[*messages, 'exit']), redirect_stdout(output):
            asyncio.run(hoi.main())
        return output.getvalue()

    def test_default_output_is_readable_without_raw_json(self):
        output = self.chat('Tổng tài sản BID tại 30/06/2026?')
        self.assertNotIn('"request_id":', output)
        self.assertIn('giả lập', output.lower())

    def test_company_and_metric_replies_keep_the_original_year(self):
        output = self.chat('lợi nhuận năm 2025 là bao nhiêu', 'BID', 'sau thuế')
        self.assertIn('BID', output)
        self.assertIn('2025', output)
        self.assertIn('chưa tìm thấy', output.lower())

    def test_mixed_case_unsupported_ticker_is_not_missing_company(self):
        output = self.chat('cho t xem lợi nhuận ssi')
        self.assertIn('SSI', output)
        self.assertIn('ngoài', output.lower())


if __name__ == '__main__':
    unittest.main()
