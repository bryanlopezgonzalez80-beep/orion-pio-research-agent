from __future__ import annotations

import platform_store
from orion_platform import SOURCE_SPECS, all_topics, classify_query, execute_academic_search, route_query, source_search_url

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
