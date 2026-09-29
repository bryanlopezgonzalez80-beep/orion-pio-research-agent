from __future__ import annotations

from datetime import date

import pytest

import deep_harvest

pytestmark = pytest.mark.integration


def test_coverage_catalog_is_broad_and_global():
    queries = deep_harvest.coverage_queries()
    assert len(queries) >= 150
    assert len(queries) == len({q.casefold() for q in queries})
    assert "industrial organizational psychology" in queries
    assert "diversity inclusion workplace" in queries
    assert "human factors work performance" in queries
    assert "return to office employees" in queries
    assert "psicología industrial organizacional Puerto Rico" in queries
    assert any("Puerto Rico" in q for q in queries)
    assert any("Latin America" in q or "América Latina" in q for q in queries)
    assert len(deep_harvest.PIO_JOURNALS) >= 20
    assert "Journal of Applied Psychology" in deep_harvest.PIO_JOURNALS


def test_live_sweep_covers_every_query_and_rotates_keyless_openalex(monkeypatch, sample_paper):
    queries = [
        "leadership effectiveness",
        "employee burnout",
        "AI human resources workplace",
    ]
    calls = []
    saved = []
    settings = {}

    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.setenv("ORION_OPENALEX_QUERIES_PER_RUN", "1")
    monkeypatch.setattr(deep_harvest, "coverage_queries", lambda: queries)
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", ["Journal of Applied Psychology"])
    monkeypatch.setattr(
        deep_harvest, "search_crossref_journal_window", lambda *a, **k: []
    )
    monkeypatch.setattr(
        deep_harvest,
        "get_setting",
        lambda key, default=None: settings.get(key, default),
    )
    monkeypatch.setattr(
        deep_harvest,
        "set_setting",
        lambda key, value: settings.__setitem__(key, value),
    )
    monkeypatch.setattr(
        deep_harvest,
        "upsert_papers",
        lambda papers: saved.extend(papers),
    )

    def fake_search(query, **kwargs):
        sources = kwargs["sources"]
        calls.append((query, list(sources)))
        paper = dict(sample_paper, id=f"id:{len(calls)}", title=query)
        return {
            "received": len(sources),
            "results": [paper],
            "errors": [],
            "source_meta": [
                {
                    "source": source,
                    "status": "ok",
                    "count": 1,
                    "network_requests": 1,
                    "cache_hits": 0,
                    "retries": 0,
                    "rate_limited": False,
                }
                for source in sources
            ],
        }

    monkeypatch.setattr(deep_harvest, "execute_academic_search", fake_search)

    result = deep_harvest.run_live_sweep(max_runtime_seconds=60)

    assert result["queries_processed"] == len(queries)
    assert result["queries_remaining"] == 0
    assert len(saved) == len(queries)
    assert all("Crossref" in sources for _, sources in calls)
    assert all("PubMed" in sources for _, sources in calls)
    assert all("Europe PMC" in sources for _, sources in calls)
    assert sum("OpenAlex" in sources for _, sources in calls) == 1
    assert "arXiv" in calls[-1][1]
    assert result["source_totals"]["Crossref"]["queries"] == 3
    assert settings["deep_harvest.openalex_rotation"] == 1


