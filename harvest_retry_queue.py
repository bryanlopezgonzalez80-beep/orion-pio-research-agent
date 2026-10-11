"""Durable query retry state; used inside Orion's existing single-writer lease.

Uses the existing settings store, not a new service or schema. A task is recorded
before its request and removed only after its records are persisted. Interrupted
requests are therefore retried at least once; existing paper upserts deduplicate.
"""
from __future__ import annotations

import time

KEY = "deep_harvest.query_retries"


class QueryRetryQueue:
    def __init__(self, queries, read, write, clock=None):
        self.clock, self.write = clock or time.time, write
        allowed = set(queries)
        raw = read(KEY, {})
        if not isinstance(raw, dict):
            raise ValueError("Invalid harvest retry state")
        self.entries = {}
        for query, value in raw.items():
            if query not in allowed:
                continue
            if (not isinstance(value, dict)
                    or not isinstance(value.get("attempts"), int)
                    or not 1 <= value["attempts"] <= 20
                    or not isinstance(value.get("retry_at"), (int, float))
                    or not 0 <= value["retry_at"] < 10**12):
                raise ValueError("Invalid harvest retry entry")
            self.entries[query] = {"attempts": value["attempts"], "retry_at": value["retry_at"]}

    def ordered(self, regular):
        now = self.clock()
        ready = [q for q in regular if q in self.entries and self.entries[q]["retry_at"] <= now]
        return ready + [q for q in regular if q not in self.entries]

    def begin(self, query):
        attempts = min(20, self.entries.get(query, {}).get("attempts", 0) + 1)
        delay = min(86400, 300 * 2 ** min(attempts - 1, 9))
        self.entries[query] = {"attempts": attempts, "retry_at": self.clock() + delay}
        self._save()

    def complete(self, query):
        self.entries.pop(query, None)
        self._save()

    def summary(self):
        return {"retry_queue_pending": len(self.entries),
                "retry_queue_deferred": sum(v["retry_at"] > self.clock() for v in self.entries.values())}

    def _save(self):
        self.write(KEY, {key: dict(value) for key, value in self.entries.items()})
