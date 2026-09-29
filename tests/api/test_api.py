from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import data_store
from database.connection import DatabaseConnectionError
from orion_api.config import APISettings, DEFAULT_ALLOWED_ORIGINS, get_settings
from orion_api.errors import ExternalRateLimit, ExternalSearchError, ExternalSearchTimeout
from orion_api.main import create_app
from orion_api.routes import health as health_route
from orion_api.routes import radar as radar_route
from orion_api.services import paper_service, research_service

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_health_healthy_is_sanitized(client, monkeypatch):
    monkeypatch.setattr(
        health_route,
        "check_database_health",
        lambda: {
            "engine": "postgres",
            "reachable": True,
            "basic_query": "pass",
            "latency_ms": 4.2,
            "database_url": "must-not-leak",
        },
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": {"engine": "postgres", "reachable": True},
    }
    assert "must-not-leak" not in response.text


def test_health_database_down_returns_503_without_error_details(client, monkeypatch):
    monkeypatch.setattr(
        health_route,
        "check_database_health",
        lambda: {
            "engine": "postgres",
            "reachable": False,
            "basic_query": "fail",
            "error": "postgresql://user:secret@example.test/db",
        },
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "secret" not in response.text


def _seed_papers(sample_paper):
    data_store.upsert_papers(
        [
            sample_paper,
            dict(
                sample_paper,
                id="openalex:W2",
                title="Remote teams and trust",
                source="Crossref",
                year=2024,
                relevance_score=4,
            ),
            dict(
                sample_paper,
                id="arxiv:3",
                title="Artificial intelligence at work",
                source="arXiv",
                year=2023,
                relevance_score=2,
            ),
        ]
    )


def test_papers_pagination_and_filters(client, sample_paper):
    _seed_papers(sample_paper)

    page = client.get("/api/v1/papers", params={"limit": 1, "offset": 1})
    filtered = client.get(
        "/api/v1/papers",
        params={"query": "Remote", "source": "Crossref", "year": 2024},
    )

    assert page.status_code == 200
    assert page.json()["count"] == 1
    assert page.json()["offset"] == 1
    assert filtered.status_code == 200
    assert [paper["id"] for paper in filtered.json()["items"]] == ["openalex:W2"]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"query": "x"},
        {"year": 1200},
    ],
)
def test_papers_reject_unsafe_pagination_and_filters(client, params):
    assert client.get("/api/v1/papers", params=params).status_code == 422


def test_radar_is_accumulated_and_new_results_do_not_replace_old(client, sample_paper):
    first = dict(sample_paper, id="radar:first", title="First radar result")
    second = dict(sample_paper, id="radar:second", title="Second radar result")
    data_store.upsert_papers([first])

    before = client.get("/api/v1/radar", params={"limit": 100})
    data_store.upsert_papers([second])
    after = client.get("/api/v1/radar", params={"limit": 100})

    assert before.status_code == 200
    assert after.status_code == 200
    before_ids = {paper["id"] for paper in before.json()["items"]}
    after_ids = {paper["id"] for paper in after.json()["items"]}
    assert "radar:first" in before_ids
    assert {"radar:first", "radar:second"} <= after_ids


def test_radar_status_and_manual_refresh_are_nonblocking(client, monkeypatch):
    state = {}
    snapshots = []
    monkeypatch.setattr(
        radar_route,
        "harvest_status",
        lambda: {"coverage_query_count": 99, "backfill_cursor": "2026-01-01"},
    )
    monkeypatch.setattr(
        radar_route,
        "get_setting",
        lambda key, default=None: state.get(key, default),
    )

    def save_setting(key, value):
        state[key] = value
        if key == radar_route._MANUAL_STATUS_KEY:
            snapshots.append(dict(value))

    monkeypatch.setattr(radar_route, "set_setting", save_setting)

    def fake_harvest(include_backfill=False, progress_callback=None):
        assert include_backfill is False
        progress_callback(
            {
                "phase": "taxonomy",
                "queries_processed": 40,
                "queries_total": 99,
                "received": 70,
                "unique_seen": 50,
                "journal_watch_processed": 0,
                "journal_watch_total": 23,
                "source_totals": {"Crossref": {"results": 50}},
            }
        )
        return {
            "live": {
                "queries_processed": 99,
                "queries_total": 99,
                "received": 123,
                "unique_seen": 88,
                "errors": [],
                "source_totals": {"Crossref": {"results": 80}},
                "journal_watch_processed": 23,
                "journal_watch_count": 23,
            }
        }

    monkeypatch.setattr(radar_route, "run_deep_harvest", fake_harvest)

    status = client.get("/api/v1/radar/status")
    refresh = client.post("/api/v1/radar/refresh")
    after = client.get("/api/v1/radar/status")

    assert status.status_code == 200
    assert status.json()["coverage_query_count"] == 99
    assert refresh.status_code == 202
    assert refresh.json()["status"] == "queued"
    assert any(
        item.get("state") == "running"
        and item.get("queries_processed") == 40
        and item.get("queries_total") == 99
        for item in snapshots
    )
    # TestClient executes Starlette background tasks before returning.
    assert after.json()["manual_refresh"]["state"] == "completed"
    assert after.json()["manual_refresh"]["queries_processed"] == 99
    assert after.json()["manual_refresh"]["source_totals"]["Crossref"]["results"] == 80


