import json
import unittest
from unittest import mock

from speedyindex import SpeedyIndex, SpeedyIndexError
from speedyindex.cli import main


class FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.si = SpeedyIndex(api_key="k")

    def _capture(self, payload):
        calls = []

        def fake(req, timeout=None):
            calls.append(req)
            return FakeResp(payload)

        return calls, mock.patch("urllib.request.urlopen", fake)

    def test_balance_and_auth_header(self):
        calls, p = self._capture({"code": 0, "balance": {"tokens": 1}})
        with p:
            self.assertEqual(self.si.balance(), {"tokens": 1})
        self.assertEqual(calls[0].get_header("Authorization"), "k")
        self.assertTrue(calls[0].full_url.endswith("/v2/account"))

    def test_google_indexer_forces_pay_per_indexed_and_dedupes(self):
        calls, p = self._capture({"code": 0, "task_id": "x"})
        with p:
            self.si.create_task(["https://a/", "https://a/", "#c", "https://b/"], task_type="indexer")
        body = json.loads(calls[0].data)
        self.assertEqual(body["urls"], ["https://a/", "https://b/"])
        self.assertTrue(body["pay_per_indexed"])
        self.assertTrue(calls[0].full_url.endswith("/v2/task/google/indexer/create"))

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.si.create_task(["https://a/"], engine="bing", task_type="indexer")
        with self.assertRaises(ValueError):
            self.si.create_task(["https://a/"], drip_feed=True, drip_feed_days=2)
        with self.assertRaises(ValueError):
            self.si.create_task([])

    def test_api_error(self):
        _, p = self._capture({"code": 1})
        with p, self.assertRaises(SpeedyIndexError) as ctx:
            self.si.balance()
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SpeedyIndexError):
                SpeedyIndex()

    def test_cli_balance(self):
        _, p = self._capture({"code": 0, "balance": {"tokens": 5}})
        with p, mock.patch.dict("os.environ", {"SPEEDYINDEX_API_KEY": "k"}):
            self.assertEqual(main(["balance"]), 0)


if __name__ == "__main__":
    unittest.main()
