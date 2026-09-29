from __future__ import annotations

from datetime import date

import pytest

import deep_harvest

pytestmark = pytest.mark.integration


def test_coverage_catalog_is_broad_and_global():
    queries = deep_harvest.coverage_queries()
    assert len(queries) >= 80
    assert len(queries) == len({q.casefold() for q in queries})
    assert "industrial organizational psychology" in queries
    assert any("Puerto Rico" in q for q in queries)
    assert any("Latin America" in q or "América Latina" in q for q in queries)


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


def test_live_sweep_uses_all_openalex_queries_when_key_is_configured(monkeypatch, sample_paper):
    queries = ["leadership", "teams"]
    calls = []
    monkeypatch.setenv("OPENALEX_API_KEY", "test-only")
    monkeypatch.setattr(deep_harvest, "coverage_queries", lambda: queries)
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

    assert status["coverage_query_count"] >= 80
    assert status["backfill_cursor"] == "2025-01-01"
    names = {item["name"] for item in status["secondary_sources"]}
    assert {"Google Scholar", "APA PsycNet", "SIOP", "SSRN"} <= names
    assert all(item["url"].startswith("https://") for item in status["secondary_sources"])
