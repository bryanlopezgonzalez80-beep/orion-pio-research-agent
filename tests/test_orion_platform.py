from __future__ import annotations

import pytest
import requests

import orion_platform
import platform_store
from orion_platform import SOURCE_SPECS, all_topics, classify_query, execute_academic_search, recommended_academic_sources, route_query, source_search_url

pytestmark = pytest.mark.integration

def test_topic_catalog_is_broad():
    topics=all_topics()
    assert len(topics)>=60
    assert len(set(topics))==len(topics)

def test_query_router():
    assert classify_query("Ley 80 despido injustificado Puerto Rico")=="legal_pr"
    assert classify_query("Title VII EEOC federal law")=="legal_us"
    assert classify_query("international law treaty ICJ")=="legal_intl"
    assert classify_query("psychological safety leadership")=="academic"

def test_routes_have_sources():
    for domain in ["academic","legal_pr","legal_us","legal_intl"]:
        plan=route_query("leadership" if domain=="academic" else "law",domain)
        assert plan["automated_sources"] or plan["manual_sources"]

def test_source_catalog_urls_are_https():
    names=[s.name for s in SOURCE_SPECS]
    assert len(names)==len(set(names))
    for s in SOURCE_SPECS:
        if s.official_url: assert s.official_url.startswith("https://")
        if s.login_url: assert s.login_url.startswith("https://")

def test_legal_search_link_contains_query():
    assert "artificial" in source_search_url("Congress.gov","artificial intelligence").lower()

