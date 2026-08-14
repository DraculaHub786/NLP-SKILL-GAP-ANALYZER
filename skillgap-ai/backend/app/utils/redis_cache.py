"""Redis helpers for anonymous, TTL-scoped session caching.

The /analyze endpoint persists only the already-anonymized GapReport JSON —
never raw text — keyed by a session UUID (client-provided, or generated
server-side), with a 48h Redis-native EXPIRE. Fail-soft policy: if Redis is
unreachable (any connection/command error, not just RedisError subclasses)
the endpoint still returns the report; cache operations degrade to None/False
with a rate-limited warning log.
"""
import re
import time
import uuid

from app.core.config import get_redis, settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_SESSION_PREFIX = "session:"
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")

_last_warned_at = 0.0
_WARN_COOLDOWN_SECONDS = 60


def _warn_once(exc: Exception) -> None:
    global _last_warned_at
    now = time.monotonic()
    if now - _last_warned_at > _WARN_COOLDOWN_SECONDS:
        logger.warning("redis_unavailable_cache_degraded", error=str(exc))
        _last_warned_at = now


def is_valid_session_id(session_id: str) -> bool:
    return bool(_SESSION_ID_PATTERN.match(session_id or ""))


def cache_report_json(payload_json: str, session_id: str | None = None) -> str | None:
    """Stores an anonymized gap report under a session id. Returns the id."""
    if session_id and not is_valid_session_id(session_id):
        raise ValueError("Invalid session id.")
    key = f"{_SESSION_PREFIX}{session_id or uuid.uuid4()}"
    try:
        get_redis().setex(key, settings.session_ttl_seconds, payload_json)
        return key.removeprefix(_SESSION_PREFIX)
    except Exception as exc:
        _warn_once(exc)
        return None


def get_report_json(session_id: str) -> str | None:
    if not is_valid_session_id(session_id):
        return None
    try:
        return get_redis().get(f"{_SESSION_PREFIX}{session_id}")
    except Exception as exc:
        _warn_once(exc)
        return None


def delete_session(session_id: str) -> bool:
    if not is_valid_session_id(session_id):
        return False
    try:
        return bool(get_redis().delete(f"{_SESSION_PREFIX}{session_id}"))
    except Exception as exc:
        _warn_once(exc)
        return False
