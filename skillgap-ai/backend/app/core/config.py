"""Central settings object (pydantic-settings) — one source of truth.

Every module that needs configuration imports `settings` from here. In tests,
`settings` may be swapped via `override_settings(context)` for a false value of
`rate_limit_enabled` (slow tests) without touching env vars.
"""
from contextlib import contextmanager
from functools import lru_cache

import redis as redis_lib
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 172800  # 48 hours

    # CORS
    allowed_origins: list[str] = ["http://localhost:5173"]

    # NLP
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    skill_match_threshold: float = 0.78

    # Rate limiting (per-IP, per-endpoint group)
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 20

    # Load the spaCy pipeline lazily (first request) so tests and the API
    # can boot without the model downloaded; NER runs best-effort.
    spacy_model: str = "en_core_web_sm"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


@lru_cache(maxsize=1)
def _redis_client() -> redis_lib.Redis:
    return redis_lib.from_url(settings.redis_url, decode_responses=True, socket_timeout=3)


def get_redis() -> redis_lib.Redis:
    """Returns a shared Redis client. Raises redis.ConnectionError on failure."""
    return _redis_client()


@contextmanager
def override_settings(**kwargs):
    """Temporarily patch settings (e.g. rate_limit_enabled=False in tests)."""
    previous = {k: getattr(settings, k) for k in kwargs}
    for k, v in kwargs.items():
        setattr(settings, k, v)
    try:
        yield
    finally:
        for k, v in previous.items():
            setattr(settings, k, v)