def test_live_sweep_resumes_after_runtime_budget(monkeypatch, sample_paper):
    queries = ["first", "second", "third"]
    calls = []
    settings = {"deep_harvest.live_rotation": 0}
    ticks = iter([0.0, 0.0, 20.0, 20.0])

    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.setenv("ORION_OPENALEX_QUERIES_PER_RUN", "0")
    monkeypatch.setattr(deep_harvest, "coverage_queries", lambda: queries)
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", [])
    monkeypatch.setattr(
        deep_harvest,
        "get_setting",
        lambda key, default=None: settings.get(key, default),
    )
    monkeypatch.setattr(
        deep_harvest,
        "set_setting",
        lambda key, value: settings.__setitem__(key, value),
    )
    monkeypatch.setattr(deep_harvest.time, "monotonic", lambda: next(ticks, 20.0))
    monkeypatch.setattr(deep_harvest, "upsert_papers", lambda papers: None)

    def fake_search(query, **kwargs):
        calls.append(query)
        return {
            "received": 1,
            "results": [dict(sample_paper, id=f"id:{query}", title=query)],
            "errors": [],
            "source_meta": [],
        }

    monkeypatch.setattr(deep_harvest, "execute_academic_search", fake_search)

    first = deep_harvest.run_live_sweep(max_runtime_seconds=10)

    assert calls == ["first"]
    assert first["queries_processed"] == 1
    assert first["queries_remaining"] == 2
    assert first["stopped_for_runtime_budget"] is True
    assert first["next_query_rotation"] == 1
    assert settings["deep_harvest.live_rotation"] == 1

    # A later run starts at the next query instead of starving the tail.
    ticks2 = iter([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    monkeypatch.setattr(deep_harvest.time, "monotonic", lambda: next(ticks2, 0.0))
    calls.clear()

    second = deep_harvest.run_live_sweep(max_runtime_seconds=10)

    assert calls == ["second", "third", "first"]
    assert second["queries_processed"] == 3
    assert second["queries_remaining"] == 0
    assert second["query_rotation_start"] == 1
    assert settings["deep_harvest.live_rotation"] == 1


def test_live_sweep_uses_all_openalex_queries_when_key_is_configured(monkeypatch, sample_paper):
    queries = ["leadership", "teams"]
    calls = []
    monkeypatch.setenv("OPENALEX_API_KEY", "test-only")
    monkeypatch.setattr(deep_harvest, "coverage_queries", lambda: queries)
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", ["Journal of Applied Psychology"])
    monkeypatch.setattr(
        deep_harvest, "search_crossref_journal_window", lambda *a, **k: []
    )
    monkeypatch.setattr(deep_harvest, "set_setting", lambda *a, **k: None)
    monkeypatch.setattr(deep_harvest, "upsert_papers", lambda papers: None)

    def fake_search(query, **kwargs):
        calls.append(kwargs["sources"])
        return {
            "received": 0,
            "results": [],
            "errors": [],
            "source_meta": [],
        }

    monkeypatch.setattr(deep_harvest, "execute_academic_search", fake_search)
    result = deep_harvest.run_live_sweep(max_runtime_seconds=60)

    assert result["openalex_queries_this_run"] == 2
    assert all("OpenAlex" in sources for sources in calls)


def test_historical_backfill_resumes_month_by_month(monkeypatch, sample_paper):
    settings = {"deep_harvest.backfill_cursor": "2026-09-01"}
    windows = []
    saved = []

    monkeypatch.setattr(deep_harvest, "BACKFILL_QUERIES", ["leadership"])
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", ["Journal of Applied Psychology"])
    monkeypatch.setattr(
        deep_harvest, "search_crossref_journal_window", lambda *a, **k: []
    )
    monkeypatch.setattr(
        deep_harvest,
        "get_setting",
        lambda key, default=None: settings.get(key, default),
    )
    monkeypatch.setattr(
        deep_harvest,
        "set_setting",
        lambda key, value: settings.__setitem__(key, value),
    )
    monkeypatch.setattr(
        deep_harvest,
        "upsert_papers",
        lambda papers: saved.extend(papers),
    )

    def fake_window(query, start_date, end_date, **kwargs):
        windows.append((start_date, end_date))
        return [
            dict(
                sample_paper,
                id=f"{start_date.isoformat()}:{query}",
                published_date=start_date.isoformat(),
            )
        ]

    monkeypatch.setattr(deep_harvest, "search_crossref_window", fake_window)

    result = deep_harvest.run_historical_backfill(months_per_run=2)

    assert windows == [
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 7, 1), date(2026, 7, 31)),
    ]
    assert result["months_processed"] == 2
    assert result["unique_seen"] == 2
    assert result["next_cursor"] == "2026-07-01"
    assert settings["deep_harvest.backfill_cursor"] == "2026-07-01"
    assert len(saved) == 2


def test_historical_backfill_retries_month_after_provider_failure(monkeypatch):
    settings = {"deep_harvest.backfill_cursor": "2026-09-01"}
    monkeypatch.setattr(deep_harvest, "BACKFILL_QUERIES", ["leadership"])
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", [])
    monkeypatch.setattr(
        deep_harvest,
        "get_setting",
        lambda key, default=None: settings.get(key, default),
    )
    monkeypatch.setattr(
        deep_harvest,
        "set_setting",
        lambda key, value: settings.__setitem__(key, value),
    )
    monkeypatch.setattr(deep_harvest, "upsert_papers", lambda papers: None)
    monkeypatch.setattr(
        deep_harvest,
        "search_crossref_window",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("temporary provider error")),
    )

    result = deep_harvest.run_historical_backfill(months_per_run=2)

    assert result["months_processed"] == 1
    assert result["errors"]
    assert result["next_cursor"] == "2026-09-01"
    assert settings["deep_harvest.backfill_cursor"] == "2026-09-01"


def test_harvest_status_exposes_secondary_sources_without_secrets(monkeypatch):
    settings = {
        "deep_harvest.last_run": {"completed_at": "2026-09-28T12:00:00+00:00"},
        "deep_harvest.backfill_cursor": "2025-01-01",
    }
    monkeypatch.setattr(
        deep_harvest,
        "get_setting",
        lambda key, default=None: settings.get(key, default),
    )
    status = deep_harvest.harvest_status()

    assert status["coverage_query_count"] >= 150
    assert status["backfill_cursor"] == "2025-01-01"
    names = {item["name"] for item in status["secondary_sources"]}
    assert {"Google Scholar", "APA PsycNet", "SIOP", "SSRN"} <= names
    assert all(item["url"].startswith("https://") for item in status["secondary_sources"])
