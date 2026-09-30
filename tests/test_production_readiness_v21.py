from __future__ import annotations

import json
import inspect
from datetime import date

import pytest
from fastapi.testclient import TestClient

import data_store
import deep_harvest
import source_registry
from orion_api.main import create_app
from orion_api.routes import radar as radar_route
from orion_api.services.paper_service import _normalize_paper
from platform_store import enrichment_summary, get_checkpoint

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_progress_is_monotonic_across_harvest_phases(monkeypatch):
    snapshots = []
    counts = iter((10, 12))
    monkeypatch.setattr(deep_harvest, "db_stats", lambda: {"papers": next(counts)})
    monkeypatch.setattr(deep_harvest, "coverage_queries", lambda: ["q"] * 188)
    monkeypatch.setattr(deep_harvest, "set_setting", lambda *args: None)

    def live(progress_callback=None):
        progress_callback({"phase": "taxonomy", "queries_processed": 188, "queries_total": 188, "received": 40, "unique_seen": 30, "journal_watch_processed": 10, "source_totals": {"Crossref": {"results": 40}}})
        return {"received": 40, "unique_seen": 30, "errors": []}

    def geography(progress_callback=None):
        progress_callback({"geography_phase": "Puerto Rico", "geo_queries_processed": 2, "geo_queries_total": 5})
        return {"received": 5, "unique_seen": 4, "errors": []}

    def backfill(progress_callback=None):
        progress_callback({"phase": "backfill", "backfill_tasks_completed": 3, "backfill_tasks_total": 10})
        return {"received": 7, "unique_seen": 6, "errors": []}

    monkeypatch.setattr(deep_harvest, "run_live_sweep", live)
    monkeypatch.setattr(deep_harvest, "run_geographic_booster", geography)
    monkeypatch.setattr(deep_harvest, "run_historical_backfill", backfill)

    result = deep_harvest.run_deep_harvest(progress_callback=lambda value: snapshots.append(value))

    assert all(item["queries_processed"] == 188 for item in snapshots)
    assert all(item["received"] == 40 for item in snapshots)
    assert snapshots[-1]["geo_queries_processed"] == 2
    assert snapshots[-1]["backfill_tasks_completed"] == 3
    assert result["total_papers_persisted"] == 12
    assert result["new_papers_this_run"] == 2
    assert result["records_received_this_run"] == 52


def test_geographic_upsert_unions_provenance_without_inventing_sample(sample_paper):
    data_store.upsert_papers([{
        **sample_paper, "id": "geo", "title": "Puerto Rican workers",
        "study_location": "Puerto Rico", "geography_tags": ["Puerto Rico"],
        "geography_basis": {"Puerto Rico": ["study_location_explicit"]},
    }])
    data_store.upsert_papers([{
        **sample_paper, "id": "geo", "title": "American employees",
        "author_affiliation_location": "United States",
        "geography_tags": ["United States"],
        "geography_basis": {"United States": ["affiliation"]},
    }])
    stored = data_store.get_paper("geo")
    assert json.loads(stored["geography_tags"]) == ["Puerto Rico", "United States"]
    basis = json.loads(stored["geography_basis"])
    assert "study_location_explicit" in basis["Puerto Rico"]
    assert "affiliation" in basis["United States"]
    assert stored["study_location"] == "Puerto Rico"
    assert stored["geo_pr"] == stored["geo_us"] == 1


