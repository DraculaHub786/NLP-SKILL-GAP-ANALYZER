"""Per-IP sliding-window rate limiting backed by Redis.

Costly NLP endpoints are the abuse surface (file parsing + embedding calls),
so /parse/* and /analyze are limited hardest. Rate limiting is fail-open:
if Redis is unreachable, requests pass through rather than the whole API
going down (the same policy as the session cache).
"""
import time

import redis as redis_lib
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_redis, settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

RATE_LIMIT_WINDOW_SECONDS = 60

# Heavier NLP endpoints get a stricter cap than cheap introspection ones.
_STRICT_PREFIXES = ("/api/v1/parse", "/api/v1/analyze")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        limit = settings.rate_limit_per_minute
        if path.startswith(_STRICT_PREFIXES):
            limit = min(limit, 30)

        ip = _client_ip(request)
        key = f"ratelimit:{ip}:{path}"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS

        try:
            redis = get_redis()
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, RATE_LIMIT_WINDOW_SECONDS)
            _requests = pipe.execute()
            count = int(_requests[2])
        except redis_lib.RedisError as exc:
            logger.warning("rate_limit_unavailable_failing_open", error=str(exc))
            return await call_next(request)

        if count > limit:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")

        return await call_next(request)
