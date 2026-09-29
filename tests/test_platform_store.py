from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

import pytest

import platform_store

pytestmark = pytest.mark.integration


def test_cache_key_is_normalized_and_cache_round_trip(tmp_path):
    path = tmp_path / "cache.db"
    assert platform_store.make_cache_key("OpenAlex", " Leadership ", 30, 5) == platform_store.make_cache_key("OpenAlex", "leadership", 30, 5)
    platform_store.set_cache("OpenAlex", "Leadership", 30, 5, [{"id": "ñ"}], path=path)
    assert platform_store.get_cache("OpenAlex", "leadership", 30, 5, path=path) == [{"id": "ñ"}]


def test_expired_cache_is_ignored_and_purged(tmp_path):
    path = tmp_path / "cache.db"
    platform_store.set_cache("OpenAlex", "old", 30, 5, [], ttl_hours=-1, path=path)
    assert platform_store.get_cache("OpenAlex", "old", 30, 5, path=path) is None
    assert platform_store.purge_expired_cache(path=path) == 1


def test_source_health_opens_and_resets_circuit(tmp_path, monkeypatch):
    path = tmp_path / "health.db"
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(platform_store, "_utcnow", lambda: fixed)
    assert platform_store.source_available("Crossref", path=path)
    for _ in range(3):
        platform_store.record_source_failure("Crossref", "x" * 1500, path=path, threshold=3)
    health = platform_store.get_source_health(path=path)[0]
    assert health["failure_count"] == 3
    assert health["success_count"] == 0
    assert health["consecutive_failures"] == 3
    assert health["last_status"] == "error"
    assert len(health["last_error"]) == 1000
    assert not platform_store.source_available("Crossref", path=path)
    platform_store.record_source_success("Crossref", path=path)
    assert platform_store.source_available("Crossref", path=path)
    recovered = platform_store.get_source_health(path=path)[0]
    assert recovered["failure_count"] == 3
    assert recovered["success_count"] == 1
    assert recovered["consecutive_failures"] == 0
    assert recovered["last_status"] == "ok"
    assert recovered["last_error"] == ""


def test_sqlite_source_health_preserves_existing_history(tmp_path):
    path = tmp_path / "health.db"
    platform_store.record_source_success("OpenAlex", path=path)
    platform_store.record_source_success("OpenAlex", path=path)
    platform_store.record_source_failure("OpenAlex", "temporary", path=path)

    health = platform_store.get_source_health(path=path)[0]
    assert health["success_count"] == 2
    assert health["failure_count"] == 1
    assert health["consecutive_failures"] == 1
    assert health["last_status"] == "error"


def test_sqlite_first_source_failure_creates_health_row(tmp_path):
    path = tmp_path / "health.db"

    platform_store.record_source_failure("Crossref", "first failure", path=path)

    health = platform_store.get_source_health(path=path)[0]
    assert health["source"] == "Crossref"
    assert health["success_count"] == 0
    assert health["failure_count"] == 1
    assert health["consecutive_failures"] == 1


def test_history_collections_and_stats(tmp_path):
    path = tmp_path / "platform.db"
    platform_store.log_search("liderazgo ñ", "academic", ["OpenAlex"], 4, 3, 20, [], path=path)
    history = platform_store.get_search_history(path=path)
    assert history[0]["query"] == "liderazgo ñ"
    cid = platform_store.create_collection(" Favoritos ", " Primera ", path=path)
    assert platform_store.create_collection("Favoritos", "Actualizada", path=path) == cid
    platform_store.add_to_collection(cid, "paper-1", path=path)
    platform_store.add_to_collection(cid, "paper-1", path=path)
    collection = platform_store.get_collections(path=path)[0]
    assert collection["item_count"] == 1
    assert collection["description"] == "Actualizada"
    stats = platform_store.platform_stats(path=path)
    assert stats["searches"] == stats["collections"] == 1