def test_cache_round_trip(tmp_path,monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH",str(tmp_path/"test.db"))
    platform_store.set_cache("OpenAlex","leadership",30,5,[{"id":"1"}],ttl_hours=1)
    assert platform_store.get_cache("OpenAlex","leadership",30,5)==[{"id":"1"}]

def test_circuit_breaker(tmp_path,monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH",str(tmp_path/"test.db"))
    for _ in range(3): platform_store.record_source_failure("Synthetic","boom",threshold=3)
    assert platform_store.source_available("Synthetic") is False
    platform_store.record_source_success("Synthetic")
    assert platform_store.source_available("Synthetic") is True

def test_rate_limit_retry_respects_retry_after(tmp_path, monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH", str(tmp_path / "test.db"))
    calls = {"n": 0}
    sleeps = []

    def rate_limited_then_ok(query, days, per_page):
        calls["n"] += 1
        if calls["n"] == 1:
            response = requests.Response()
            response.status_code = 429
            response.headers["Retry-After"] = "1.5"
            raise requests.HTTPError("rate limited", response=response)
        return [{"id": "ok", "title": "Recovered", "published_date": "2026-09-01", "relevance_score": 8}]

    out = execute_academic_search(
        "leadership",
        sources=["OpenAlex"],
        searchers={"OpenAlex": rate_limited_then_ok},
        retries=1,
        sleep_fn=sleeps.append,
        force_refresh=True,
    )

    assert calls["n"] == 2
    assert sleeps == [1.5]
    assert out["unique"] == 1
    assert out["errors"] == []


def test_rate_limit_retry_uses_bounded_backoff_without_header():
    response = requests.Response()
    response.status_code = 429
    exc = requests.HTTPError("rate limited", response=response)

    assert orion_platform._rate_limit_delay(exc, 0) == 0.75
    assert orion_platform._rate_limit_delay(exc, 8) == 8.0
    assert orion_platform._rate_limit_delay(RuntimeError("other"), 0) is None


def test_retry_and_deduplicate(tmp_path,monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH",str(tmp_path/"test.db"))
    calls={"n":0}
    def flaky(query,days,per_page):
        calls["n"]+=1
        if calls["n"]==1: raise RuntimeError("temporary")
        return [
          {"id":"x","title":"Same","published_date":"2026-09-01","relevance_score":10},
          {"id":"x","title":"Same","published_date":"2026-09-01","relevance_score":10},
        ]
    out=execute_academic_search("leadership",sources=["OpenAlex"],searchers={"OpenAlex":flaky},retries=1,sleep_fn=lambda _:None,force_refresh=True)
    assert calls["n"]==2
    assert out["unique"]==1
    assert out["errors"]==[]

def test_cache_hit_skips_network(tmp_path,monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH",str(tmp_path/"test.db"))
    platform_store.set_cache("OpenAlex","cached topic",30,5,[{"id":"cached","title":"Cached","published_date":"2026-09-01","relevance_score":9}],ttl_hours=1)
    calls={"n":0}
    def should_not_run(query,days,per_page):
        calls["n"]+=1
        raise AssertionError("network should not run")
    out=execute_academic_search("cached topic",days=30,per_source=5,sources=["OpenAlex"],searchers={"OpenAlex":should_not_run},retries=0,sleep_fn=lambda _:None)
    assert calls["n"]==0
    assert out["unique"]==1
    assert out["source_meta"][0]["cached"] is True

def test_partial_failure_keeps_successes(tmp_path,monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH",str(tmp_path/"test.db"))
    def good(query,days,per_page):
        return [{"id":"good","title":"Useful","published_date":"2026-09-01","relevance_score":8}]
    def bad(query,days,per_page):
        raise RuntimeError("provider down")
    out=execute_academic_search("leadership",sources=["OpenAlex","Crossref"],searchers={"OpenAlex":good,"Crossref":bad},retries=0,sleep_fn=lambda _:None,force_refresh=True)
    assert out["unique"]==1
    assert len(out["errors"])==1
    assert {m["status"] for m in out["source_meta"]}=={"ok","error"}

def test_spanish_queries():
    assert classify_query("jurisprudencia y reglamento de Puerto Rico")=="legal_pr"
    assert classify_query("desarrollo organizacional y liderazgo")=="academic"

def test_alert_is_due(tmp_path,monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH",str(tmp_path/"test.db"))
    aid=platform_store.create_alert("Daily leadership","leadership","academic",["OpenAlex"],"daily")
    assert any(a["id"]==aid for a in platform_store.alerts_due())


def test_spanish_academic_search_expands_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH", str(tmp_path / "test.db"))
    calls = []

    def bilingual_searcher(query, days, per_page):
        calls.append(query)
        return [
            {
                "id": "same-paper",
                "title": "Organizational development and leadership",
                "published_date": "2026-09-01",
                "relevance_score": 1,
            }
        ]

    out = execute_academic_search(
        "desarrollo organizacional y liderazgo",
        sources=["OpenAlex"],
        searchers={"OpenAlex": bilingual_searcher},
        retries=0,
        sleep_fn=lambda _: None,
        force_refresh=True,
    )

    assert calls == [
        "desarrollo organizacional y liderazgo",
        "organizational development and leadership",
    ]
    assert out["query_expanded"] is True
    assert out["query_variants"] == calls
    assert out["unique"] == 1
    assert out["results"][0]["matched_query"] == "desarrollo organizacional y liderazgo"
    assert out["source_meta"][0]["network_requests"] == 2
    assert out["source_meta"][0]["cache_hits"] == 0
    assert out["source_meta"][0]["minimum_interval_seconds"] == 0.0
    assert out["source_meta"][0]["rate_limited"] is False


def test_health_topics_route_to_pubmed_and_europe_pmc():
    sources = recommended_academic_sources("employee burnout and occupational stress")
    assert "PubMed" in sources
    assert "Europe PMC" in sources


def test_academic_route_exposes_trusted_complementary_sources():
    plan = route_query("leadership effectiveness", "academic")
    assert {"Google Scholar", "APA PsycNet", "SIOP", "SSRN"} <= set(
        plan["manual_sources"]
    )
    assert {"Academy of Management", "DOAJ"} <= set(plan["manual_sources"])
    for source in plan["manual_sources"]:
        assert source_search_url(source, "leadership").startswith("https://")


def test_semantic_scholar_default_requires_key(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    assert "Semantic Scholar" not in recommended_academic_sources("leadership effectiveness")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "test-key")
    assert "Semantic Scholar" in recommended_academic_sources("leadership effectiveness")


def test_ambiguous_and_bilingual_routing_stays_conservative():
    assert classify_query("organizational justice and employee voice") == "academic"
    assert classify_query("clima laboral y desarrollo organizacional") == "academic"
    assert classify_query("employment law and workplace policy") == "legal_general"
    assert classify_query("Ley 100 discriminación") == "legal_pr"
    assert classify_query("ADA federal court accommodation") == "legal_us"
    assert classify_query("derecho internacional y tratado") == "legal_intl"
    assert route_query("employment law")["automated_sources"] == []


def test_unavailable_source_is_reported_without_calling_network(tmp_path, monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH", str(tmp_path / "test.db"))
    out = execute_academic_search(
        "leadership", sources=["Missing"], searchers={}, retries=0,
        sleep_fn=lambda _: None, force_refresh=True,
    )
    assert out["results"] == []
    meta = out["source_meta"][0]
    assert meta["source"] == "Missing"
    assert meta["status"] == "unavailable"
    assert meta["count"] == 0
    assert meta["cached"] is False
    assert meta["network_requests"] == 0
    assert meta["cache_hits"] == 0
    assert meta["retries"] == 0
    assert meta["rate_limited"] is False


def test_open_circuit_skips_searcher(tmp_path, monkeypatch):
    monkeypatch.setenv("ORION_DB_PATH", str(tmp_path / "test.db"))
    called = []
    monkeypatch.setattr(orion_platform, "source_available", lambda source: False)
    out = execute_academic_search(
        "leadership", sources=["OpenAlex"],
        searchers={"OpenAlex": lambda *a, **k: called.append(True)},
        retries=0, sleep_fn=lambda _: None, force_refresh=True,
    )
    assert called == []
    assert out["source_meta"][0]["status"] == "circuit_open"


def test_source_configuration_reports_only_configured_credentials(monkeypatch):
    monkeypatch.setenv("CROSSREF_EMAIL", "test@example.test")
    rows = {row["name"]: row for row in orion_platform.source_configuration()}
    assert rows["Crossref"]["credential_configured"] is True
    assert rows["Semantic Scholar"]["credential_configured"] is False
