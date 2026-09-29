from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from scripts import orion_health_check as monitor

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
FAKE_DATABASE_URL = "postgresql://monitor:test-only@db.example.test/orion"


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeCursor:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeConnection:
    engine = "postgres"

    def __init__(
        self,
        *,
        papers=267,
        searches=42,
        latest_search=None,
        latest_weekly=None,
        latest_paper=None,
        sources=None,
    ):
        self.papers = papers
        self.searches = searches
        self.latest_search = latest_search or (NOW - timedelta(hours=4)).isoformat()
        self.latest_weekly = latest_weekly or (NOW - timedelta(days=3)).isoformat()
        self.latest_paper = latest_paper or (NOW - timedelta(hours=2)).isoformat()
        self.sources = sources if sources is not None else [
            {
                "source": "OpenAlex",
                "last_status": "ok",
                "success_count": 5,
                "failure_count": 0,
                "consecutive_failures": 0,
                "circuit_open_until": None,
                "last_checked": (NOW - timedelta(hours=1)).isoformat(),
            }
        ]
        self.statements = []
        self.rolled_back = False
        self.closed = False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.statements.append((normalized, params))
        if normalized == "SET TRANSACTION READ ONLY":
            return FakeCursor()
        if "COUNT(*)" in normalized and "FROM papers" in normalized:
            return FakeCursor(one={"count": self.papers})
        if "COUNT(*)" in normalized and "FROM orion_search_history" in normalized:
            return FakeCursor(one={"count": self.searches})
        if "COUNT(*)" in normalized and "FROM orion_source_health" in normalized:
            return FakeCursor(one={"count": len(self.sources)})
        if "MAX(created_at)" in normalized:
            return FakeCursor(one={"latest": self.latest_search})
        if "MAX(updated_at)" in normalized:
            return FakeCursor(one={"latest": self.latest_paper})
        if "MAX(run_at)" in normalized:
            return FakeCursor(one={"latest": self.latest_weekly})
        if normalized.startswith("SELECT source,last_status"):
            return FakeCursor(many=self.sources)
        raise AssertionError(f"Unexpected SQL: {normalized}")

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def healthy_api_response():
    return FakeResponse(
        payload={
            "status": "ok",
            "database": {"engine": "postgres", "reachable": True},
        }
    )


def postgres_tables(connection):
    return sorted(monitor.MAIN_TABLES)


def test_api_healthy():
    session = FakeSession([healthy_api_response()])

    result = monitor.check_api(session=session, sleep_fn=lambda seconds: None)

    assert result["status"] == "OK"
    assert result["metrics"]["database_reachable"] is True
    assert session.calls == [(monitor.DEFAULT_API_URL, 15.0)]


def test_api_timeout_retries_and_sanitizes_message():
    secret = "postgresql://user:secret@private.example/db"
    session = FakeSession([requests.Timeout(secret), requests.Timeout(secret)])
    sleeps = []

    result = monitor.check_api(
        session=session, retries=2, sleep_fn=sleeps.append, timeout=2
    )

    assert result["status"] == "CRITICAL"
    assert result["metrics"]["attempts"] == 2
    assert sleeps == [0.5]
    assert secret not in json.dumps(result)


def test_api_http_error_and_invalid_payload_are_critical():
    error = monitor.check_api(
        session=FakeSession([FakeResponse(status_code=503)]), retries=1
    )
    invalid = monitor.check_api(
        session=FakeSession(
            [FakeResponse(payload={"status": "ok", "database": {"engine": "sqlite", "reachable": True}})]
        ),
        retries=1,
    )

    assert error["status"] == "CRITICAL"
    assert error["summary"] == "HTTP 503"
    assert invalid["status"] == "CRITICAL"


def test_database_url_absent_is_skipped_without_sqlite_fallback():
    calls = []

    checks = monitor.check_database(environ={}, connector=lambda config: calls.append(config))

    assert calls == []
    assert all(check["status"] == "SKIPPED" for check in checks.values())
    assert "SQLite fallback disabled" in checks["database"]["summary"]


def test_database_unavailable_is_critical_and_sanitized():
    secret = "postgresql://user:secret@private.example/db"

    def unavailable(config):
        raise RuntimeError(secret)

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL}, connector=unavailable
    )

    rendered = json.dumps(checks)
    assert checks["database"]["status"] == "CRITICAL"
    assert checks["papers"]["status"] == "SKIPPED"
    assert secret not in rendered
    assert FAKE_DATABASE_URL not in rendered


