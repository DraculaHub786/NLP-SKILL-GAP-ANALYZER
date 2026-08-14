"""Tests for the fail-soft Redis session cache."""
import fakeredis
import pytest

import app.utils.redis_cache as redis_cache


@pytest.fixture()
def fake_redis(monkeypatch):
    # decode_responses=True matches the production client in config.py, so
    # values come back as str, not bytes.
    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server, decode_responses=True)
    monkeypatch.setattr(redis_cache, "get_redis", lambda: client)
    redis_cache._last_warned_at = 0.0
    return client


def test_cache_and_get_roundtrip(fake_redis):
    sid = redis_cache.cache_report_json('{"match_score": 42.0}', session_id="abc-123")
    assert sid == "abc-123"
    assert redis_cache.get_report_json("abc-123") == '{"match_score": 42.0}'


def test_cache_generates_id_when_none(fake_redis):
    sid = redis_cache.cache_report_json('{"a": 1}')
    assert sid and len(sid) > 10
    assert redis_cache.get_report_json(sid) == '{"a": 1}'


def test_empty_session_id_auto_generates(fake_redis):
    """An empty session id means 'generate one for me' — by design."""
    sid = redis_cache.cache_report_json('{"a": 1}', session_id="")
    assert sid and len(sid) > 10
    assert redis_cache.get_report_json(sid) == '{"a": 1}'


def test_delete_removes_entry(fake_redis):
    redis_cache.cache_report_json('{"a": 1}', session_id="del-me")
    assert redis_cache.delete_session("del-me") is True
    assert redis_cache.get_report_json("del-me") is None


def test_delete_unknown_returns_false(fake_redis):
    assert redis_cache.delete_session("does-not-exist") is False


def test_invalid_session_ids_rejected(fake_redis):
    for bad in ("../etc/passwd", "has space", "x" * 65):
        assert redis_cache.get_report_json(bad) is None
        assert redis_cache.delete_session(bad) is False
        with pytest.raises(ValueError):
            redis_cache.cache_report_json('{"a": 1}', session_id=bad)


def test_redis_down_fails_open(monkeypatch):
    """When Redis is unreachable (any error), the cache degrades (returns
    None/False) rather than crashing — the API still returns the report."""
    redis_cache._last_warned_at = 0.0

    def broken_redis():
        raise ConnectionError("redis down")

    monkeypatch.setattr(redis_cache, "get_redis", broken_redis)
    assert redis_cache.cache_report_json('{"a": 1}') is None
    assert redis_cache.get_report_json("any-id") is None
    assert redis_cache.delete_session("any-id") is False