def test_settings_round_trip_json_values(tmp_path):
    path = tmp_path / "settings.db"
    assert platform_store.get_setting("missing", {"default": True}, path=path) == {
        "default": True
    }
    platform_store.set_setting(
        "deep_harvest.cursor",
        {"month": "2026-08-01", "count": 4},
        path=path,
    )
    assert platform_store.get_setting("deep_harvest.cursor", path=path) == {
        "month": "2026-08-01",
        "count": 4,
    }


def test_empty_collection_and_invalid_alert_are_rejected(tmp_path):
    path = tmp_path / "platform.db"
    with pytest.raises(ValueError, match="empty"):
        platform_store.create_collection(" ", path=path)
    with pytest.raises(ValueError, match="cadence"):
        platform_store.create_alert("A", "query", cadence="hourly", path=path)


def test_alert_lifecycle_and_due_calculation(tmp_path, monkeypatch):
    path = tmp_path / "alerts.db"
    now = datetime(2026, 2, 8, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(platform_store, "_utcnow", lambda: now)
    daily = platform_store.create_alert("Daily", "leadership", "academic", ["OpenAlex"], "daily", path=path)
    weekly = platform_store.create_alert("Weekly", "Ley 80", "legal_pr", cadence="weekly", path=path)
    assert {a["id"] for a in platform_store.alerts_due(path=path)} == {daily, weekly}
    platform_store.mark_alert_run(daily, path=path)
    assert {a["id"] for a in platform_store.alerts_due(path=path)} == {weekly}
    with platform_store.connect(path) as con:
        con.execute("UPDATE orion_alerts SET last_run=? WHERE id=?", ((now - timedelta(days=8)).isoformat(), weekly))
        con.execute("UPDATE orion_alerts SET last_run='invalid' WHERE id=?", (daily,))
    assert {a["id"] for a in platform_store.alerts_due(path=path)} == {daily, weekly}
    assert len(platform_store.get_alerts(enabled_only=True, path=path)) == 2


def test_postgres_collection_insert_uses_conflict_clause(monkeypatch):
    statements = []

    class Connection:
        engine = "postgres"

        def execute(self, sql, params):
            statements.append((sql, params))

    @contextmanager
    def fake_connect(path=None):
        yield Connection()

    monkeypatch.setattr(platform_store, "connect", fake_connect)
    platform_store.add_to_collection(3, "paper-1")
    assert "ON CONFLICT(collection_id,paper_id) DO NOTHING" in statements[0][0]


def test_postgres_failure_upsert_qualifies_existing_counter(monkeypatch):
    statements = []

    class Cursor:
        def fetchone(self):
            return {"consecutive_failures": 0}

    class Connection:
        engine = "postgres"

        def execute(self, sql, params):
            statements.append((" ".join(sql.split()), params))
            return Cursor()

    @contextmanager
    def fake_connect(path=None):
        yield Connection()

    monkeypatch.setattr(platform_store, "connect", fake_connect)
    platform_store.record_source_failure("Crossref", "provider down")

    upsert = statements[-1][0]
    assert "failure_count=COALESCE(orion_source_health.failure_count,0)+1" in upsert
    assert "failure_count=failure_count+1" not in upsert


def test_postgres_success_upsert_qualifies_existing_counter(monkeypatch):
    statements = []

    class Connection:
        engine = "postgres"

        def execute(self, sql, params):
            statements.append((" ".join(sql.split()), params))

    @contextmanager
    def fake_connect(path=None):
        yield Connection()

    monkeypatch.setattr(platform_store, "connect", fake_connect)
    platform_store.record_source_success("OpenAlex")

    upsert = statements[-1][0]
    assert "success_count=COALESCE(orion_source_health.success_count,0)+1" in upsert
    assert "success_count=success_count+1" not in upsert
    assert "last_status=excluded.last_status" in upsert
    assert "last_error=excluded.last_error" in upsert
