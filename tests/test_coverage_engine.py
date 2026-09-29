from __future__ import annotations

from collections import Counter

import pytest

import coverage_engine
from coverage_catalog import COVERAGE_TOPICS, coverage_domains, coverage_queries

pytestmark = pytest.mark.unit


def test_coverage_catalog_is_broad_and_unique():
    assert len(COVERAGE_TOPICS) >= 100
    assert len(coverage_domains()) >= 10
    queries = coverage_queries()
    assert len(queries) == len(set(queries))
    assert "industrial organizational psychology" in queries
    assert "organizational development" in queries
    assert any("Puerto Rico" in query for query in queries)


def test_source_plan_respects_context_and_optional_keys(monkeypatch):
    counters = Counter()
    wellbeing = next(t for t in COVERAGE_TOPICS if t.biomedical)
    tech = next(t for t in COVERAGE_TOPICS if t.technology)

    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)

    well_sources = coverage_engine._source_plan(wellbeing, counters)
    tech_sources = coverage_engine._source_plan(tech, counters)

    assert "Crossref" in well_sources
    assert "OpenAlex" in well_sources
    assert "Europe PMC" in well_sources
    assert "arXiv" in tech_sources
    assert "Semantic Scholar" not in well_sources

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "test-key")
    assert "Semantic Scholar" in coverage_engine._source_plan(wellbeing, counters)


def test_comprehensive_refresh_persists_chunks_and_progress(monkeypatch, sample_paper):
    topics = list(COVERAGE_TOPICS[:3])
    created = []
    updates = []
    saved = []

    monkeypatch.setattr(coverage_engine, "create_coverage_run", lambda trigger, total: created.append((trigger, total)) or 11)
    monkeypatch.setattr(coverage_engine, "update_coverage_run", lambda run_id, **kwargs: updates.append((run_id, kwargs)))
    monkeypatch.setattr(coverage_engine, "upsert_papers", lambda papers: saved.extend(papers))

    def fake_search(query, **kwargs):
        paper = dict(
            sample_paper,
            id=f"id:{query}",
            doi="",
            url=f"https://example.test/recent/{query.replace(' ', '-')}",
            title=f"Study about {query}",
            topic_relevance_percent=100,
        )
        return {
            "results": [paper],
            "source_meta": [{"source": "Crossref", "count": 1}],
            "errors": [],
        }

    monkeypatch.setattr(coverage_engine, "execute_academic_search", fake_search)
    monkeypatch.setattr(coverage_engine, "pace_source_request", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        coverage_engine,
        "search_crossref_range",
        lambda query, start_date, end_date, per_page: [
            dict(
                sample_paper,
                id=f"historical:{query}",
                doi="",
                url=f"https://example.test/historical/{query.replace(' ', '-')}",
                title=f"Historical study about {query}",
                topic_relevance_percent=100,
            )
        ],
    )

    result = coverage_engine.run_comprehensive_refresh(
        trigger="manual",
        topics=topics,
        days=2,
        per_source=5,
    )

    assert created == [("manual", 6)]
    assert result["status"] == "success"
    assert result["topics_completed"] == 6
    assert result["topics_total"] == 6
    assert result["unique_processed"] == 6
    assert len(saved) == 6
    assert updates[-1][1]["status"] == "success"
    assert updates[-1][1]["completed"] is True
