"""Python client and CLI for the SpeedyIndex API v2: indexing, index checks and Rank Tracker."""

from .client import DEFAULT_BASE_URL, SpeedyIndex, SpeedyIndexError
from .rank import RankTracker
from .webhooks import parse_event, verify_signature

__all__ = ["SpeedyIndex", "SpeedyIndexError", "RankTracker", "DEFAULT_BASE_URL", "verify_signature", "parse_event"]
__version__ = "0.2.0"
