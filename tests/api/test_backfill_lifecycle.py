from __future__ import annotations

from threading import Lock
import time

from fastapi import BackgroundTasks, HTTPException
import pytest

from orion_api.routes import radar


@pytest.fixture
def backfill_state(monkeypatch):
    settings = {}
    snapshots = []
    monkeypatch.setattr(radar, "get_setting", lambda key: settings.get(key))

    def save(key, value):
        settings[key] = value
        snapshots.append(dict(value))

    monkeypatch.setattr(radar, "set_setting", save)
    monkeypatch.setattr(radar, "harvest_status", lambda: {"coverage_query_count": 251})
    monkeypatch.setattr(radar, "_BACKFILL_LOCK", Lock())
    monkeypatch.setattr(radar, "_STATUS_CACHE_LOCK", Lock())
    monkeypatch.setattr(radar, "_STATUS_CACHE", None)
    monkeypatch.setattr(radar, "_STATUS_CACHE_AT", 0.0)
    return settings, snapshots


@pytest.mark.parametrize("path", ["fresh", "cached", "contended"])
def test_status_recovers_abandoned_backfill_in_every_cache_path(backfill_state, monkeypatch, path):
    settings, _ = backfill_state
    settings[radar._BACKFILL_STATUS_KEY] = {"state": "running", "instance_id": "old-instance"}
    if path != "fresh":
        monkeypatch.setattr(radar, "_STATUS_CACHE", {"coverage_query_count": 251})
        monkeypatch.setattr(radar, "_STATUS_CACHE_AT", time.monotonic() if path == "cached" else 0.0)
    if path == "contended":
        radar._STATUS_CACHE_LOCK.acquire()
    try:
        assert radar.radar_status()["manual_backfill"]["state"] == "interrupted_retryable"
        assert settings[radar._BACKFILL_STATUS_KEY]["state"] == "interrupted_retryable"
    finally:
        if path == "contended":
            radar._STATUS_CACHE_LOCK.release()


def test_same_instance_active_job_is_not_falsely_interrupted(backfill_state):
    settings, _ = backfill_state
    settings[radar._BACKFILL_STATUS_KEY] = {"state": "running", "instance_id": radar._INSTANCE_ID}
    assert radar.radar_status()["manual_backfill"]["state"] == "running"


@pytest.mark.parametrize("value", ["24", "invalid", 0, 1, 25, 24.0, None, True])
def test_invalid_month_selection_never_acquires_or_poisons_the_lock(backfill_state, value):
    settings, _ = backfill_state
    tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as error:
        radar.refresh_backfill(tasks, {"months_per_run": value})
    assert error.value.status_code == 422
    assert not radar._BACKFILL_LOCK.locked()
    assert not tasks.tasks
    assert not settings


@pytest.mark.parametrize("months", [24, 48, 96, 120])
def test_selection_reaches_the_background_job_and_duplicates_join(backfill_state, months):
    tasks = BackgroundTasks()
    result = radar.refresh_backfill(tasks, {"months_per_run": months})
    try:
        assert result["months_per_run"] == months
        assert tasks.tasks[0].args == (months,)
        assert radar.refresh_backfill(tasks, {"months_per_run": months})["status"] == "already_running"
        assert len(tasks.tasks) == 1
    finally:
        radar._BACKFILL_LOCK.release()


def test_default_selection_is_two_years(backfill_state):
    tasks = BackgroundTasks()
    try:
        assert radar.refresh_backfill(tasks)["months_per_run"] == 24
    finally:
        radar._BACKFILL_LOCK.release()


def test_progress_uses_run_total_and_cumulative_records_across_months(backfill_state, monkeypatch):
    settings, snapshots = backfill_state
    monkeypatch.setattr(radar, "BACKFILL_FLOOR_YEAR", 1940)

    def fake_run(*, months_per_run, progress_callback):
        assert months_per_run == 24
        progress_callback({"backfill_month": "2025-12-01", "backfill_tasks_total": 2,
                           "backfill_tasks_completed_total": 2, "backfill_records_received": 10})
        progress_callback({"backfill_month": "2025-11-01", "backfill_tasks_total": 2,
                           "backfill_tasks_completed_total": 3, "backfill_records_received": 5})
        return {"next_cursor": "2025-12-01", "months_processed": 2, "received": 15, "errors": ["retry"]}

    monkeypatch.setattr(radar, "run_historical_backfill", fake_run)
    radar._BACKFILL_LOCK.acquire()
    radar._run_manual_backfill(24)
    progress = [item for item in snapshots if item.get("updated_at")]
    assert progress[0]["tasks_total"] == progress[1]["tasks_total"] == 48
    assert progress[1]["tasks_completed"] == 3
    assert progress[1]["records_received"] == 15
    final = settings[radar._BACKFILL_STATUS_KEY]
    assert final["tasks_scope"] == "run"
    assert final["tasks_completed"] == 3
    assert final["state"] == "completed_with_warnings"
    assert not radar._BACKFILL_LOCK.locked()


def test_progress_plan_stops_at_historical_floor(backfill_state, monkeypatch):
    settings, _ = backfill_state
    monkeypatch.setattr(radar, "BACKFILL_FLOOR_YEAR", 1940)

    def fake_run(*, months_per_run, progress_callback):
        progress_callback({"backfill_month": "1940-01-01", "backfill_tasks_total": 4,
                           "backfill_tasks_completed_total": 4, "backfill_records_received": 5})
        return {"next_cursor": "1940-01-01", "months_processed": 1, "received": 5, "errors": []}

    monkeypatch.setattr(radar, "run_historical_backfill", fake_run)
    radar._run_manual_backfill(24)
    assert settings[radar._BACKFILL_STATUS_KEY]["tasks_total"] == 4
    assert settings[radar._BACKFILL_STATUS_KEY]["tasks_completed"] == 4


def test_worker_failure_preserves_progress_and_releases_lock(backfill_state, monkeypatch):
    settings, _ = backfill_state

    def fail(**kwargs):
        raise RuntimeError("private diagnostic")

    monkeypatch.setattr(radar, "run_historical_backfill", fail)
    radar._BACKFILL_LOCK.acquire()
    radar._run_manual_backfill(24)
    final = settings[radar._BACKFILL_STATUS_KEY]
    assert final["state"] == "failed"
    assert final["months_per_run"] == 24
    assert "private diagnostic" not in str(final)
    assert not radar._BACKFILL_LOCK.locked()