def test_backfill_429_leaves_remaining_tasks_pending(monkeypatch):
    settings = {"deep_harvest.backfill_cursor": "2026-09-01"}
    calls = []
    monkeypatch.setattr(deep_harvest, "BACKFILL_QUERIES", ["one", "two", "three"])
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", [])
    monkeypatch.setattr(deep_harvest, "get_setting", lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(deep_harvest, "set_setting", lambda key, value: settings.__setitem__(key, value))

    def limited(query, *args, **kwargs):
        calls.append(query)
        if query == "two":
            raise RuntimeError("HTTP 429 rate limit")
        return []

    monkeypatch.setattr(deep_harvest, "search_crossref_window", limited)
    result = deep_harvest.run_historical_backfill(months_per_run=12)

    assert calls == ["one", "two"]
    assert get_checkpoint("2026-08-01", "Crossref", "query", "one")["status"] == "COMPLETED"
    assert get_checkpoint("2026-08-01", "Crossref", "query", "two")["status"] == "RATE_LIMITED"
    assert get_checkpoint("2026-08-01", "Crossref", "query", "three")["status"] == "PENDING"
    assert result["next_cursor"] == "2026-09-01"


def test_backfill_honors_retry_after_before_recovery(monkeypatch):
    class Response:
        status_code = 429
        headers = {"Retry-After": "1.25"}

    class Limited(Exception):
        response = Response()

    attempts = []
    sleeps = []
    monkeypatch.setattr(deep_harvest, "BACKFILL_QUERIES", ["one"])
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", [])
    monkeypatch.setattr(deep_harvest, "get_setting", lambda key, default=None: "2026-09-01" if key.endswith("backfill_cursor") else default)
    monkeypatch.setattr(deep_harvest, "set_setting", lambda *args: None)

    def recover(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise Limited("limited")
        return []

    monkeypatch.setattr(deep_harvest, "search_crossref_window", recover)
    result = deep_harvest.run_historical_backfill(months_per_run=1, sleep_fn=sleeps.append)

    assert len(attempts) == 2
    assert sleeps == [1.25]
    assert result["errors"] == []


def test_persistent_429_uses_status_code_and_stops_provider(monkeypatch):
    class Response:
        status_code = 429
        headers = {"Retry-After": "0"}

    class Limited(Exception):
        response = Response()

    calls = []
    monkeypatch.setattr(deep_harvest, "BACKFILL_QUERIES", ["one", "two"])
    monkeypatch.setattr(deep_harvest, "PIO_JOURNALS", [])
    monkeypatch.setattr(deep_harvest, "get_setting", lambda key, default=None: "2026-09-01" if key.endswith("backfill_cursor") else default)
    monkeypatch.setattr(deep_harvest, "set_setting", lambda *args: None)

    def limited(query, *args, **kwargs):
        calls.append(query)
        raise Limited("temporarily unavailable")

    monkeypatch.setattr(deep_harvest, "search_crossref_window", limited)
    deep_harvest.run_historical_backfill(months_per_run=1, sleep_fn=lambda _delay: None)

    assert calls == ["one", "one", "one"]
    assert get_checkpoint("2026-08-01", "Crossref", "query", "one")["status"] == "RATE_LIMITED"
    assert get_checkpoint("2026-08-01", "Crossref", "query", "two")["status"] == "PENDING"


def test_enrichment_queue_is_idempotent_after_persistence(sample_paper):
    data_store.upsert_papers([sample_paper, dict(sample_paper)])
    summary = enrichment_summary()
    assert summary["pending"] == 1
    assert summary["completed"] == 0


def test_access_upsert_never_degrades_open_access(sample_paper):
    data_store.upsert_papers([{
        **sample_paper, "id": "access", "oa_url": "https://repository.example/open",
    }])
    data_store.upsert_papers([{
        **sample_paper, "id": "access", "oa_url": "", "url": "https://publisher.example/landing",
    }])
    stored = data_store.get_paper("access")
    assert stored["access_status"] == "OPEN_ACCESS"
    assert stored["best_access_url"] == "https://repository.example/open"
    assert stored["open_access"] == 1
    assert {item["url"] for item in json.loads(stored["alternative_access_options"])} >= {"https://publisher.example/landing"}


def test_open_access_filter_and_observability_use_boolean(sample_paper):
    data_store.upsert_papers([{**sample_paper, "id": "oa", "oa_url": "https://repository.example/open"}])
    con = data_store.connect()
    try:
        con.execute("UPDATE papers SET access_status='DOI_ONLY', open_access=1 WHERE id=?", ("oa",))
        con.commit()
    finally:
        con.close()
    assert [row["id"] for row in data_store.list_papers(open_access=True)] == ["oa"]
    assert data_store.evidence_observability()["open_access"] == 1


def test_preprint_observability_clause_is_not_duplicated(sample_paper):
    data_store.upsert_papers([{**sample_paper, "id": "pre", "source": "arXiv", "work_type": "preprint"}])
    assert data_store.evidence_observability()["preprints"] == 1
    assert "IN ('PREPRINT','PREPRINT')" not in inspect.getsource(data_store.evidence_observability)


def test_backfill_progress_resets_current_month_and_keeps_run_total(monkeypatch):
    snapshots = []
    counts = iter((0, 0))
    monkeypatch.setattr(deep_harvest, "db_stats", lambda: {"papers": next(counts)})
    monkeypatch.setattr(deep_harvest, "coverage_queries", lambda: ["q"] * 188)
    monkeypatch.setattr(deep_harvest, "set_setting", lambda *args: None)
    monkeypatch.setattr(deep_harvest, "run_live_sweep", lambda progress_callback=None: {"received": 0, "unique_seen": 0, "errors": []})
    monkeypatch.setattr(deep_harvest, "run_geographic_booster", lambda progress_callback=None: {"received": 0, "unique_seen": 0, "errors": []})

    def backfill(progress_callback=None):
        progress_callback({"phase": "backfill", "backfill_month": "2026-08-01", "backfill_tasks_completed": 33, "backfill_tasks_total": 33, "backfill_month_tasks_completed": 33, "backfill_month_tasks_total": 33, "backfill_tasks_completed_total": 33})
        progress_callback({"phase": "backfill", "backfill_month": "2026-07-01", "backfill_tasks_completed": 0, "backfill_tasks_total": 33, "backfill_month_tasks_completed": 0, "backfill_month_tasks_total": 33, "backfill_tasks_completed_total": 33})
        return {"received": 0, "unique_seen": 0, "errors": []}

    monkeypatch.setattr(deep_harvest, "run_historical_backfill", backfill)
    deep_harvest.run_deep_harvest(progress_callback=snapshots.append)

    assert snapshots[-1]["backfill_month"] == "2026-07-01"
    assert snapshots[-1]["backfill_month_tasks_completed"] == 0
    assert snapshots[-1]["backfill_tasks_completed"] == 0
    assert snapshots[-1]["backfill_tasks_completed_total"] == 33


def test_registry_lifecycle_does_not_claim_unimplemented_adapters(monkeypatch):
    monkeypatch.setenv("PROQUEST_API_ENABLED", "true")
    monkeypatch.setenv("PROQUEST_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("PROQUEST_API_AUTHORIZED", "true")
    providers = source_registry.source_registry()
    assert providers["crossref"].implemented is providers["crossref"].active is True
    assert providers["core"].registered is True
    assert providers["core"].implemented is providers["core"].active is False
    assert providers["proquest"].configured is providers["proquest"].authorized is True
    assert providers["proquest"].implemented is providers["proquest"].active is False


def test_v21_filters_are_exact_and_global_is_allowlisted(sample_paper):
    data_store.upsert_papers([
        {**sample_paper, "id": "global", "peer_review_status": "CONFIRMED", "access_status": "DOI_ONLY"},
        {**sample_paper, "id": "pr", "title": "Puerto Rico workforce", "doi": "10.1/pr", "retraction_status": "EXPRESSION_OF_CONCERN"},
    ])
    assert [row["id"] for row in data_store.list_papers(geography="global")] == ["global"]
    assert [row["id"] for row in data_store.list_papers(peer_review_status="CONFIRMED")] == ["global"]
    assert {row["id"] for row in data_store.list_papers(access_status="PUBLISHER_ACCESS")} == {"global", "pr"}
    assert [row["id"] for row in data_store.list_papers(retraction_status="EXPRESSION_OF_CONCERN")] == ["pr"]


def test_postgres_schema_is_additive_and_contains_v21_contract():
    schema = (data_store.Path(__file__).parents[1] / "database" / "schema_postgres.sql").read_text(encoding="utf-8")
    assert "DROP TABLE" not in schema.upper()
    assert "TRUNCATE" not in schema.upper()
    for field in ("abstract_available", "access_type", "institutional_access_possible", "alternative_access_options"):
        assert f"ADD COLUMN IF NOT EXISTS {field}" in schema
    for table in ("paper_external_ids", "orion_enrichment_queue", "orion_harvest_checkpoints", "orion_source_metrics"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema


def test_exact_global_query_contract_is_251():
    assert len(deep_harvest.coverage_queries()) == 251


def test_v21_status_contract_is_additive_and_fast_shape(client):
    response = client.get("/api/v1/radar/status")
    assert response.status_code == 200
    body = response.json()
    assert body["corpus"]["total_papers"] == 0
    assert body["run"]["records_received_this_run"] == 0
    assert body["geography_summary"]["global_or_unknown"] == 0
    assert body["historical"]["target_months_per_run"] == 12
    assert body["historical"]["estimated_months_remaining"] is None
    assert body["enrichment"] == {"completed": 0, "pending": 0, "by_status": {}}
    assert set(("registered", "implemented", "configured", "authorized", "active")) <= body["providers"].keys()
    assert body["providers"]["registered"] >= body["providers"]["active"]
    assert body["providers"]["registry"] == body["provider_registry"]
    assert "coverage_query_count" in body


def test_api_rejects_non_allowlisted_filter_values(client):
    assert client.get("/api/v1/papers?peer_review_status=trusted").status_code == 422
    assert client.get("/api/v1/radar?access_status=free").status_code == 422


@pytest.mark.parametrize(
    ("paper_id", "evidence_type", "peer_review_status"),
    [
        ("preprint", "PREPRINT", "NOT_PEER_REVIEWED"),
        ("systematic", "SYSTEMATIC_REVIEW", "CONFIRMED"),
        ("meta", "META_ANALYSIS", "CONFIRMED"),
        ("unknown-review", "UNKNOWN", "UNKNOWN"),
    ],
)
def test_v21_evidence_types_and_unknown_peer_review_round_trip(
    client, sample_paper, paper_id, evidence_type, peer_review_status
):
    data_store.upsert_papers([{**sample_paper, "id": paper_id, "doi": f"10.1/{paper_id}"}])
    con = data_store.connect()
    try:
        con.execute(
            "UPDATE papers SET evidence_type=?, peer_review_status=? WHERE id=?",
            (evidence_type, peer_review_status, paper_id),
        )
        con.commit()
    finally:
        con.close()

    response = client.get("/api/v1/papers", params={"evidence_type": evidence_type})

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["id"] == paper_id)
    assert item["evidence_type"] == evidence_type
    assert item["peer_review_status"] == peer_review_status


@pytest.mark.parametrize(
    ("paper_id", "access_status", "requires_login", "open_access"),
    [
        ("oa", "OPEN_ACCESS", 0, 1),
        ("institution", "INSTITUTIONAL_ACCESS", 1, 0),
        ("provider", "PROVIDER_LOGIN", 1, 0),
        ("doi", "DOI_ONLY", 0, 0),
        ("metadata", "METADATA_ONLY", 0, 0),
    ],
)
def test_v21_access_states_are_preserved_for_site_actions(
    client, sample_paper, paper_id, access_status, requires_login, open_access
):
    data_store.upsert_papers([{**sample_paper, "id": paper_id, "doi": f"10.1/{paper_id}"}])
    con = data_store.connect()
    try:
        con.execute(
            "UPDATE papers SET access_status=?, requires_login=?, open_access=? WHERE id=?",
            (access_status, requires_login, open_access, paper_id),
        )
        con.commit()
    finally:
        con.close()

    response = client.get("/api/v1/papers", params={"access_status": access_status})

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["id"] == paper_id)
    assert item["access_status"] == access_status
    assert item["requires_login"] == requires_login
    assert item["open_access"] == open_access


@pytest.mark.parametrize("status", ["RETRACTED", "EXPRESSION_OF_CONCERN"])
def test_v21_integrity_alert_states_round_trip(client, sample_paper, status):
    paper_id = status.casefold()
    data_store.upsert_papers([{**sample_paper, "id": paper_id, "doi": f"10.1/{paper_id}"}])
    con = data_store.connect()
    try:
        con.execute("UPDATE papers SET retraction_status=? WHERE id=?", (status, paper_id))
        con.commit()
    finally:
        con.close()

    response = client.get("/api/v1/papers", params={"retraction_status": status})

    assert response.status_code == 200
    assert response.json()["items"][0]["retraction_status"] == status


def test_v21_partial_and_null_paper_fields_normalize_safely():
    normalized = _normalize_paper({"id": "partial", "title": None, "geography_basis": None})

    assert normalized["title"] == "Sin título"
    assert normalized["peer_review_status"] == "UNKNOWN"
    assert normalized["geography_tags"] == []
    assert normalized["geography_basis"] == {}
    assert normalized["alternative_access_options"] == []
    assert normalized["open_access"] == 0


def test_affiliation_only_never_becomes_study_location(sample_paper):
    data_store.upsert_papers([{
        **sample_paper,
        "id": "affiliation-only",
        "title": "Workplace study",
        "study_location": "",
        "author_affiliation_location": "Puerto Rico",
        "affiliation_locations": ["Puerto Rico"],
        "geography_tags": ["Puerto Rico"],
        "geography_basis": {"Puerto Rico": ["affiliation"]},
    }])

    stored = data_store.get_paper("affiliation-only")
    assert stored["study_location"] == ""
    assert json.loads(stored["affiliation_locations"]) == ["Puerto Rico"]
    assert json.loads(stored["geography_basis"]) == {"Puerto Rico": ["affiliation"]}


def test_manual_refresh_exposes_completed_with_warnings(client, monkeypatch):
    state = {}
    monkeypatch.setattr(radar_route, "get_setting", lambda key, default=None: state.get(key, default))
    monkeypatch.setattr(radar_route, "set_setting", lambda key, value: state.__setitem__(key, value))
    monkeypatch.setattr(
        radar_route,
        "run_live_sweep",
        lambda **kwargs: {
            "queries_processed": 251,
            "queries_total": 251,
            "queries_remaining": 0,
            "errors": ["sanitized"],
            "received": 2,
            "unique_seen": 1,
        },
    )

    response = client.post("/api/v1/radar/refresh")

    assert response.status_code == 202
    assert state[radar_route._MANUAL_STATUS_KEY]["state"] == "completed_with_warnings"


def test_site_v21_spec_defines_terminal_error_and_mobile_contract():
    spec = (data_store.Path(__file__).parents[1] / "site_migration" / "SITE_V21_SPEC.md").read_text(encoding="utf-8")
    for value in (
        "completed_with_warnings", "`429`", "`503`", "`504`",
        "Mobile/iPhone", "backfill_month_tasks_completed",
        "backfill_tasks_completed_total", "registered", "active",
    ):
        assert value in spec
