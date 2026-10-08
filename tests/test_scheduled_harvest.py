from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import daily_agent
import deep_harvest
from orion_api.routes import radar
from scripts import scheduled_harvest as runner

pytestmark = pytest.mark.integration


@pytest.fixture
def cloud(monkeypatch):
    settings = {}
    monkeypatch.setattr(runner, "require_persistent_database", lambda: None)
    for module in (runner, radar):
        monkeypatch.setattr(module, "get_setting", lambda key, default=None: settings.get(key, default))
        monkeypatch.setattr(module, "set_setting", lambda key, value: settings.__setitem__(key, value))
    @contextmanager
    def owned(*args):
        yield True
    monkeypatch.setattr(runner, "harvest_lock", owned)
    return settings


def test_cloud_requires_postgres_before_touching_data(monkeypatch):
    monkeypatch.setattr(runner, "get_database_config", lambda: SimpleNamespace(engine="sqlite"))
    monkeypatch.setattr(runner, "connect_database", lambda *args: pytest.fail("SQLite connected"))
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        runner.require_persistent_database()


@pytest.mark.parametrize("value,healthy", [(1, True), (0, False)])
def test_database_health_probe_closes_connection(monkeypatch, value, healthy):
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (value,)
    monkeypatch.setattr(runner, "get_database_config", lambda: SimpleNamespace(engine="postgres"))
    monkeypatch.setattr(runner, "connect_database", lambda config: connection)
    if healthy:
        runner.require_persistent_database()
        connection.commit.assert_called_once()
    else:
        with pytest.raises(RuntimeError):
            runner.require_persistent_database()
    connection.close.assert_called_once()


@pytest.mark.parametrize("job,action,scheduled", [("unknown", "preserve", False), ("verify", "unknown", False), ("verify", "resume", True)])
def test_invalid_jobs_and_schedule_mutations_fail_before_database(monkeypatch, job, action, scheduled):
    monkeypatch.setattr(runner, "require_persistent_database", lambda: pytest.fail("database touched"))
    with pytest.raises(ValueError):
        runner.execute(job, historical_action=action, scheduled=scheduled)


def test_verify_checks_database_without_starting_harvest(cloud, monkeypatch):
    monkeypatch.setattr(runner, "run_cloud_deep", lambda: pytest.fail("harvest started"))
    assert runner.execute("verify") == {"state": "healthy", "database": "postgres"}
    assert not cloud


@pytest.mark.parametrize("enabled", [None, False, "false", "true"])
def test_historical_schedule_remains_paused_until_explicit_resume(cloud, monkeypatch, enabled):
    if enabled is not None:
        cloud[runner.BACKFILL_ENABLED_KEY] = enabled
    monkeypatch.setattr(radar, "_run_manual_backfill", lambda *args: pytest.fail("paused job started"))
    assert runner.execute("backfill", scheduled=True)["state"] == "paused"


def test_pause_is_persistent_and_does_not_run_backfill(cloud, monkeypatch):
    monkeypatch.setattr(radar, "_run_manual_backfill", lambda *args: pytest.fail("paused job started"))
    assert runner.execute("backfill", historical_action="pause")["state"] == "paused"
    assert cloud[runner.BACKFILL_ENABLED_KEY] is False


def test_resume_uses_two_years_and_preserves_partial_progress(cloud, monkeypatch):
    calls = []
    def run(months):
        calls.append(months)
        cloud[radar._BACKFILL_STATUS_KEY] = {"state": "partial_retryable", "months_per_run": months, "records_received": 83}
    monkeypatch.setattr(radar, "_run_manual_backfill", run)
    monkeypatch.delenv("ORION_BACKFILL_RUNTIME_SECONDS", raising=False)
    result = runner.execute("backfill", historical_action="resume")
    assert cloud[runner.BACKFILL_ENABLED_KEY] is True
    assert calls == [24]
    assert result["state"] == "partial_retryable"
    assert result["records_received"] == 83
    assert runner.os.environ["ORION_BACKFILL_RUNTIME_SECONDS"] == "3000"
    assert runner.execute("backfill", scheduled=True)["state"] == "partial_retryable"
    assert calls == [24, 24]


