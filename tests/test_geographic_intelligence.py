from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import data_store
import deep_harvest
import geographic_intelligence as geo
from orion_api.main import create_app
from research_agent import deduplicate

pytestmark = pytest.mark.integration


def test_explicit_puerto_rico_sample_is_primary():
    result = geo.classify_geography(
        {"title": "Work engagement", "sample_location": "Puerto Rico"}
    )

    assert result["study_location"] == "Puerto Rico"
    assert result["geography_primary"] == "Puerto Rico"
    assert result["geo_pr"] == 1
    assert result["geography_basis"]["Puerto Rico"] == ["sample_explicit"]


def test_puerto_rico_affiliation_does_not_invent_sample_location():
    result = geo.classify_geography(
        {
            "title": "Work engagement",
            "affiliations": ["Universidad de Puerto Rico, Mayagüez"],
        }
    )

    assert result["study_location"] == ""
    assert result["author_affiliation_location"] == "Puerto Rico"
    assert result["geo_pr"] == 1
    assert result["geography_basis"]["Puerto Rico"] == ["affiliation"]


def test_explicit_usa_sample_is_classified():
    result = geo.classify_geography(
        {"sample_location": "United States", "title": "Leadership"}
    )
    assert result["study_location"] == "United States"
    assert result["geo_us"] == 1


def test_us_affiliation_only_is_not_a_us_sample():
    result = geo.classify_geography(
        {"affiliations": ["Example University, United States"]}
    )
    assert result["study_location"] == ""
    assert result["author_affiliation_location"] == "United States"
    assert result["geo_us"] == 1


def test_multinational_pr_sample_and_us_affiliation_keeps_both_tags():
    result = geo.classify_geography(
        {
            "sample_location": "Puerto Rico",
            "affiliations": ["Example University, United States"],
        }
    )
    assert result["geography_primary"] == "Puerto Rico"
    assert result["geography_tags"] == ["Puerto Rico", "United States"]
    assert result["geo_pr"] == result["geo_us"] == 1


def test_bare_san_juan_is_not_assumed_to_be_puerto_rico():
    ambiguous = geo.classify_geography({"title": "Employees in San Juan"})
    explicit = geo.classify_geography({"title": "Employees in San Juan, Puerto Rico"})
    assert ambiguous["geo_pr"] == 0
    assert explicit["geo_pr"] == 1


def test_doi_and_native_id_deduplication_are_unchanged(sample_paper):
    by_doi = dict(sample_paper, id="provider:a")
    duplicate_doi = dict(sample_paper, id="provider:b")
    by_native_id = dict(sample_paper, id="native:1", doi="", title="First title")
    duplicate_native = dict(by_native_id, title="Richer title")

    assert len(deduplicate([by_doi, duplicate_doi])) == 1
    assert len(deduplicate([by_native_id, duplicate_native])) == 1


