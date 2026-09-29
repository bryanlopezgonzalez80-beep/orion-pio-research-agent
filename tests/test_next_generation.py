from __future__ import annotations

import json

import pytest

import access_resolver
import citation_graph
import evidence_integrity
import evidence_pipeline
import source_registry
import data_store
from platform_store import checkpoint_summary, get_checkpoint, get_source_metrics, record_source_metrics, set_checkpoint

pytestmark = pytest.mark.integration


def test_registry_describes_open_and_disabled_premium_sources(monkeypatch):
    monkeypatch.delenv("PSYCINFO_API_ENABLED", raising=False)
    registry = source_registry.source_registry()
    assert {"crossref", "openalex", "pubmed", "europe_pmc", "core", "doaj", "datacite", "eric", "arxiv"} <= set(registry)
    assert source_registry.SourceType.CITATION_GRAPH in registry["openalex"].source_type
    assert registry["arxiv"].peer_review_information_available is False
    assert registry["psycinfo"].discovery_enabled is False
    assert registry["psycinfo"].health_status == source_registry.SourceHealth.INACTIVE
    assert "API_KEY" not in json.dumps(source_registry.public_source_registry())


def test_premium_provider_requires_both_enablement_and_configuration(monkeypatch):
    monkeypatch.setenv("SCOPUS_API_ENABLED", "true")
    monkeypatch.delenv("SCOPUS_API_KEY", raising=False)
    assert source_registry.source_registry()["scopus"].health_status == source_registry.SourceHealth.AUTH_REQUIRED
    monkeypatch.setenv("SCOPUS_API_KEY", "test-placeholder")
    assert source_registry.source_registry()["scopus"].discovery_enabled is True


@pytest.mark.parametrize(
    ("paper", "expected"),
    [
        ({"oa_url": "https://repository.example/paper", "title": "x"}, "OPEN_ACCESS"),
        ({"licensed_providers": ["Scopus"], "provider_url": "https://example.test", "title": "x"}, "PROVIDER_LOGIN"),
        ({"url": "https://publisher.example/x", "title": "x"}, "PUBLISHER_ACCESS"),
        ({"doi": "10.1000/test", "title": "x"}, "DOI_ONLY"),
        ({"title": "metadata"}, "METADATA_ONLY"),
        ({}, "UNKNOWN"),
    ],
)
def test_access_resolution_order(paper, expected):
    result = access_resolver.resolve_access(paper)
    assert result["access_status"] == expected
    assert result["access_status"] in access_resolver.ACCESS_STATUSES


def test_access_resolver_requires_confirmed_pdf_and_supports_openurl():
    result = access_resolver.resolve_access(
        {"doi": "https://doi.org/10.1000/ABC", "pdf_url": "https://x.test/file.pdf", "title": "x"},
        institution={"enabled": True, "institution_name": "University", "openurl_base": "https://resolver.test/openurl"},
    )
    assert result["access_status"] == "INSTITUTIONAL_ACCESS"
    assert result["pdf_available"] is False
    assert result["requires_login"] is True
    assert "10.1000%2Fabc" in result["best_access_url"]


def test_access_resolver_rejects_unsafe_urls():
    result = access_resolver.resolve_access({"title": "x", "oa_url": "javascript:alert(1)"})
    assert result["access_status"] == "METADATA_ONLY"


def test_integrity_does_not_treat_doi_as_peer_review_proof():
    result = evidence_integrity.assess_integrity({"doi": "10.1/x", "title": "Article"})
    assert result["peer_review_status"] == "UNKNOWN"
    assert result["doi_verified"] is False


def test_integrity_marks_preprint_and_preserves_retraction():
    result = evidence_integrity.assess_integrity({
        "source": "arXiv", "title": "A preprint", "retraction_status": "RETRACTED"
    })
    assert result["peer_review_status"] == "NOT_PEER_REVIEWED"
    assert "RETRACTED" in result["evidence_flags"]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("A meta-analysis of leadership", "META_ANALYSIS"),
        ("Systematic review of teams", "SYSTEMATIC_REVIEW"),
        ("A randomized controlled trial", "RANDOMIZED_TRIAL"),
        ("Longitudinal employee study", "LONGITUDINAL"),
        ("Cross-sectional survey", "CROSS_SECTIONAL"),
        ("Conceptual paper", "THEORETICAL"),
        ("Unspecified evidence", "UNKNOWN"),
    ],
)
def test_evidence_type_is_conservative(title, expected):
    assert evidence_integrity.classify_evidence_type({"title": title}) == expected


def test_canonical_identity_prefers_doi_and_normalizes_it():
    assert evidence_pipeline.canonical_key({"doi": "HTTPS://DOI.ORG/10.1000/ABC."}) == "doi:10.1000/abc"


def test_canonical_identity_falls_back_conservatively():
    first = evidence_pipeline.canonical_key({"title": "Título", "authors": "Pérez", "year": 2020})
    second = evidence_pipeline.canonical_key({"title": "Titulo", "authors": "Pérez", "year": 2020})
    assert first == second
    assert first.startswith("metadata:")


