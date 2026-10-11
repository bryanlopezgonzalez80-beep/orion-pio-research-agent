import copy
import pytest
from harvest_retry_queue import QueryRetryQueue, KEY


def setup_queue():
    store = {}
    now = [1000]
    def reopen():
        return QueryRetryQueue(["a", "b", "c"], lambda key, default: copy.deepcopy(store.get(key, default)),
                               lambda key, value: store.__setitem__(key, copy.deepcopy(value)), lambda: now[0])
    return store, now, reopen


def test_interruption_survives_reopen_and_waits_before_retry():
    store, now, reopen = setup_queue()
    queue = reopen()
    queue.begin("a")
    # Simulated process exit before results were committed.
    queue = reopen()
    assert queue.ordered(["a", "b", "c"]) == ["b", "c"]
    assert queue.summary() == {"retry_queue_pending": 1, "retry_queue_deferred": 1}
    now[0] += 300
    assert queue.ordered(["b", "c", "a"]) == ["a", "b", "c"]
    queue.begin("a")
    assert store[KEY]["a"]["attempts"] == 2
    assert store[KEY]["a"]["retry_at"] == now[0] + 600
    queue.complete("a")
    assert reopen().summary()["retry_queue_pending"] == 0


def test_backoff_is_bounded_and_persists_no_provider_error_or_secret():
    store, now, reopen = setup_queue()
    queue = reopen()
    for _ in range(30):
        queue.begin("a")
        now[0] = store[KEY]["a"]["retry_at"]
    assert store[KEY]["a"]["attempts"] == 20
    queue.begin("a")
    assert store[KEY]["a"]["retry_at"] - now[0] == 86400
    assert set(store[KEY]["a"]) == {"attempts", "retry_at"}


def test_corrupt_queue_fails_closed_and_removed_taxonomy_entries_are_ignored():
    for value in ([], {"a": {}}, {"a": {"attempts": 1, "retry_at": float("nan")}}):
        with pytest.raises(ValueError):
            QueryRetryQueue(["a"], lambda *args: value, lambda *args: None)
    queue = QueryRetryQueue(["a"], lambda *args: {"old": {}}, lambda *args: None)
    assert queue.ordered(["a"]) == ["a"]