def test_additive_sqlite_migration_preserves_existing_papers(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE papers(id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    con.execute("INSERT INTO papers VALUES (?, ?)", ("old:1", "Existing paper"))
    con.commit()
    con.close()
    monkeypatch.setattr(data_store, "DB_PATH", path)

    migrated = data_store.connect()
    columns = {row[1] for row in migrated.execute("PRAGMA table_info(papers)")}
    existing = migrated.execute("SELECT title FROM papers WHERE id=?", ("old:1",)).fetchone()
    migrated.close()

    assert set(data_store.PAPER_COLUMNS) <= columns
    assert existing[0] == "Existing paper"


def test_geography_round_trip_and_parameterized_filter(sample_paper):
    data_store.upsert_papers(
        [{**sample_paper, "sample_location": "Puerto Rico"}]
    )

    stored = data_store.get_paper(sample_paper["id"])
    filtered = data_store.list_papers(geography="puerto_rico")

    assert stored["geo_pr"] == 1
    assert json.loads(stored["geography_tags"]) == ["Puerto Rico"]
    assert [paper["id"] for paper in filtered] == [sample_paper["id"]]
    with pytest.raises(ValueError, match="Unsupported geography"):
        data_store.list_papers(geography="puerto_rico OR 1=1")


def test_papers_and_radar_accept_allowlisted_geography_filter(sample_paper):
    data_store.upsert_papers(
        [
            {**sample_paper, "id": "pr:1", "sample_location": "Puerto Rico"},
            {**sample_paper, "id": "us:1", "sample_location": "United States"},
        ]
    )
    client = TestClient(create_app(), raise_server_exceptions=False)

    papers = client.get("/api/v1/papers", params={"geography": "puerto_rico"})
    radar = client.get("/api/v1/radar", params={"geography": "united_states"})
    invalid = client.get("/api/v1/papers", params={"geography": "x OR 1=1"})

    assert [item["id"] for item in papers.json()["items"]] == ["pr:1"]
    assert papers.json()["items"][0]["geography_tags"] == ["Puerto Rico"]
    assert papers.json()["items"][0]["geography_basis"] == {
        "Puerto Rico": ["sample_explicit"]
    }
    assert [item["id"] for item in radar.json()["items"]] == ["us:1"]
    assert invalid.status_code == 422


def test_postgres_schema_has_additive_geography_columns_and_safe_indexes():
    schema = open("database/schema_postgres.sql", encoding="utf-8").read()
    for column in (
        "geography_primary", "geography_tags", "geography_confidence",
        "geography_basis", "study_location", "affiliation_locations",
        "geo_pr", "geo_us", "geo_latam_caribbean", "evidence_type",
    ):
        assert f"ADD COLUMN IF NOT EXISTS {column}" in schema
    assert "DROP COLUMN" not in schema
    assert "DROP TABLE" not in schema


def test_query_rotation_and_cursors_persist_across_runs(monkeypatch, sample_paper):
    settings = {}
    calls = []
    saved = []
    monkeypatch.setenv("ORION_GEO_PR_QUERIES_PER_RUN", "1")
    monkeypatch.setenv("ORION_GEO_US_QUERIES_PER_RUN", "1")
    monkeypatch.setenv("ORION_GEO_LATAM_QUERIES_PER_RUN", "1")
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.setattr(geo, "get_setting", lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(geo, "set_setting", lambda key, value: settings.__setitem__(key, value))
    monkeypatch.setattr(geo, "upsert_papers", lambda papers: saved.extend(papers))
    monkeypatch.setattr(geo.time, "monotonic", lambda: 0.0)

    def search(query, **kwargs):
        calls.append((query, kwargs["sources"]))
        return {
            "received": 1,
            "results": [dict(sample_paper, id=f"id:{len(calls)}")],
            "errors": [],
            "source_meta": [],
        }

    monkeypatch.setattr(geo, "execute_academic_search", search)
    first = geo.run_geographic_booster()
    first_calls = list(calls)
    calls.clear()
    second = geo.run_geographic_booster()

    assert first["queries_processed"] == second["queries_processed"] == 3
    assert [query for query, _ in calls] != [query for query, _ in first_calls]
    assert settings["geographic_intelligence.puerto_rico_cursor"] == 2
    assert settings["geographic_intelligence.united_states_cursor"] == 2
    assert settings["geographic_intelligence.latam_caribbean_cursor"] == 2
    assert settings["geographic_intelligence.us_state_group"] == 2
    assert all("OpenAlex" not in sources for _, sources in first_calls)
    assert all("Semantic Scholar" not in sources for _, sources in first_calls)
    assert len(saved) == 6


def test_source_failure_and_progress_failure_do_not_abort_booster(monkeypatch, sample_paper):
    settings = {}
    calls = 0
    monkeypatch.setenv("ORION_GEO_PR_QUERIES_PER_RUN", "2")
    monkeypatch.setenv("ORION_GEO_US_QUERIES_PER_RUN", "0")
    monkeypatch.setenv("ORION_GEO_LATAM_QUERIES_PER_RUN", "0")
    monkeypatch.setattr(geo, "get_setting", lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(geo, "set_setting", lambda key, value: settings.__setitem__(key, value))
    monkeypatch.setattr(geo, "upsert_papers", lambda papers: None)
    monkeypatch.setattr(geo.time, "monotonic", lambda: 0.0)

    def search(query, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("provider unavailable")
        return {
            "received": 1,
            "results": [sample_paper],
            "errors": [],
            "source_meta": [],
        }

    monkeypatch.setattr(geo, "execute_academic_search", search)
    result = geo.run_geographic_booster(
        progress_callback=lambda payload: (_ for _ in ()).throw(RuntimeError("UI"))
    )

    assert result["queries_processed"] == 2
    assert result["received"] == 1
    assert result["partial_source_incidents"] == 1
    assert calls == 2


def test_status_is_backward_compatible_and_adds_geography(monkeypatch):
    settings = {"deep_harvest.backfill_cursor": "2025-01-01"}
    monkeypatch.setattr(
        deep_harvest,
        "get_setting",
        lambda key, default=None: settings.get(key, default),
    )
    monkeypatch.setattr(
        deep_harvest,
        "geography_status",
        lambda: {"coverage": {"Puerto Rico": 10}},
    )
    status = deep_harvest.harvest_status()

    assert status["coverage_query_count"] == 188
    assert status["backfill_cursor"] == "2025-01-01"
    assert status["geography"]["coverage"]["Puerto Rico"] == 10


def test_deep_harvest_runs_global_then_geography_then_backfill(monkeypatch):
    order = []
    settings = {}
    monkeypatch.setattr(
        deep_harvest,
        "run_live_sweep",
        lambda progress_callback=None: order.append("global") or {"received": 1},
    )
    monkeypatch.setattr(
        deep_harvest,
        "run_geographic_booster",
        lambda progress_callback=None: order.append("geography") or {"received": 2},
    )
    monkeypatch.setattr(
        deep_harvest,
        "run_historical_backfill",
        lambda **kwargs: order.append("backfill") or {"received": 3},
    )
    monkeypatch.setattr(
        deep_harvest,
        "set_setting",
        lambda key, value: settings.__setitem__(key, value),
    )

    result = deep_harvest.run_deep_harvest(include_backfill=True)

    assert order == ["global", "geography", "backfill"]
    assert result["geography"]["received"] == 2
    assert result["coverage_query_count"] == 188


def test_evidence_types_do_not_invent_peer_review_status():
    assert geo.classify_evidence_type({"source": "CONUCO", "work_type": "article"}) == "professional_publication"
    assert geo.classify_evidence_type({"source": "arXiv", "work_type": "article"}) == "preprint"
    assert geo.classify_evidence_type({"source": "SIOP TIP", "work_type": "article"}) == "professional_publication"


def test_global_taxonomy_remains_exactly_188_queries():
    queries = deep_harvest.coverage_queries()
    assert len(queries) == 188
    assert len(set(query.casefold() for query in queries)) == 188
