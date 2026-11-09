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


class RankAndWebhookTests(unittest.TestCase):
    def setUp(self):
        self.si = SpeedyIndex(api_key="k")

    def test_rank_pagination_and_query(self):
        pages = [
            {"code": 0, "items": [{"q": "a"}], "next_cursor": "c1"},
            {"code": 0, "items": [{"q": "b"}], "next_cursor": None},
        ]
        urls = []

        def fake(req, timeout=None):
            urls.append(req.full_url)
            return FakeResp(pages.pop(0))

        with mock.patch("urllib.request.urlopen", fake):
            rows = list(self.si.rank.positions("p1", changed_only=True))
        self.assertEqual([r["q"] for r in rows], ["a", "b"])
        self.assertIn("/v2/rank-tracker/projects/p1/positions?changed_only=true", urls[0])
        self.assertIn("cursor=c1", urls[1])

    def test_rank_create_project_body(self):
        calls = []

        def fake(req, timeout=None):
            calls.append(req)
            return FakeResp({"code": 0, "project": {"id": "x"}})

        with mock.patch("urllib.request.urlopen", fake):
            self.si.rank.create_project("example.com", [{"location": "New York,New York,United States", "gl": "us"}],
                                        keywords=["pizza"], ref="r1", depth=30)
        body = json.loads(calls[0].data)
        self.assertEqual(body["domain"], "example.com")
        self.assertEqual(body["keywords"], ["pizza"])
        self.assertEqual(body["ref"], "r1")
        self.assertEqual(calls[0].get_method(), "POST")

    def test_http_error_body_is_parsed(self):
        import io
        import urllib.error

        def fake(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 410, "Gone", {"Retry-After": "5"},
                                         io.BytesIO(b'{"code":1,"error":"rows_expired","message":"old"}'))

        with mock.patch("urllib.request.urlopen", fake), self.assertRaises(SpeedyIndexError) as ctx:
            self.si.rank.check("c1")
        self.assertEqual(ctx.exception.status, 410)
        self.assertEqual(ctx.exception.error, "rows_expired")
        self.assertEqual(ctx.exception.retry_after, 5.0)

    def test_webhook_signature(self):
        from speedyindex.webhooks import parse_event, sign, verify_signature

        body = b'{"event":"check.finished","event_id":"e1"}'
        good = sign(body, "whsec_new")
        old = sign(body, "whsec_old")
        self.assertTrue(verify_signature(body, good, "whsec_new"))
        self.assertTrue(verify_signature(body, f"{good}, {old}", "whsec_old"))
        self.assertFalse(verify_signature(body, good, "whsec_other"))
        self.assertFalse(verify_signature(body, None, "whsec_new"))
        self.assertEqual(parse_event(body, good, "whsec_new")["event_id"], "e1")
        with self.assertRaises(ValueError):
            parse_event(body, "sha256=00", "whsec_new")


if __name__ == "__main__":
    unittest.main()