def test_database_metrics_are_read_only_and_healthy():
    connection = FakeConnection()

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        connector=lambda config: connection,
        table_lister=postgres_tables,
        now=NOW,
    )

    assert checks["database"]["status"] == "OK"
    assert checks["papers"]["metrics"]["count"] == 267
    assert checks["daily_radar"]["status"] == "OK"
    assert checks["weekly_radar"]["status"] == "OK"
    assert checks["source_health"]["metrics"]["healthy"] == 1
    assert connection.statements[0][0] == "SET TRANSACTION READ ONLY"
    assert all(
        statement.startswith(("SET TRANSACTION READ ONLY", "SELECT"))
        for statement, _ in connection.statements
    )
    assert connection.rolled_back and connection.closed


def test_source_failures_are_warning_without_exposing_last_error():
    sources = [
        {
            "source": "Crossref",
            "last_status": "error",
            "success_count": 3,
            "failure_count": 2,
            "consecutive_failures": 1,
            "circuit_open_until": None,
            "last_checked": NOW.isoformat(),
            "last_error": "secret provider URL",
        }
    ]
    connection = FakeConnection(sources=sources)

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        connector=lambda config: connection,
        table_lister=postgres_tables,
        now=NOW,
    )

    source = checks["source_health"]
    assert source["status"] == "WARNING"
    assert source["metrics"]["failing"] == 1
    assert source["metrics"]["sources"][0]["consecutive_failures"] == 1
    assert "secret provider URL" not in json.dumps(source)
    assert "last_error" not in " ".join(sql for sql, _ in connection.statements)


def test_stale_source_error_is_inactive_not_warning():
    sources = [
        {
            "source": "Semantic Scholar",
            "last_status": "error",
            "success_count": 1,
            "failure_count": 3,
            "consecutive_failures": 3,
            "circuit_open_until": None,
            "last_checked": (NOW - timedelta(hours=31)).isoformat(),
        },
        {
            "source": "OpenAlex",
            "last_status": "ok",
            "success_count": 4,
            "failure_count": 1,
            "consecutive_failures": 0,
            "circuit_open_until": None,
            "last_checked": (NOW - timedelta(minutes=30)).isoformat(),
        },
    ]
    connection = FakeConnection(
        latest_search=(NOW - timedelta(minutes=15)).isoformat(),
        sources=sources,
    )

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        connector=lambda config: connection,
        table_lister=postgres_tables,
        now=NOW,
    )

    source = checks["source_health"]
    assert source["status"] == "OK"
    assert source["metrics"]["healthy"] == 1
    assert source["metrics"]["failing"] == 0
    assert source["metrics"]["inactive"] == 1
    semantic = next(item for item in source["metrics"]["sources"] if item["source"] == "Semantic Scholar")
    assert semantic["status"] == "inactive"


def test_explicit_inactive_provider_is_not_counted_healthy():
    sources = [
        {
            "source": "Semantic Scholar",
            "last_status": "inactive",
            "success_count": 0,
            "failure_count": 3,
            "consecutive_failures": 0,
            "circuit_open_until": None,
            "last_checked": NOW.isoformat(),
        }
    ]
    connection = FakeConnection(sources=sources)

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        connector=lambda config: connection,
        table_lister=postgres_tables,
        now=NOW,
    )

    source = checks["source_health"]
    assert source["status"] == "OK"
    assert source["metrics"]["healthy"] == 0
    assert source["metrics"]["failing"] == 0
    assert source["metrics"]["inactive"] == 1
    assert source["metrics"]["sources"][0]["status"] == "inactive"


