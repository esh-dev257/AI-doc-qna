"""Sliding-window rate limiter backed by Redis (optional)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from app.config import get_settings


class InMemoryLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: int = 60) -> bool:
        now = time.time()
        bucket = self._buckets[key]
        while bucket and bucket[0] < now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_memory = InMemoryLimiter()
_redis = None


def _get_redis():
    global _redis
    settings = get_settings()
    if not settings.redis_enabled:
        return None
    if _redis is not None:
        return _redis
    try:
        import redis

        _redis = redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
    except Exception:
        _redis = None
    return _redis


def check_rate_limit(key: str, limit: int | None = None, window: int = 60) -> bool:
    settings = get_settings()
    if limit is None:
        limit = settings.rate_limit_per_minute
    r = _get_redis()
    if r is None:
        return _memory.allow(key, limit, window)
    try:
        bucket_key = f"rl:{key}:{int(time.time() // window)}"
        count = r.incr(bucket_key)
        if count == 1:
            r.expire(bucket_key, window)
        return int(count) <= limit
    except Exception:
        return _memory.allow(key, limit, window)


def reset() -> None:
    _memory._buckets.clear()
