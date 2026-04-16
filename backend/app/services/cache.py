"""Thin cache helper. Uses Redis when available, otherwise an in-process dict."""
from __future__ import annotations

import json
import time
from typing import Any

from app.config import get_settings

_memory: dict[str, tuple[float, Any]] = {}
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


def get(key: str) -> Any | None:
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            return None
    entry = _memory.get(key)
    if entry is None:
        return None
    expires, value = entry
    if expires and expires < time.time():
        _memory.pop(key, None)
        return None
    return value


def set(key: str, value: Any, ttl: int = 300) -> None:
    r = _get_redis()
    if r is not None:
        try:
            r.set(key, json.dumps(value), ex=ttl)
            return
        except Exception:
            pass
    _memory[key] = (time.time() + ttl if ttl else 0, value)


def clear() -> None:
    _memory.clear()
