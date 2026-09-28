from __future__ import annotations

import json

import pytest

import daily_agent
import weekly_agent

pytestmark = pytest.mark.integration


def test_agents_import_without_running_refresh():
    assert callable(daily_agent.main)
    assert callable(weekly_agent.main)


def test_daily_agent_main_uses_mocks_and_temporary_reports(tmp_path, monkeypatch, sample_paper):
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(daily_agent, "REPORTS", reports)
    monkeypatch.setattr(daily_agent, "CORE_TOPICS", ["leadership"])
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
