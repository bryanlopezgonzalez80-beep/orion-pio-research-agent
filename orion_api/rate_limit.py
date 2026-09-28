from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable, Mapping
from enum import Enum
from threading import Lock


class CredentialSlot(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class RateLimitCategory(str, Enum):
    READ = "read"
    WRITE = "write"
    SEARCH = "search"


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


class InMemoryRateLimiter:
    """Thread-safe per-process sliding-window limiter with six fixed identities."""

    WINDOW_SECONDS = 60.0
    MAX_BUCKETS = len(CredentialSlot) * len(RateLimitCategory)

    def __init__(
        self,
        limits: Mapping[RateLimitCategory, int],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = dict(limits)
        self._clock = clock
        self._lock = Lock()
        self._buckets: dict[
            tuple[CredentialSlot, RateLimitCategory], deque[float]
        ] = {}

    @property
    def bucket_count(self) -> int:
        with self._lock:
            return len(self._buckets)

    def consume(
        self, credential: CredentialSlot, category: RateLimitCategory
    ) -> None:
        if not isinstance(credential, CredentialSlot) or not isinstance(
            category, RateLimitCategory
        ):
            raise ValueError("Unknown authenticated rate-limit bucket")

        now = self._clock()
        cutoff = now - self.WINDOW_SECONDS
        key = (credential, category)
        with self._lock:
            for existing_key, timestamps in tuple(self._buckets.items()):
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if not timestamps and existing_key != key:
                    del self._buckets[existing_key]

            timestamps = self._buckets.setdefault(key, deque())
            limit = self._limits[category]
            if len(timestamps) >= limit:
                retry_after = max(
                    1,
                    math.ceil(timestamps[0] + self.WINDOW_SECONDS - now),
                )
                raise RateLimitExceeded(retry_after)
            timestamps.append(now)