def test_targeted_search_does_not_make_daily_providers_inactive():
    sources = [
        {
            "source": "Crossref",
            "last_status": "ok",
            "success_count": 4,
            "failure_count": 0,
            "consecutive_failures": 0,
            "circuit_open_until": None,
            "last_checked": (NOW - timedelta(hours=10)).isoformat(),
        },
        {
            "source": "OpenAlex",
            "last_status": "ok",
            "success_count": 4,
            "failure_count": 0,
            "consecutive_failures": 0,
            "circuit_open_until": None,
            "last_checked": (NOW - timedelta(minutes=5)).isoformat(),
        },
    ]
    connection = FakeConnection(
        latest_search=(NOW - timedelta(minutes=1)).isoformat(),
        sources=sources,
    )

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        connector=lambda config: connection,
        table_lister=postgres_tables,
        now=NOW,
    )

    source = checks["source_health"]
    assert source["status"] == "OK"
    assert source["metrics"]["healthy"] == 2
    assert source["metrics"]["inactive"] == 0


def test_open_circuit_is_critical():
    connection = FakeConnection(
        sources=[
            {
                "source": "OpenAlex",
                "last_status": "error",
                "success_count": 1,
                "failure_count": 4,
                "consecutive_failures": 4,
                "circuit_open_until": (NOW + timedelta(minutes=10)).isoformat(),
                "last_checked": NOW.isoformat(),
            }
        ]
    )

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        connector=lambda config: connection,
        table_lister=postgres_tables,
        now=NOW,
    )

    assert checks["source_health"]["status"] == "CRITICAL"
    assert checks["source_health"]["metrics"]["circuits_open"] == 1


def test_staleness_distinguishes_warning_and_critical():
    connection = FakeConnection(
        latest_search=(NOW - timedelta(hours=60)).isoformat(),
        latest_weekly=(NOW - timedelta(days=15)).isoformat(),
    )

    checks = monitor.check_database(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        connector=lambda config: connection,
        table_lister=postgres_tables,
        now=NOW,
    )

    assert checks["daily_radar"]["status"] == "WARNING"
    assert checks["weekly_radar"]["status"] == "CRITICAL"


def test_collect_health_sets_warning_and_critical_overall():
    warning_connection = FakeConnection(papers=0)
    warning = monitor.collect_health(
        environ={"DATABASE_URL": FAKE_DATABASE_URL},
        session=FakeSession([healthy_api_response()]),
        connector=lambda config: warning_connection,
        table_lister=postgres_tables,
        now=NOW,
    )
    critical = monitor.collect_health(
        environ={},
        session=FakeSession([FakeResponse(status_code=500)]),
        retries=1,
        now=NOW,
    )
    skipped_database = monitor.collect_health(
        environ={},
        session=FakeSession([healthy_api_response()]),
        now=NOW,
    )

    assert warning["overall"] == "WARNING"
    assert critical["overall"] == "CRITICAL"
    assert skipped_database["overall"] == "WARNING"


def test_main_writes_valid_json_and_returns_failure_for_critical(tmp_path, monkeypatch, capsys):
    output = tmp_path / "artifacts" / "health.json"
    report = {
        "generated_at": NOW.isoformat(),
        "overall": "CRITICAL",
        "checks": {
            "api": monitor._result("CRITICAL", "HTTP 500"),
            **monitor._skipped_database_checks(),
        },
    }
    monkeypatch.setattr(monitor, "collect_health", lambda **kwargs: report)

    exit_code = monitor.main(["--output", str(output)])
    parsed = json.loads(output.read_text(encoding="utf-8"))
    stdout = capsys.readouterr().out

    assert exit_code == 1
    assert output.parent.is_dir()
    assert parsed == report
    assert "ORION SYSTEM HEALTH" in stdout
    assert "Overall............... CRITICAL" in stdout


def test_monitor_workflow_is_hourly_read_only_and_archives_json():
    workflow = Path(".github/workflows/orion-health-monitor.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "17 * * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: read" in workflow
    assert "DATABASE_URL: ${{ secrets.DATABASE_URL }}" in workflow
    assert "run: PYTHONPATH=. python scripts/orion_health_check.py" in workflow
    assert "uses: actions/upload-artifact@" in workflow
    assert "if: always()" in workflow
    assert "retention-days: 30" in workflow
    assert "pio_dashboard.db" not in workflow
    assert "ORION_API_KEY" not in workflow
    assert "git push" not in workflow
    assert "git commit" not in workflow
    assert "git add" not in workflow


def test_monitor_script_imports_from_repository_root_with_pythonpath():
    env = dict(os.environ)
    env["PYTHONPATH"] = "."

    result = subprocess.run(
        [sys.executable, "scripts/orion_health_check.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--output" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr
