from __future__ import annotations

import json
from pathlib import Path

import pytest

import daily_agent
import data_store
import weekly_agent
from database.connection import DatabaseConnectionError

pytestmark = pytest.mark.integration


def test_agents_import_without_running_refresh():
    assert callable(daily_agent.main)
    assert callable(weekly_agent.main)


def test_daily_agent_main_uses_mocks_and_temporary_reports(tmp_path, monkeypatch, sample_paper):
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(daily_agent, "REPORTS", reports)
    monkeypatch.setattr(daily_agent, "CORE_TOPICS", ["leadership"])
    monkeypatch.setattr(daily_agent, "verify_database_backend", lambda: "sqlite")
    monkeypatch.setattr(daily_agent, "alerts_due", lambda: [
        {"id": 1, "query": "Ley 80 Puerto Rico", "domain": "auto", "sources_json": "[]"},
        {"id": 2, "query": "teams", "domain": "academic", "sources_json": "invalid"},
    ])
    monkeypatch.setattr(daily_agent, "route_query", lambda query, domain="auto": {
        "domain": "legal_pr" if "Ley" in query else "academic",
        "manual_sources": ["SUTRA"], "automated_sources": ["OpenAlex"],
    })
    monkeypatch.setattr(daily_agent, "_run", lambda query, sources=None: {
        "results": [dict(sample_paper, id=query)], "errors": [], "received": 1, "unique": 1,
    })
    saved, marked = [], []
    monkeypatch.setattr(daily_agent, "upsert_papers", lambda papers: saved.extend(papers))
    monkeypatch.setattr(daily_agent, "mark_alert_run", marked.append)
    daily_agent.main()
    assert len(saved) == 2
    assert marked == [1, 2]
    json_file = next(reports.glob("daily_*.json"))
    assert json.loads(json_file.read_text(encoding="utf-8"))["results_seen"] == 2
    assert next(reports.glob("daily_*.md")).stat().st_size > 0


def test_weekly_agent_main_uses_mocks_and_temporary_reports(tmp_path, monkeypatch, sample_paper):
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(weekly_agent, "REPORTS", reports)
    monkeypatch.setattr(weekly_agent, "DEFAULT_TOPICS", ["leadership"])
    monkeypatch.setattr(weekly_agent, "DEFAULT_SOURCES", ["OpenAlex"])
    monkeypatch.setattr(weekly_agent, "verify_database_backend", lambda: "sqlite")
    monkeypatch.setattr(weekly_agent, "search_all_sources", lambda *a, **k: ([sample_paper], []))
    monkeypatch.setattr(weekly_agent, "deduplicate", lambda papers: list(papers))
    saved, runs = [], []
    monkeypatch.setattr(weekly_agent, "upsert_papers", lambda papers: saved.extend(papers))
    monkeypatch.setattr(weekly_agent, "log_radar_run", lambda *args: runs.append(args))
    weekly_agent.main()
    assert saved == [sample_paper]
    assert len(runs) == 1
    report = next(reports.glob("weekly_*.md"))
    assert sample_paper["title"] in report.read_text(encoding="utf-8")


@pytest.mark.parametrize("agent", [daily_agent, weekly_agent])
@pytest.mark.parametrize(
    ("database_url", "expected_engine"),
    [
        (None, "sqlite"),
        ("postgresql://user:test-only@db.example.test/orion", "postgres"),
    ],
)
def test_cloud_agents_select_configured_database(
    agent, database_url, expected_engine, monkeypatch
):
    selected = []

    class FakeConnection:
        def __init__(self, engine):
            self.engine = engine

        def commit(self):
            pass

        def close(self):
            pass

    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    def fake_connect_database(*, sqlite_path):
        from database.config import get_database_config

        engine = get_database_config(sqlite_path).engine
        selected.append(engine)
        return FakeConnection(engine)

    monkeypatch.setattr(data_store, "connect_database", fake_connect_database)
    monkeypatch.setattr(data_store, "ensure_postgres_schema", lambda connection: None)
    monkeypatch.setattr(data_store, "_init_schema", lambda connection: None)
    monkeypatch.setattr(agent, "verify_database_backend", data_store.verify_database_backend)

    assert agent.verify_database_backend() == expected_engine
    assert selected == [expected_engine]


@pytest.mark.parametrize("agent", [daily_agent, weekly_agent])
def test_cloud_agents_fail_before_work_when_postgres_is_unavailable(agent, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:test-only@db.example.test/orion"
    )
    monkeypatch.setattr(
        agent,
        "verify_database_backend",
        lambda: (_ for _ in ()).throw(
            DatabaseConnectionError("Unable to connect to the configured PostgreSQL database")
        ),
    )
    if agent is daily_agent:
        monkeypatch.setattr(
            agent, "_run", lambda *args, **kwargs: pytest.fail("daily work started")
        )
    else:
        monkeypatch.setattr(
            agent,
            "search_all_sources",
            lambda *args, **kwargs: pytest.fail("weekly work started"),
        )

    with pytest.raises(DatabaseConnectionError, match="configured PostgreSQL"):
        agent.main()


@pytest.mark.parametrize(
    "workflow",
    [
        Path(".github/workflows/daily-radar.yml"),
        Path(".github/workflows/weekly-radar.yml"),
    ],
)
def test_cloud_agent_workflows_pass_database_secret_without_exposing_it(workflow):
    contents = workflow.read_text(encoding="utf-8")

    assert "DATABASE_URL: ${{ secrets.DATABASE_URL }}" in contents
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in contents
    assert "OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}" in contents
    assert "SEMANTIC_SCHOLAR_API_KEY: ${{ secrets.SEMANTIC_SCHOLAR_API_KEY }}" in contents
    assert "DATABASE_URL=" not in contents
