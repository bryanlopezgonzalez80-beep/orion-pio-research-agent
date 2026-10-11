from types import SimpleNamespace
import pytest
import data_store
import corpus_cache as cache_module
from orion_api.library_cursor import encode_cursor, decode_cursor


def test_cursor_walk_keeps_equal_rank_and_missing_dates(sample_paper):
    data_store.upsert_papers([{**sample_paper, "id": str(i), "title": f"Paper {i}", "doi": "", "published_date": ""} for i in range(9)])
    first = data_store.list_library_cursor(4)
    # A newly inserted record before the cursor must not shift later pages.
    data_store.upsert_papers([{**sample_paper, "id": "z", "title": "New", "doi": ""}])
    second = data_store.list_library_cursor(4, first[-1]["id"])
    third = data_store.list_library_cursor(4, second[-1]["id"])
    ids = [p["id"] for p in first + second + third]
    assert ids == list(reversed([str(i) for i in range(9)]))
    assert decode_cursor(encode_cursor(first[-1]["id"])) == first[-1]["id"]


def test_invalid_cursor_is_rejected():
    from fastapi import HTTPException
    for value in ("garbage!", "W10", "bnVsbA", "e30"):
        with pytest.raises(HTTPException):
            decode_cursor(value)


def test_stats_cache_expires_isolates_database_and_copies(monkeypatch):
    now = [0]
    config = SimpleNamespace(engine="postgres", database_url="db-A")
    monkeypatch.setattr(cache_module, "get_database_config", lambda: config)
    monkeypatch.setattr(cache_module, "monotonic", lambda: now[0])
    calls = []
    @cache_module.corpus_cache(ttl=120)
    def read():
        calls.append(1)
        return {"total": len(calls)}
    read()["total"] = 999
    assert read() == {"total": 1}
    now[0] = 121
    assert read() == {"total": 2}
    config.database_url = "db-B"
    assert read() == {"total": 3}
