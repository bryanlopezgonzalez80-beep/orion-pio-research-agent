import copy
import pytest
import deep_harvest
import harvest_retry_queue


@pytest.mark.parametrize("raises", [False, True])
def test_failed_query_waits_survives_restart_and_clears_only_after_persistence(monkeypatch, raises):
    store, calls, saved = {}, [], []
    now = [1000]
    monkeypatch.setattr(harvest_retry_queue.time, "time", lambda: now[0])
    monkeypatch.setattr(deep_harvest.time, "monotonic", lambda: 0)
    monkeypatch.setattr(deep_harvest, "coverage_queries", lambda: ["burnout"])
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", [])
    monkeypatch.setattr(deep_harvest, "get_setting", lambda key, default=None: copy.deepcopy(store.get(key, default)))
    monkeypatch.setattr(deep_harvest, "set_setting", lambda key, value: store.__setitem__(key, copy.deepcopy(value)))
    monkeypatch.setattr(deep_harvest, "upsert_papers", lambda papers: saved.extend(papers))

    def search(query, **kwargs):
        calls.append(query)
        if len(calls) == 1 and raises:
            raise RuntimeError("provider unavailable")
        return {"received": 1, "results": [{"id": "a", "title": "A"}],
                "errors": ["provider unavailable"] if len(calls) == 1 else [], "source_meta": []}

    monkeypatch.setattr(deep_harvest, "execute_academic_search", search)
    first = deep_harvest.run_live_sweep()
    assert first["retry_queue_pending"] == 1
    second = deep_harvest.run_live_sweep()
    assert calls == ["burnout"]
    assert second["queries_processed"] == 0
    assert second["retry_queue_deferred"] == 1
    now[0] += 301
    third = deep_harvest.run_live_sweep()
    assert calls == ["burnout", "burnout"]
    assert third["retry_queue_pending"] == 0
    assert saved[-1]["id"] == "a"