def test_busy_backfill_returns_retryable_without_copying_other_job(cloud, monkeypatch):
    monkeypatch.setattr(radar, "_run_manual_backfill", lambda *args: {"state": "blocked_retryable"})
    assert runner.execute("backfill") == {"state": "blocked_retryable"}


def test_busy_deep_returns_retryable_without_claiming_success(cloud, monkeypatch):
    monkeypatch.setattr(runner, "run_cloud_deep", lambda: {"state": "blocked_retryable"})
    assert runner.execute("deep") == {"state": "blocked_retryable"}


@pytest.mark.parametrize("partial,warnings,expected", [(False, False, "completed"), (False, True, "completed_with_warnings"), (True, False, "partial_retryable")])
def test_deep_has_no_historical_work_and_reports_truthful_state(cloud, monkeypatch, partial, warnings, expected):
    def sweep(*, include_backfill, progress_callback):
        assert include_backfill is False
        progress_callback({"queries_processed": 1, "queries_total": 2, "received": 7})
        assert cloud[runner.LIVE_STATUS_KEY]["state"] == "running"
        return {"status": "PARTIAL_RETRYABLE" if partial else "COMPLETED", "live": {"queries_processed": 1 if partial else 2, "queries_total": 2, "errors": ["provider"] if warnings else []}, "records_received_this_run": 13}
    monkeypatch.setattr(runner, "run_deep_harvest", sweep)
    monkeypatch.setattr(runner, "run_cloud_deep", runner.run_cloud_deep.__wrapped__)
    result = runner.execute("deep")
    assert result["state"] == expected
    assert result["records_received"] == 13
    assert cloud[runner.LIVE_STATUS_KEY]["executor"] == "github_actions"


def test_deep_failure_keeps_safe_error_type_and_progress(cloud, monkeypatch):
    def sweep(**kwargs):
        kwargs["progress_callback"]({"queries_processed": 1, "queries_total": 2})
        raise RuntimeError("sensitive-connection-details")
    monkeypatch.setattr(runner, "run_deep_harvest", sweep)
    with pytest.raises(RuntimeError):
        runner.run_cloud_deep.__wrapped__()
    state = cloud[runner.LIVE_STATUS_KEY]
    assert state["state"] == "failed"
    assert state["queries_processed"] == 1
    assert state["error"] == "RuntimeError"
    assert "sensitive" not in json.dumps(state)


@pytest.mark.parametrize("warnings", [[], ["provider"]])
def test_daily_does_not_launch_deep_or_history(cloud, monkeypatch, warnings):
    calls = []
    def daily(**kwargs):
        calls.append(kwargs)
        return {"errors": warnings, "results_seen": 15}
    monkeypatch.setattr(daily_agent, "main", daily)
    result = runner.execute("daily")
    assert calls == [{"core_only": True, "include_backfill": False}]
    assert result["state"] == ("completed_with_warnings" if warnings else "completed")
    assert result["records_received"] == 15


def test_busy_daily_does_not_execute(cloud, monkeypatch):
    @contextmanager
    def busy(*args):
        yield False
    monkeypatch.setattr(runner, "harvest_lock", busy)
    monkeypatch.setattr(daily_agent, "main", lambda **kwargs: pytest.fail("duplicate daily"))
    assert runner.execute("daily") == {"state": "blocked_retryable"}


def test_core_daily_persists_each_query_and_continues_provider_failures(monkeypatch, sample_paper):
    saved = []
    def search(query):
        if query == "bad":
            raise RuntimeError("provider")
        return {"results": [sample_paper], "received": 1, "errors": []}
    monkeypatch.setattr(daily_agent, "CORE_TOPICS", ["first", "bad", "last"])
    monkeypatch.setattr(daily_agent, "_run", search)
    monkeypatch.setattr(daily_agent, "upsert_papers", lambda values: saved.extend(values))
    result = daily_agent.core_daily_sweep()
    assert len(saved) == 2
    assert result["live"]["queries_processed"] == 3
    assert result["live"]["errors"] == ["bad: RuntimeError"]
    assert result["backfill"] is None


def test_cli_writes_safe_failure_summary(tmp_path, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise RuntimeError("secret-not-for-output")
    monkeypatch.setattr(runner, "execute", fail)
    output = tmp_path / "summary.json"
    assert runner.main(["--job", "verify", "--output", str(output)]) == 1
    payload = json.loads(output.read_text())
    assert payload["error_type"] == "RuntimeError"
    assert "secret" not in output.read_text() + capsys.readouterr().out


def test_cli_success_exit_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "execute", lambda *args, **kwargs: {"state": "healthy"})
    output = tmp_path / "nested" / "summary.json"
    assert runner.main(["--job", "verify", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["state"] == "healthy"


def test_api_does_not_mark_an_active_cloud_runner_interrupted(cloud, monkeypatch):
    cloud[radar._MANUAL_STATUS_KEY] = {"state": "running", "instance_id": "cloud-worker"}
    cloud[radar._BACKFILL_STATUS_KEY] = {"state": "running", "instance_id": "cloud-worker"}
    monkeypatch.setattr(radar, "active_harvest", lambda *args: True)
    assert radar._manual_refresh_status()["state"] == "running"
    assert radar._backfill_status()["state"] == "running"


def test_historical_time_budget_preserves_cursor_and_resumes_checkpoint(monkeypatch, sample_paper):
    settings = {"deep_harvest.backfill_cursor": "2026-09-01"}
    checkpoints = {}
    saved, calls = [], []
    monkeypatch.setattr(deep_harvest, "get_setting", lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(deep_harvest, "set_setting", lambda key, value: settings.__setitem__(key, value))
    monkeypatch.setattr(deep_harvest, "BACKFILL_QUERIES", ["first", "second"])
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", [])
    monkeypatch.setattr(deep_harvest, "get_checkpoint", lambda *key: checkpoints.get(key))
    monkeypatch.setattr(deep_harvest, "set_checkpoint", lambda *args, **kwargs: checkpoints.__setitem__(args[:4], {"status": args[4]}))
    monkeypatch.setattr(deep_harvest, "checkpoint_summary", lambda: [])
    monkeypatch.setattr(deep_harvest, "upsert_papers", lambda values: saved.extend(values))
    def fetch(query, *args, **kwargs):
        calls.append(query)
        return [dict(sample_paper, id=query, doi="", title=query)]
    monkeypatch.setattr(deep_harvest, "search_crossref_window", fetch)
    ticks = iter([0, 0, 2])
    monkeypatch.setattr(deep_harvest.time, "monotonic", lambda: next(ticks))
    result = deep_harvest.run_historical_backfill(months_per_run=1, max_runtime_seconds=1)
    assert result["partial"] and result["stopped_for_budget"]
    assert result["next_cursor"] == "2026-09-01"
    assert calls == ["first"]
    monkeypatch.setattr(deep_harvest.time, "monotonic", lambda: 0)
    result = deep_harvest.run_historical_backfill(months_per_run=1, max_runtime_seconds=1)
    assert not result["partial"]
    assert calls == ["first", "second"]
    assert len(saved) == 2
    assert result["next_cursor"] == "2026-08-01"


def test_workflows_share_writer_group_and_separate_daily_from_deep():
    daily = Path(".github/workflows/daily-radar.yml").read_text()
    cloud = Path(".github/workflows/cloud-harvest.yml").read_text()
    assert 'cron: "0 10 * * *"' in daily
    assert 'cron: "0 11 * * *"' in cloud
    assert 'cron: "23 2,8,14,20 * * *"' in cloud
    for text in (daily, cloud):
        assert "group: orion-harvest-writers" in text
        assert "cancel-in-progress: false" in text
        assert "workflow_dispatch:" in text
    assert "--job daily" in daily
