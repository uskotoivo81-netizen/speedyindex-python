"""Python client and CLI for the SpeedyIndex API v2."""

from .client import DEFAULT_BASE_URL, SpeedyIndex, SpeedyIndexError

__all__ = ["SpeedyIndex", "SpeedyIndexError", "DEFAULT_BASE_URL"]
__version__ = "0.1.0"