def test_paper_detail_supports_text_id_with_slash(client, sample_paper):
    data_store.upsert_papers([sample_paper])

    response = client.get("/api/v1/papers/doi:10.1234/orion")

    assert response.status_code == 200
    assert response.json()["id"] == "doi:10.1234/orion"


def test_paper_detail_returns_404(client):
    response = client.get("/api/v1/papers/missing:text-id")
    assert response.status_code == 404
    assert response.json() == {"detail": "Paper not found"}


def test_sources_are_public_and_contain_no_credentials(client, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "provider-secret")
    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    assert any(item["name"] == "OpenAlex" for item in response.json())
    assert "provider-secret" not in response.text
    assert "credential_env" not in response.text
    assert "credential_configured" not in response.text


def test_search_uses_mocked_service_without_network(client, monkeypatch, sample_paper):
    monkeypatch.setattr(
        research_service,
        "search",
        lambda query, limit: {
            "query": query,
            "origin": "research",
            "results": [sample_paper],
            "count": 1,
            "metadata": {"external_search": True},
        },
    )

    response = client.post(
        "/api/v1/search", json={"query": "psychological safety", "limit": 10}
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == sample_paper["id"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": " "},
        {"query": "valid", "limit": 0},
        {"query": "valid", "limit": 51},
        {"query": "x" * 301},
        {"query": ["not", "text"]},
    ],
)
def test_search_rejects_bad_payload(client, payload):
    response = client.post("/api/v1/search", json=payload)
    assert response.status_code == 422


def test_research_service_prefers_existing_library(monkeypatch, sample_paper):
    external_called = []
    monkeypatch.setattr(
        paper_service, "list_papers", lambda **kwargs: [sample_paper]
    )
    monkeypatch.setattr(
        research_service,
        "execute_academic_search",
        lambda *args, **kwargs: external_called.append(True),
    )

    result = research_service.search("leadership", 10)

    assert result["origin"] == "library"
    assert result["results"] == [sample_paper]
    assert external_called == []


def test_research_service_reuses_english_library_match_for_spanish_query(
    monkeypatch, sample_paper
):
    queries = []
    external_called = []

    def list_papers(**kwargs):
        queries.append(kwargs.get("query"))
        if kwargs.get("query") == "organizational development and leadership":
            return [sample_paper]
        return []

    monkeypatch.setattr(paper_service, "list_papers", list_papers)
    monkeypatch.setattr(
        research_service,
        "execute_academic_search",
        lambda *args, **kwargs: external_called.append(True),
    )

    result = research_service.search("desarrollo organizacional y liderazgo", 10)

    assert queries == [
        "desarrollo organizacional y liderazgo",
        "organizational development and leadership",
    ]
    assert result["origin"] == "library"
    assert result["metadata"]["query_expanded"] is True
    assert external_called == []


def test_research_service_uses_orion_and_persists_real_results(monkeypatch, sample_paper):
    persisted = []
    monkeypatch.setattr(paper_service, "list_papers", lambda **kwargs: [])
    monkeypatch.setattr(
        research_service,
        "route_query",
        lambda query: {"domain": "academic", "manual_sources": []},
    )
    monkeypatch.setattr(
        research_service,
        "execute_academic_search",
        lambda query, max_keep: {
            "domain": "academic",
            "sources": ["OpenAlex"],
            "results": [sample_paper],
            "errors": ["provider detail must stay internal"],
            "duration_ms": 12,
        },
    )
    monkeypatch.setattr(data_store, "upsert_papers", persisted.extend)

    result = research_service.search("leadership", 10)

    assert result["origin"] == "research"
    assert result["count"] == 1
    assert result["metadata"]["error_count"] == 1
    assert "provider detail" not in str(result)
    assert persisted == [sample_paper]


