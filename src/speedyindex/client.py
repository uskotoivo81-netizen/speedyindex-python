"""Minimal client for the SpeedyIndex API v2 (standard library only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_BASE_URL = "https://api.speedyindex.com"
ENGINES = ("google", "yandex", "bing")
TASK_TYPES = ("indexer", "checker")
MAX_URLS_PER_TASK = 10_000
MAX_TASK_IDS = 1_000


class SpeedyIndexError(Exception):
    """Raised when the API returns a non-zero code or an HTTP error."""

    def __init__(self, message: str, code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.code = code
        self.payload = payload


def _check_engine(engine: str, task_type: Optional[str] = None) -> None:
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of {ENGINES}, got {engine!r}")
    if task_type is not None:
        if task_type not in TASK_TYPES:
            raise ValueError(f"task_type must be one of {TASK_TYPES}, got {task_type!r}")
        if engine == "bing" and task_type != "checker":
            raise ValueError("Bing supports only the 'checker' task type")


def _clean_urls(urls: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for url in urls:
        url = url.strip()
        if url and not url.startswith("#") and url not in seen:
            seen.add(url)
            result.append(url)
    return result


class SpeedyIndex:
    """Client for the SpeedyIndex API v2.

    The API key is read from ``api_key`` or the ``SPEEDYINDEX_API_KEY``
    environment variable. It is sent in the ``Authorization`` header.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("SPEEDYINDEX_API_KEY")
        if not self.api_key:
            raise SpeedyIndexError(
                "No API key: pass api_key=... or set SPEEDYINDEX_API_KEY"
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- transport -------------------------------------------------------
    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Authorization", self.api_key)
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "speedyindex-python")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise SpeedyIndexError(f"HTTP {exc.code} for {path}", code=exc.code) from exc
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise SpeedyIndexError(f"Non-JSON response for {path}", payload=raw) from exc
        code = payload.get("code") if isinstance(payload, dict) else None
        if code not in (0, None):
            messages = {1: "insufficient balance", 2: "validation error"}
            raise SpeedyIndexError(
                f"API error {code}: {messages.get(code, 'see payload')}", code=code, payload=payload
            )
        return payload

    # -- account ---------------------------------------------------------
    def balance(self) -> Dict[str, Any]:
        """GET /v2/account - current balance."""
        return self._request("GET", "/v2/account")["balance"]

    # -- tasks -----------------------------------------------------------
    def create_task(
        self,
        urls: Iterable[str],
        engine: str = "google",
        task_type: str = "checker",
        title: Optional[str] = None,
        pay_per_indexed: Optional[bool] = None,
        drip_feed: bool = False,
        drip_feed_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """POST /v2/task/<engine>/<type>/create.

        For ``google``/``indexer`` the API accepts only ``pay_per_indexed=True``,
        so it is set automatically. Up to 10,000 URLs per request.
        """
        _check_engine(engine, task_type)
        url_list = _clean_urls(urls)
        if not url_list:
            raise ValueError("urls is empty")
        if len(url_list) > MAX_URLS_PER_TASK:
            raise ValueError(f"max {MAX_URLS_PER_TASK} URLs per task, got {len(url_list)}")
        body: Dict[str, Any] = {"urls": url_list}
        if title:
            body["title"] = title
        if engine == "google" and task_type == "indexer":
            pay_per_indexed = True
        if pay_per_indexed is not None:
            body["pay_per_indexed"] = pay_per_indexed
        if drip_feed:
            if not drip_feed_days or not 2 <= drip_feed_days <= 30:
                raise ValueError("drip_feed_days must be between 2 and 30")
            if len(url_list) < drip_feed_days:
                raise ValueError("number of URLs must be >= drip_feed_days")
            body["drip_feed"] = True
            body["drip_feed_days"] = drip_feed_days
        return self._request("POST", f"/v2/task/{engine}/{task_type}/create", body)

    def list_tasks(self, engine: str = "google", page: int = 0) -> Dict[str, Any]:
        """GET /v2/task/<engine>/list/<page> - 1000 tasks per page, newest first."""
        _check_engine(engine)
        return self._request("GET", f"/v2/task/{engine}/list/{int(page)}")

    def task_status(self, task_ids: Iterable[str], engine: str = "google", task_type: str = "checker") -> Dict[str, Any]:
        """POST /v2/task/<engine>/<type>/status - up to 1000 task IDs."""
        _check_engine(engine, task_type)
        ids = list(task_ids)
        if len(ids) > MAX_TASK_IDS:
            raise ValueError(f"max {MAX_TASK_IDS} task IDs per request")
        return self._request("POST", f"/v2/task/{engine}/{task_type}/status", {"task_ids": ids})

    def full_report(self, task_id: str, engine: str = "google", task_type: str = "checker") -> Dict[str, Any]:
        """POST /v2/task/<engine>/<type>/fullreport - indexed and unindexed links."""
        _check_engine(engine, task_type)
        return self._request("POST", f"/v2/task/{engine}/{task_type}/fullreport", {"task_id": task_id})

    # -- single link -----------------------------------------------------
    def index_url(self, url: str, engine: str = "google") -> Dict[str, Any]:
        """POST /v2/<engine>/url - submit one link (google or yandex)."""
        if engine not in ("google", "yandex"):
            raise ValueError("single-link submission supports google and yandex")
        return self._request("POST", f"/v2/{engine}/url", {"url": url})

    # -- backlink checker ------------------------------------------------
    def create_backlink_check(self, urls: Iterable[str], target_domains: Iterable[str]) -> Dict[str, Any]:
        """POST /v2/task/backlink/checker/create - look for links to your domains on donor pages."""
        url_list = _clean_urls(urls)
        if not url_list:
            raise ValueError("urls is empty")
        if len(url_list) > MAX_URLS_PER_TASK:
            raise ValueError(f"max {MAX_URLS_PER_TASK} URLs per task")
        return self._request(
            "POST",
            "/v2/task/backlink/checker/create",
            {"urls": url_list, "target_domains": list(target_domains)},
        )

    def backlink_report(self, task_id: str, page: int = 0, limit: int = 50) -> Dict[str, Any]:
        """POST /v2/task/backlink/checker/report - per-donor details."""
        return self._request(
            "POST",
            "/v2/task/backlink/checker/report",
            {"task_id": task_id, "page": page, "limit": limit},
        )
