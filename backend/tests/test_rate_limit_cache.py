import time

from app.services import cache, rate_limit


def test_in_memory_limiter_allows_then_blocks():
    lim = rate_limit.InMemoryLimiter()
    assert lim.allow("k", limit=2) is True
    assert lim.allow("k", limit=2) is True
    assert lim.allow("k", limit=2) is False


def test_in_memory_limiter_window_expiry():
    lim = rate_limit.InMemoryLimiter()
    assert lim.allow("k", limit=1, window=1) is True
    assert lim.allow("k", limit=1, window=1) is False
    time.sleep(1.05)
    assert lim.allow("k", limit=1, window=1) is True


def test_check_rate_limit_fallbacks_to_memory():
    rate_limit.reset()
    for _ in range(5):
        assert rate_limit.check_rate_limit("ip:test", limit=5, window=60)
    assert rate_limit.check_rate_limit("ip:test", limit=5, window=60) is False


def test_cache_set_and_get_and_expiry():
    cache.clear()
    cache.set("k", {"a": 1}, ttl=60)
    assert cache.get("k") == {"a": 1}
    cache.set("k2", "v", ttl=1)
    time.sleep(1.1)
    assert cache.get("k2") is None
    assert cache.get("missing") is None