def test_research_service_falls_back_to_accumulated_radar_and_manual_links(
    monkeypatch, sample_paper
):
    calls = []

    def list_papers(**kwargs):
        calls.append(kwargs.get("query"))
        if kwargs.get("query") is None:
            return [sample_paper]
        return []

    monkeypatch.setattr(paper_service, "list_papers", list_papers)
    monkeypatch.setattr(
        research_service,
        "route_query",
        lambda query: {
            "domain": "academic",
            "manual_sources": ["Google Scholar", "APA PsycNet"],
        },
    )
    monkeypatch.setattr(
        research_service,
        "execute_academic_search",
        lambda query, max_keep=None, **kwargs: {
            "domain": "academic",
            "sources": ["OpenAlex", "Crossref"],
            "results": [],
            "errors": ["rate limited"],
            "duration_ms": 15,
            "source_meta": [
                {
                    "source": "OpenAlex",
                    "status": "error",
                    "network_requests": 3,
                    "cache_hits": 0,
                    "retries": 2,
                    "rate_limited": True,
                }
            ],
        },
    )

    result = research_service.search("liderazgo emergente", 10)

    assert result["origin"] == "radar_fallback"
    assert result["results"] == [sample_paper]
    assert result["metadata"]["fallback_used"] is True
    assert result["metadata"]["fallback_reason"] == "no_direct_results"
    assert result["metadata"]["historical_search"] is True
    assert result["metadata"]["source_meta"][0]["rate_limited"] is True
    assert {link["name"] for link in result["metadata"]["manual_links"]} == {
        "Google Scholar",
        "APA PsycNet",
    }
    assert all(link["url"].startswith("https://") for link in result["metadata"]["manual_links"])


def test_research_service_routes_legal_queries_to_real_manual_sources(monkeypatch):
    monkeypatch.setattr(paper_service, "list_papers", lambda **kwargs: [])
    monkeypatch.setattr(
        research_service,
        "route_query",
        lambda query: {"domain": "legal_pr", "manual_sources": ["OSL / SUTRA"]},
    )

    result = research_service.search("Ley 80", 10)

    assert result["origin"] == "manual_sources"
    assert result["results"] == []
    assert result["metadata"]["manual_sources"] == ["OSL / SUTRA"]


def test_database_failure_is_sanitized(client, monkeypatch):
    monkeypatch.setattr(
        paper_service,
        "list_papers",
        lambda **kwargs: (_ for _ in ()).throw(
            DatabaseConnectionError("postgresql://user:secret@example.test/db")
        ),
    )

    response = client.get("/api/v1/papers")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "secret" not in response.text


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ExternalSearchError("provider secret"), 502),
        (ExternalSearchTimeout("provider secret"), 504),
        (ExternalRateLimit("provider secret"), 429),
        (RuntimeError("internal secret"), 500),
    ],
)
def test_service_failures_are_consistent_and_sanitized(
    client, monkeypatch, error, expected_status
):
    monkeypatch.setattr(
        research_service,
        "search",
        lambda query, limit: (_ for _ in ()).throw(error),
    )

    response = client.post("/api/v1/search", json={"query": "leadership"})

    assert response.status_code == expected_status
    assert "secret" not in response.text


def test_library_reads_and_updates_existing_favorites(client, sample_paper):
    data_store.upsert_papers([sample_paper])

    update = client.post(
        "/api/v1/library", json={"paper_id": sample_paper["id"], "favorite": True}
    )
    listing = client.get("/api/v1/library")

    assert update.status_code == 200
    assert update.json()["favorite"] == 1
    assert [item["id"] for item in listing.json()["items"]] == [sample_paper["id"]]


def test_library_rejects_unknown_paper(client):
    response = client.post("/api/v1/library", json={"paper_id": "missing"})
    assert response.status_code == 404


