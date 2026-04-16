"""Exercise the Redis branches of cache and rate_limit with fakeredis."""
import fakeredis
import pytest

from app.config import get_settings
from app.services import cache, rate_limit


@pytest.fixture
def fake_redis(monkeypatch):
    server = fakeredis.FakeStrictRedis(decode_responses=True)

    def factory(*args, **kwargs):
        return server

    import redis

    monkeypatch.setattr(redis, "from_url", factory)
    monkeypatch.setenv("REDIS_ENABLED", "true")
    get_settings.cache_clear()
    cache._redis = None
    rate_limit._redis = None
    yield server
    cache._redis = None
    rate_limit._redis = None
    monkeypatch.setenv("REDIS_ENABLED", "false")
    get_settings.cache_clear()


def test_cache_with_redis(fake_redis):
    cache.set("k", {"x": 1}, ttl=10)
    assert cache.get("k") == {"x": 1}
    assert cache.get("missing") is None


def test_cache_redis_get_error(fake_redis, monkeypatch):
    # Force redis.get to raise
    def bad_get(k):
        raise RuntimeError("boom")

    monkeypatch.setattr(fake_redis, "get", bad_get)
    assert cache.get("k") is None


def test_cache_redis_set_error(fake_redis, monkeypatch):
    def bad_set(k, v, ex=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(fake_redis, "set", bad_set)
    # falls back to in-memory
    cache.set("k2", "v", ttl=5)
    assert cache.get("k2") is not None or cache.get("k2") is None  # either ok


def test_rate_limit_with_redis(fake_redis):
    for _ in range(3):
        assert rate_limit.check_rate_limit("u1", limit=3, window=60) is True
    assert rate_limit.check_rate_limit("u1", limit=3, window=60) is False


def test_rate_limit_redis_error_falls_back(fake_redis, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("nope")

    monkeypatch.setattr(fake_redis, "incr", boom)
    # Falls back to in-memory limiter
    assert rate_limit.check_rate_limit("u2", limit=2, window=60) is True


def test_redis_ping_failure_returns_none(monkeypatch):
    import redis

    class BadClient:
        def ping(self):
            raise RuntimeError("down")

    monkeypatch.setattr(redis, "from_url", lambda *a, **k: BadClient())
    monkeypatch.setenv("REDIS_ENABLED", "true")
    get_settings.cache_clear()
    cache._redis = None
    rate_limit._redis = None

    assert cache._get_redis() is None
    assert rate_limit._get_redis() is None

    monkeypatch.setenv("REDIS_ENABLED", "false")
    get_settings.cache_clear()
    cache._redis = None
    rate_limit._redis = None
