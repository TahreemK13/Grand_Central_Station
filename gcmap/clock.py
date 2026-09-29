"""Time: every timestamp is stored as UTC ISO 8601 and shown in Pacific time."""
import os
from datetime import datetime, timezone

from .settings import PACIFIC


def now():
    """Current UTC time. GC_NOW (ISO 8601) overrides it, to test the settle window."""
    return when(os.environ["GC_NOW"]) if os.environ.get("GC_NOW") else datetime.now(timezone.utc)


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def pt(t):
    t = t.astimezone(PACIFIC)
    return f"{t:%a %b} {t.day}, {t.hour % 12 or 12}:{t:%M} {'am' if t.hour < 12 else 'pm'} {t:%Z}"