@pytest.fixture
def authenticated_api(monkeypatch, sample_paper):
    secret = "test-only-orion-key"
    monkeypatch.setenv("ORION_API_KEY", secret)
    data_store.upsert_papers([sample_paper])
    monkeypatch.setattr(
        research_service,
        "search",
        lambda query, limit: {
            "query": query,
            "origin": "library",
            "results": [sample_paper],
            "count": 1,
            "metadata": {},
        },
    )
    return TestClient(create_app(), raise_server_exceptions=False), secret, sample_paper


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/papers", None),
        ("get", "/api/v1/papers/doi:10.1234/orion", None),
        ("get", "/api/v1/radar", None),
        ("get", "/api/v1/radar/status", None),
        ("get", "/api/v1/sources", None),
        ("post", "/api/v1/search", {"query": "leadership"}),
        ("get", "/api/v1/library", None),
        (
            "post",
            "/api/v1/library",
            {"paper_id": "doi:10.1234/orion", "favorite": True},
        ),
    ],
)
def test_all_data_endpoints_reject_missing_and_incorrect_key(
    authenticated_api, method, path, payload
):
    client, secret, _ = authenticated_api

    missing = client.request(method, path, json=payload)
    incorrect = client.request(
        method,
        path,
        json=payload,
        headers={"X-Orion-API-Key": "incorrect-key"},
    )

    assert missing.status_code == 401
    assert incorrect.status_code == 401
    assert missing.json() == {"detail": "Valid API key required"}
    assert incorrect.json() == {"detail": "Valid API key required"}
    assert secret not in missing.text
    assert secret not in incorrect.text


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/papers", None),
        ("get", "/api/v1/papers/doi:10.1234/orion", None),
        ("get", "/api/v1/sources", None),
        ("post", "/api/v1/search", {"query": "leadership"}),
        ("get", "/api/v1/library", None),
        (
            "post",
            "/api/v1/library",
            {"paper_id": "doi:10.1234/orion", "favorite": True},
        ),
    ],
)
def test_all_data_endpoints_accept_correct_key(
    authenticated_api, method, path, payload
):
    client, secret, _ = authenticated_api

    response = client.request(
        method,
        path,
        json=payload,
        headers={"X-Orion-API-Key": secret},
    )

    assert response.status_code == 200
    assert secret not in response.text


@pytest.mark.parametrize(
    "path", ["/health", "/api/v1/health", "/docs", "/openapi.json"]
)
def test_health_and_api_documentation_remain_public(authenticated_api, path):
    client, secret, _ = authenticated_api

    response = client.get(path)

    assert response.status_code == 200
    assert secret not in response.text


def test_api_key_is_not_logged_or_exposed_in_openapi(authenticated_api, caplog):
    client, secret, _ = authenticated_api

    denied = client.get(
        "/api/v1/papers", headers={"X-Orion-API-Key": f"wrong-{secret}"}
    )
    schema = client.get("/openapi.json")

    assert denied.status_code == 401
    assert "X-Orion-API-Key" in schema.text
    assert secret not in schema.text
    assert secret not in denied.text
    assert secret not in caplog.text


def test_cors_defaults_and_explicit_configuration(monkeypatch):
    assert get_settings(environ={}).allowed_origins == DEFAULT_ALLOWED_ORIGINS
    settings = APISettings(
        allowed_origins=("https://site.example.test",), api_key=None
    )
    client = TestClient(create_app(settings))

    allowed = client.options(
        "/api/v1/papers",
        headers={
            "Origin": "https://site.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/v1/papers",
        headers={
            "Origin": "https://evil.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "https://site.example.test"
    assert "access-control-allow-origin" not in denied.headers
    with pytest.raises(ValueError, match="explicit origins"):
        get_settings(environ={"ORION_ALLOWED_ORIGINS": "*"})


def test_openapi_and_docs_are_available_without_secrets(client, monkeypatch):
    monkeypatch.setenv("ORION_API_KEY", "openapi-secret")
    schema = client.get("/openapi.json")
    docs = client.get("/docs")

    assert schema.status_code == 200
    assert schema.json()["info"] == {
        "title": "Orion PIO Intelligence API",
        "description": "Secure API over Orion's research and persistence services.",
        "version": "v1",
    }
    assert "/api/v1/papers/{paper_id}" in schema.json()["paths"]
    assert "X-Orion-API-Key" in schema.text
    assert docs.status_code == 200
    assert "openapi-secret" not in schema.text
