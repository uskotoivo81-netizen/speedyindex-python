"""Verify Rank Tracker webhook signatures (``X-SpeedyIndex-Signature``)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, Optional, Union

SIGNATURE_HEADER = "X-SpeedyIndex-Signature"
EVENT_HEADER = "X-SpeedyIndex-Event"
EVENT_ID_HEADER = "X-SpeedyIndex-Event-Id"


def sign(body: bytes, secret: str) -> str:
    """``sha256=`` + hex HMAC-SHA256 of the raw body with the webhook secret as key."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: Union[bytes, str], header: Optional[str], secret: str) -> bool:
    """True if any signature in the header matches the raw body.

    During secret rotation the header carries two comma-separated signatures,
    the new one first; either is accepted. Compute over the bytes as received,
    before parsing the JSON.
    """
    if not header or not secret:
        return False
    raw = body.encode("utf-8") if isinstance(body, str) else body
    expected = sign(raw, secret)
    return any(hmac.compare_digest(part.strip(), expected) for part in header.split(","))


def parse_event(body: Union[bytes, str], header: Optional[str], secret: str) -> Dict[str, Any]:
    """Verify and parse a webhook body; raises ``ValueError`` on a bad signature.

    Events: ``check.finished``, ``check.failed``, ``check.skipped`` and ``webhook.test``.
    A delivery may repeat: process each ``event_id`` once.
    """
    if not verify_signature(body, header, secret):
        raise ValueError("invalid SpeedyIndex webhook signature")
    raw = body.decode("utf-8") if isinstance(body, bytes) else body
    return json.loads(raw)
