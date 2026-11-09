"""SpeedyIndex Rank Tracker API (``/v2/rank-tracker``): Google positions from your own code."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Optional, Union

if TYPE_CHECKING:  # pragma: no cover
    from .client import SpeedyIndex

BASE = "/v2/rank-tracker"
Keyword = Union[str, Dict[str, Any]]


class RankTracker:
    """Projects, keywords, regions, checks, positions and webhooks.

    Use it through ``SpeedyIndex().rank``. Projects are shared with the
    dashboard: a project created here appears there, and the other way round.
    """

    def __init__(self, client: "SpeedyIndex") -> None:
        self._c = client

    # -- helpers ---------------------------------------------------------
    def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        return self._c._request("GET", BASE + path, params=params)

    def _send(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._c._request(method, BASE + path, body if body is not None else {})

    def paginate(self, path: str, **params: Any) -> Iterator[Dict[str, Any]]:
        """Yield every item of a cursor-paginated list until ``next_cursor`` is null."""
        cursor = None
        while True:
            page = self._get(path, cursor=cursor, **params)
            for item in page.get("items", []):
                yield item
            cursor = page.get("next_cursor")
            if not cursor:
                return

    # -- account and reference --------------------------------------------
    def limits(self) -> Dict[str, Any]:
        """Limits, current prices, balance and tokens held by running checks."""
        return self._get("/limits")

    def locations(self, q: str, gl: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find Google locations; use ``canonical_name`` as a region's location and ``country_code`` as ``gl``."""
        return self._get("/locations", q=q, gl=gl, limit=limit)["locations"]

    def groups(self) -> List[Dict[str, Any]]:
        return self._get("/groups")["items"]

    def usage(self, date_from: Optional[str] = None, date_to: Optional[str] = None, tz: Optional[str] = None,
              group: Optional[str] = None, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Tokens spent on checks by day and by project (last 30 days by default)."""
        return self._get("/usage", **{"from": date_from, "to": date_to, "tz": tz, "group": group, "project_id": project_id})

    # -- projects ----------------------------------------------------------
    def projects(self, sort: Optional[str] = None, archived: Optional[bool] = None, group: Optional[str] = None,
                 search: Optional[str] = None, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """Iterate over all projects (active by default)."""
        return self.paginate("/projects", sort=sort, archived=archived, group=group, search=search, limit=limit)

    def create_project(self, domain: str, regions: List[Dict[str, Any]], keywords: Optional[Iterable[Keyword]] = None,
                       ref: Optional[str] = None, **fields: Any) -> Dict[str, Any]:
        """Create a project. ``regions``: ``[{"location": ..., "gl": "us", "device": "desktop"}]``.

        Extra fields: ``name``, ``depth`` (10/30/50/100), ``competitors``, ``schedule``
        (``{"days": [1, 4], "hour": 6, "tz": "Europe/London"}``), ``group``, ``tags``,
        ``webhook_url``, ``check_emails``. Pass ``ref`` to make the request safe to repeat.
        """
        body: Dict[str, Any] = {"domain": domain, "regions": regions, **fields}
        if keywords is not None:
            body["keywords"] = list(keywords)
        if ref:
            body["ref"] = ref
        return self._send("POST", "/projects", body)

    def project(self, project_id: str) -> Dict[str, Any]:
        """The project with its tags, cost of the next check, active and last checks."""
        return self._get(f"/projects/{project_id}")

    def update_project(self, project_id: str, **fields: Any) -> Dict[str, Any]:
        return self._send("PATCH", f"/projects/{project_id}", fields)["project"]

    def delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete a project with its keywords and history (cannot be undone)."""
        return self._c._request("DELETE", f"{BASE}/projects/{project_id}")

    def bulk(self, ids: List[str], action: str, **fields: Any) -> List[Dict[str, Any]]:
        """One action for up to 500 projects: archive, unarchive, delete, set_schedule, set_group or check."""
        return self._send("POST", "/projects/bulk", {"ids": ids, "action": action, **fields})["results"]

    def summary(self, project_ids: List[str]) -> Dict[str, Any]:
        return self._send("POST", "/projects/summary", {"project_ids": project_ids})

    # -- regions -------------------------------------------------------------
    def add_region(self, project_id: str, location: str, gl: str, device: Optional[str] = None) -> Dict[str, Any]:
        body = {"location": location, "gl": gl}
        if device:
            body["device"] = device
        return self._send("POST", f"/projects/{project_id}/regions", body)

    def remove_region(self, project_id: str, region_id: str) -> Dict[str, Any]:
        return self._c._request("DELETE", f"{BASE}/projects/{project_id}/regions/{region_id}")

    # -- keywords and tags ---------------------------------------------------
    def keywords(self, project_id: str, tag: Optional[str] = None, search: Optional[str] = None,
                 limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        return self.paginate(f"/projects/{project_id}/keywords", tag=tag, search=search, limit=limit)

    def add_keywords(self, project_id: str, keywords: Iterable[Keyword], tags: Optional[List[str]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"keywords": list(keywords)}
        if tags:
            body["tags"] = tags
        return self._send("POST", f"/projects/{project_id}/keywords", body)

    def replace_keywords(self, project_id: str, keywords: Iterable[Keyword], tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Make the keyword list exactly this one; missing keywords are removed with their history."""
        body: Dict[str, Any] = {"keywords": list(keywords)}
        if tags:
            body["tags"] = tags
        return self._send("PUT", f"/projects/{project_id}/keywords", body)

    def edit_keywords(self, project_id: str, ids: List[str], add_tags: Optional[List[str]] = None,
                      remove_tags: Optional[List[str]] = None, target_url: Any = ...) -> Dict[str, Any]:
        body: Dict[str, Any] = {"ids": ids}
        if add_tags:
            body["add_tags"] = add_tags
        if remove_tags:
            body["remove_tags"] = remove_tags
        if target_url is not ...:
            body["target_url"] = target_url
        return self._send("PATCH", f"/projects/{project_id}/keywords", body)

    def delete_keywords(self, project_id: str, ids: List[str]) -> int:
        return self._send("POST", f"/projects/{project_id}/keywords/delete", {"ids": ids})["deleted"]

    def keyword_history(self, project_id: str, keyword_id: str, region_id: Optional[str] = None,
                        limit: Optional[int] = None) -> Dict[str, Any]:
        return self._get(f"/projects/{project_id}/keywords/{keyword_id}/history", region_id=region_id, limit=limit)

    def tags(self, project_id: str) -> List[Dict[str, Any]]:
        return self._get(f"/projects/{project_id}/tags")["items"]

    def rename_tag(self, project_id: str, old: str, new: str) -> List[str]:
        return self._send("POST", f"/projects/{project_id}/tags/rename", {"from": old, "to": new})["tags"]

    def set_tag_color(self, project_id: str, tag: str, color: Optional[str]) -> Dict[str, Any]:
        return self._send("POST", f"/projects/{project_id}/tags/color", {"tag": tag, "color": color})["tag_colors"]

    # -- checks ---------------------------------------------------------------
    def cost(self, project_id: str, region_id: Optional[str] = None) -> Dict[str, Any]:
        """What the project's next check can cost, in tokens."""
        return self._get(f"/projects/{project_id}/cost", region_id=region_id)

    def run_check(self, project_id: str, region_id: Optional[str] = None) -> Dict[str, Any]:
        """Queue a check; ``cost.max`` is held from the balance and the unspent part comes back."""
        body = {"region_id": region_id} if region_id else {}
        return self._send("POST", f"/projects/{project_id}/checks", body)["check"]

    def checks(self, project_id: str, region_id: Optional[str] = None, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        return self.paginate(f"/projects/{project_id}/checks", region_id=region_id, limit=limit)

    def check(self, check_id: str) -> Dict[str, Any]:
        return self._get(f"/checks/{check_id}")["check"]

    def checks_status(self, check_ids: List[str]) -> Dict[str, Any]:
        return self._send("POST", "/checks/status", {"check_ids": check_ids})

    def cancel_check(self, check_id: str) -> Dict[str, Any]:
        return self._send("POST", f"/checks/{check_id}/cancel")["check"]

    def wait(self, check_id: str, interval: float = 30.0, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Poll a check every ``interval`` seconds (15-60 is recommended) until it is no longer queued or running."""
        started = time.monotonic()
        while True:
            check = self.check(check_id)
            if check.get("status") not in ("queued", "running"):
                return check
            if timeout is not None and time.monotonic() - started > timeout:
                return check
            time.sleep(interval)

    # -- results --------------------------------------------------------------
    def positions(self, project_id: str, check_id: Optional[str] = None, region_id: Optional[str] = None,
                  tag: Optional[str] = None, changed_only: Optional[bool] = None,
                  limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """Every keyword's result in a check (latest finished by default), with the change against the previous one."""
        return self.paginate(f"/projects/{project_id}/positions", check_id=check_id, region_id=region_id,
                             tag=tag, changed_only=changed_only, limit=limit)

    def trend(self, project_id: str, region_id: Optional[str] = None) -> Dict[str, Any]:
        return self._get(f"/projects/{project_id}/trend", region_id=region_id)

    def keyword_in_check(self, check_id: str, keyword_id: str, region_id: Optional[str] = None) -> Dict[str, Any]:
        """One keyword in a finished check, with the top 10 domains and the AI Overview (cited or not)."""
        return self._get(f"/checks/{check_id}/keywords/{keyword_id}", region_id=region_id)

    def export(self, project_id: str, format: str = "csv", check_id: Optional[str] = None,
               region_id: Optional[str] = None, tag: Optional[str] = None) -> bytes:
        """All positions of a check as CSV (UTF-8 with BOM) or JSON bytes."""
        params = {"format": format, "check_id": check_id, "region_id": region_id, "tag": tag}
        return self._c._raw("GET", f"{BASE}/projects/{project_id}/export", params=params)

    # -- webhooks -------------------------------------------------------------
    def webhook(self) -> Dict[str, Any]:
        return self._get("/webhook")["webhook"]

    def set_webhook(self, url: str, events: Optional[List[str]] = None) -> Dict[str, Any]:
        """Set the account webhook. The first answer has ``secret`` (whsec_...): store it, it is shown once."""
        body: Dict[str, Any] = {"url": url}
        if events is not None:
            body["events"] = events
        return self._send("PUT", "/webhook", body)

    def remove_webhook(self) -> Dict[str, Any]:
        return self._c._request("DELETE", f"{BASE}/webhook")["webhook"]

    def rotate_webhook_secret(self) -> Dict[str, Any]:
        return self._send("POST", "/webhook/secret")

    def test_webhook(self, url: Optional[str] = None) -> Dict[str, Any]:
        return self._send("POST", "/webhook/test", {"url": url} if url else {})["delivery"]

    def deliveries(self, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        return self.paginate("/webhook/deliveries", limit=limit)

    def redeliver(self, delivery_id: str) -> Dict[str, Any]:
        return self._send("POST", f"/webhook/deliveries/{delivery_id}/redeliver")
