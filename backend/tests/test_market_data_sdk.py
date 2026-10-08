"""Verify persistent IPC and child session guard without any provider request."""
import io
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

from backend.src.market_data.sdk import BatchSDKClient
from backend.src.market_data.sdk_worker import main
from backend.tests.test_market_data_live import quote


class SDKTests(unittest.TestCase):
    def setUp(self):
        self.client = BatchSDKClient(Path.cwd(), timeout=0.01)
        self.process = Mock()
        self.process.poll.return_value = None
        self.client.process = self.process
        self.client.responses = queue.Queue()

    def tearDown(self):
        self.client.close()

    def test_reuses_process_and_preserves_batch_and_automatic_flag(self):
        self.client.responses.put(json.dumps({"rows": [quote()]}))
        self.client.responses.put(json.dumps({"rows": [quote("VCB")]}))
        self.client(["FPT", "VCB"], automatic=True)
        self.client(["VCB"])
        writes = self.process.stdin.write.call_args_list
        self.assertEqual(json.loads(writes[0].args[0]), {"symbols": ["FPT", "VCB"], "automatic": True})
        self.assertFalse(json.loads(writes[1].args[0])["automatic"])
        self.process.kill.assert_not_called()

    def test_normal_sdk_error_keeps_quota_process_but_eof_restarts_only_after_cooldown(self):
        self.client.responses.put('{"error":"source limited"}')
        with self.assertRaises(RuntimeError):
            self.client(["FPT"])
        self.assertIs(self.client.process, self.process)
        self.client.responses.put(None)
        with self.assertRaises(RuntimeError):
            self.client(["FPT"])
        self.assertIsNone(self.client.process)
        self.assertGreater(self.client.restart_after, time.monotonic())
        with patch("backend.src.market_data.sdk.subprocess.Popen") as spawn:
            with self.assertRaises(RuntimeError):
                self.client(["FPT"])
            spawn.assert_not_called()

    def test_timeout_and_invalid_json_close_child_and_keep_error_sanitized(self):
        with self.assertRaisesRegex(RuntimeError, "SDK không phản hồi"):
            self.client(["FPT"])
        self.process.kill.assert_called_once()
        self.assertIsNone(self.client.process)

    def test_invalid_input_never_reaches_process(self):
        for symbols in ([], ["../FPT"], ["FPT"] * 101):
            with self.assertRaises(ValueError):
                self.client(symbols)
        self.process.stdin.write.assert_not_called()

    def test_index_history_shares_same_ipc_and_rejects_unknown_index(self):
        self.client.responses.put(json.dumps({"rows": []}))
        self.client.history("HNXINDEX")
        self.assertEqual(json.loads(self.process.stdin.write.call_args.args[0]),
                         {"action": "index_history", "symbol": "HNXINDEX"})
        with self.assertRaises(ValueError):
            self.client.history("../FPT")

    def test_start_child_is_bounded_and_read_only_toward_old_crawler(self):
        self.client.process = None
        child = Mock()
        child.stdout.readline.return_value = ""
        with patch("backend.src.market_data.sdk.subprocess.Popen", return_value=child) as spawn:
            self.client._start()
            args, kwargs = spawn.call_args
            self.assertIn("-B", args[0])
            self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertIn("market-live", kwargs["env"]["FINMIND_LIVE_SDK_HOME"])
            self.assertEqual(self.client.responses.get(timeout=1), None)


class SDKChildTests(unittest.TestCase):
    def run_child(self, request, *, session_open=True):
        with tempfile.TemporaryDirectory() as folder:
            frame = MagicMock()
            frame.copy.return_value = frame
            frame.to_json.return_value = json.dumps([quote()])
            market = Mock()
            market.quote.return_value = frame
            market.index.return_value.ohlcv.return_value = frame
            market.equity.return_value.ohlcv.return_value = frame
            module = types.ModuleType("vnstock")
            module.Market = Mock(return_value=market)
            output = io.StringIO()
            with patch.dict(sys.modules, {"vnstock": module}), patch.dict(os.environ, {"FINMIND_LIVE_SDK_HOME": folder}), \
                 patch.object(sys, "stdin", io.StringIO(request + "\n")), patch.object(sys, "stdout", output), \
                 patch("backend.src.market_data.session.SessionGate", return_value=lambda _: session_open):
                main()
            return json.loads(output.getvalue()), market

    def test_batch_goes_to_public_sdk_once(self):
        result, market = self.run_child('{"symbols":["FPT","VCB","FPT"],"automatic":true}')
        market.quote.assert_called_once_with(symbol=["FPT", "VCB"], get_all=True)
        self.assertEqual(result["rows"][0]["close_price"], "61000")

    def test_index_history_calls_public_index_api_only(self):
        result, market = self.run_child('{"action":"index_history","symbol":"UPCOMINDEX"}')
        self.assertIn("rows", result)
        market.index.assert_called_once_with("UPCOMINDEX")
        self.assertEqual(market.index.return_value.ohlcv.call_args.kwargs["interval"], "1D")
        self.assertEqual(market.index.return_value.ohlcv.call_args.kwargs["count"], 250)
        market.quote.assert_not_called()
        result, market = self.run_child('{"action":"index_history","symbol":"../FPT"}')
        self.assertIn("error", result)
        market.index.assert_not_called()

    def test_closed_session_is_checked_in_child_after_sdk_startup(self):
        result, market = self.run_child('{"symbols":["FPT"],"automatic":true}', session_open=False)
        self.assertIn("error", result)
        market.quote.assert_not_called()
        result, market = self.run_child('{"symbols":["FPT"],"automatic":false}', session_open=False)
        self.assertIn("rows", result)
        market.quote.assert_called_once()

    def test_stock_history_uses_equity_and_preserves_sdk_price_strings(self):
        result, market = self.run_child('{"action":"stock_history","symbol":"CTR"}', session_open=False)
        self.assertIn("rows", result)
        market.equity.assert_called_once_with("CTR")
        self.assertEqual(market.equity.return_value.ohlcv.call_args.kwargs["count"], 250)
        market.index.assert_not_called()
        market.quote.assert_not_called()

    def test_bad_requests_are_rejected_without_sdk_call(self):
        for request in ('{"symbols":[]}', '{"symbols":["../FPT"]}', 'invalid', 'x' * 4097):
            result, market = self.run_child(request)
            self.assertIn("error", result)
            market.quote.assert_not_called()


if __name__ == "__main__":
    unittest.main()
