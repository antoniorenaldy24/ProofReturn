"""Bounded In-Memory Cache with TTL Expiration and LRU Eviction (API-06, Section 28, AUD-39)."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class BoundedTTLCache(Generic[T]):
    """Thread-safe bounded in-memory cache with TTL and LRU eviction preventing memory leaks (AUD-39)."""

    def __init__(self, max_size: int = 10000, ttl_seconds: float = 86400.0) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str, default: T | None = None) -> T | None:
        with self._lock:
            if key not in self._cache:
                return default
            inserted_at, val = self._cache[key]
            if time.time() - inserted_at > self.ttl_seconds:
                del self._cache[key]
                return default
            # Mark as recently used
            self._cache.move_to_end(key)
            return val

    def set(self, key: str, value: T) -> None:
        with self._lock:
            now = time.time()
            if key in self._cache:
                self._cache[key] = (now, value)
                self._cache.move_to_end(key)
                return

            # Cleanup expired or evict LRU if at capacity
            self._purge_expired_locked(now)
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (now, value)

    def add(self, key: str) -> None:
        """Add a key to the cache (convenience for set-like usage)."""
        self.set(key, True)  # type: ignore[arg-type]

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __getitem__(self, key: str) -> T:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: T) -> None:
        self.set(key, value)

    def pop(self, key: str, default: T | None = None) -> T | None:
        with self._lock:
            if key not in self._cache:
                return default
            _, val = self._cache.pop(key)
            return val

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            now = time.time()
            self._purge_expired_locked(now)
            return len(self._cache)

    def _purge_expired_locked(self, now: float) -> None:
        expired_keys = [k for k, (t, _) in self._cache.items() if now - t > self.ttl_seconds]
        for k in expired_keys:
            del self._cache[k]