def test_multi_source_merge_retains_richest_metadata_and_provenance():
    merged = evidence_pipeline.merge_records([
        {"id": "one", "doi": "10.1/a", "title": "Paper", "abstract": "short", "source": "Crossref"},
        {"id": "two", "doi": "https://doi.org/10.1/A", "title": "Paper", "abstract": "a much richer abstract", "source": "OpenAlex", "openalex_id": "W1"},
    ])
    assert len(merged) == 1
    assert merged[0]["abstract"] == "a much richer abstract"
    assert merged[0]["metadata_sources_count"] == 2
    assert merged[0]["paper_external_ids"]["openalex"] == "W1"
    assert merged[0]["metadata_provenance"]["abstract"] == ["Crossref", "OpenAlex"]


def test_enrichment_keeps_affiliation_separate_from_study_location():
    enriched = evidence_pipeline.enrich_record({
        "id": "x", "title": "Workers in Puerto Rico", "author_affiliation_location": "United States",
        "source": "Crossref",
    })
    assert enriched["study_location"] != "United States"
    assert enriched["geo_pr"] == 1
    assert enriched["access_status"] == "METADATA_ONLY"


def test_citation_graph_enforces_depth_nodes_and_relevance():
    seed = {"id": "seed", "title": "Systematic review", "relevance_score": 1}
    def fetch(paper):
        return [{"id": f"{paper['id']}-a", "title": "Related", "relevance_score": 1}]
    result = citation_graph.build_citation_graph([seed], {"OpenAlex": fetch}, max_depth=4, max_nodes=3)
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2


def test_citation_provider_failure_is_isolated():
    def broken(_paper):
        raise RuntimeError("provider down")
    result = citation_graph.build_citation_graph(
        [{"id": "seed", "title": "Meta-analysis", "relevance_score": 1}],
        {"OpenAlex": broken, "Semantic Scholar": lambda paper: []},
    )
    assert len(result["nodes"]) == 1
    assert result["errors"] == [{"provider": "OpenAlex", "error": "RuntimeError"}]


def test_checkpoint_state_is_granular_and_resumable():
    set_checkpoint("2026-08-01", "Crossref", "query", "leadership", "RUNNING")
    set_checkpoint("2026-08-01", "Crossref", "query", "leadership", "COMPLETED", records_received=7)
    row = get_checkpoint("2026-08-01", "Crossref", "query", "leadership")
    assert row["status"] == "COMPLETED"
    assert row["attempts"] == 2
    assert row["records_received"] == 7
    assert checkpoint_summary()[0]["total"] == 1


def test_checkpoint_rejects_unknown_state():
    with pytest.raises(ValueError, match="Unsupported checkpoint"):
        set_checkpoint("2026-08-01", "Crossref", "query", "x", "BOGUS")


def test_additive_paper_filters_are_parameterized(sample_paper):
    data_store.upsert_papers([
        {**sample_paper, "id": "open", "peer_review_status": "CONFIRMED", "oa_url": "https://oa.test/paper", "fulltext_available": True, "evidence_type": "SYSTEMATIC_REVIEW"},
        {**sample_paper, "id": "retracted", "doi": "10.1/retracted", "retraction_status": "RETRACTED"},
    ])
    assert [p["id"] for p in data_store.list_papers(peer_reviewed=True)] == ["open"]
    assert [p["id"] for p in data_store.list_papers(open_access=True)] == ["open"]
    assert [p["id"] for p in data_store.list_papers(full_text=True)] == ["open"]
    assert [p["id"] for p in data_store.list_papers(evidence_type="SYSTEMATIC_REVIEW")] == ["open"]
    assert [p["id"] for p in data_store.list_papers(retracted=True)] == ["retracted"]


def test_observability_stats_distinguish_corpus_facets(sample_paper):
    data_store.upsert_papers([{**sample_paper, "title": "Liderazgo en Puerto Rico", "doi_verified": True, "metadata_sources_count": 2}])
    stats = data_store.db_stats()
    assert stats["papers"] == stats["puerto_rico"] == 1
    assert stats["with_abstract"] == stats["with_doi"] == 1
    assert stats["multi_source_metadata"] == 1


def test_source_metrics_accumulate_without_overwriting_history():
    record_source_metrics("Crossref", requests=2, successes=1, records_received=5, unique_records=4, latency_ms=20)
    record_source_metrics("Crossref", requests=1, failures=1, rate_limits=1, health_status="RATE_LIMITED", latency_ms=50)
    metric = get_source_metrics()[0]
    assert metric["requests"] == 3
    assert metric["successes"] == metric["failures"] == metric["rate_limits"] == 1
    assert metric["records_received"] == 5
    assert metric["last_success"] and metric["last_failure"]
    assert metric["health_status"] == "RATE_LIMITED"
