from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

import research_agent

pytestmark = pytest.mark.unit


def test_text_doi_id_and_date_normalization():
    assert research_agent.clean_text(["<b>Niñez</b>", "&amp; ética"]) == "Niñez & ética"
    assert research_agent.clean_text(None) == ""
    assert research_agent.normalize_doi(" DOI:10.1000/ABC ") == "10.1000/abc"
    assert research_agent.stable_id("Crossref", doi="10.1000/ABC") == "doi:10.1000/abc"
    assert research_agent.stable_id("Open Alex", native_id="W1") == "open_alex:W1"
    assert research_agent.stable_id("X", title="Título Único!") == "title:t-tulo-nico"
    assert research_agent.parse_date("published 2024-02-03") == "2024-02-03"
    assert research_agent.parse_date("year 2023") == "2023-01-01"
    assert research_agent.parse_date([2022, 7]) == "2022-07-01"
    assert research_agent.parse_date("2025 Mar 04") == "2025-03-04"
    assert research_agent.parse_date("2025 March") == "2025-03-01"
    assert research_agent.parse_date(["bad"]) == ""


def test_scoring_and_apa_fallback(sample_paper):
    paper = research_agent.score_record(dict(sample_paper), "psychological safety", 3650)
    assert 0 < paper["topic_relevance_percent"] <= 100
    assert paper["relevance_score"] == paper["topic_relevance_percent"] / 5
    assert "10.1234/orion" in paper["apa_citation"]
    assert research_agent.topic_relevance_percent({}, "the and") == 0


def test_deduplicate_merges_doi_title_and_provenance():
    first = {"id": "a", "title": "Same Study", "doi": "10.1/X", "abstract": "short", "discovered_via": "OpenAlex", "relevance_score": 4, "published_date": "2024-01-01"}
    second = {"id": "b", "title": "Different title", "doi": "https://doi.org/10.1/x", "abstract": "a much longer abstract", "discovered_via": "Crossref", "relevance_score": 8, "published_date": "2025-01-01", "year": 2025}
    third = {"id": "c", "title": " same study ", "doi": "", "discovered_via": "Europe PMC", "relevance_score": 1}
    merged = research_agent.deduplicate([first, second, third])
    assert len(merged) == 1
    assert merged[0]["abstract"] == "a much longer abstract"
    assert merged[0]["published_date"] == "2025-01-01"
    assert merged[0]["discovered_via"] == "OpenAlex | Crossref | Europe PMC"


def test_openalex_parser_handles_complete_and_sparse_records(monkeypatch, fake_response):
    payload = {"results": [{
        "id": "https://openalex.org/W1", "title": "<i>Leadership</i>", "publication_year": 2025,
        "publication_date": "2025-03-02", "doi": "https://doi.org/10.1/ABC", "type": "article",
        "abstract_inverted_index": {"Team": [1], "Strong": [0]},
        "authorships": [{"author": {"display_name": "Ana"}}, {}],
        "primary_location": {"landing_page_url": "https://example.test/work", "source": {"display_name": "Journal"}},
        "open_access": {"is_oa": True}, "best_oa_location": {"pdf_url": "https://example.test/a.pdf"},
        "topics": [{"display_name": "Leadership"}], "cited_by_count": 4,
    }, {"id": "W2", "title": None}]}
    monkeypatch.setattr(research_agent, "_get", lambda *a, **k: fake_response(payload))
    papers = research_agent.search_openalex("leadership", days=30, per_page=2)
    assert papers[0]["abstract"] == "Strong Team"
    assert papers[0]["doi"] == "10.1/abc"
    assert papers[0]["pdf_url"].endswith(".pdf")
    assert papers[1]["authors"] == ""


def test_openalex_optional_key_is_sent(monkeypatch, fake_response):
    captured = {}
    monkeypatch.setenv("OPENALEX_API_KEY", "openalex-test-key")

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return fake_response({"results": []})

    monkeypatch.setattr(research_agent, "_get", fake_get)
    assert research_agent.search_openalex("leadership") == []
    assert captured["params"]["api_key"] == "openalex-test-key"


def test_provider_rate_policies_and_pacing(monkeypatch):
    monkeypatch.delenv("CROSSREF_EMAIL", raising=False)
    assert research_agent.source_rate_policy("Crossref")["minimum_interval_seconds"] == 1.0
    monkeypatch.setenv("CROSSREF_EMAIL", "researcher@example.test")
    assert research_agent.source_rate_policy("Crossref")["minimum_interval_seconds"] == pytest.approx(1 / 3)
    assert research_agent.source_rate_policy("Semantic Scholar")["minimum_interval_seconds"] == 1.0
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    assert research_agent.source_rate_policy("PubMed")["minimum_interval_seconds"] == pytest.approx(1 / 3)
    monkeypatch.setenv("NCBI_API_KEY", "test-key")
    assert research_agent.source_rate_policy("PubMed")["minimum_interval_seconds"] == 0.1
    assert research_agent.source_rate_policy("arXiv")["minimum_interval_seconds"] == 3.0

    research_agent._SOURCE_NEXT_REQUEST_AT.clear()
    sleeps = []
    now = lambda: 100.0
    assert research_agent.pace_source_request("arXiv", sleep_fn=sleeps.append, clock=now) == 0
    assert research_agent.pace_source_request("arXiv", sleep_fn=sleeps.append, clock=now) == 3.0
    assert sleeps == [3.0]


def test_crossref_parser_handles_missing_fields(monkeypatch, fake_response):
    payload = {"message": {"items": [{
        "title": ["Cambio &amp; cultura"], "author": [{"given": "Zoë", "family": "Ruiz"}],
        "published": {"date-parts": [[2024, 5]]}, "container-title": ["Revista"],
        "DOI": "10.2/XYZ", "type": "journal-article", "abstract": None,
        "subject": ["Culture"], "is-referenced-by-count": 2,
    }, {"title": [], "created": {"date-time": "2023-01-02T00:00:00Z"}}]}}
    monkeypatch.setattr(research_agent, "_get", lambda *a, **k: fake_response(payload))
    papers = research_agent.search_crossref("culture", per_page=2)
    assert papers[0]["authors"] == "Zoë Ruiz"
    assert papers[0]["published_date"] == "2024-05-01"
    assert papers[1]["id"].startswith("title:")
    assert papers[1]["published_date"] == "2023-01-02"


def test_crossref_historical_window_uses_cursor_paging(monkeypatch, fake_response):
    calls = []
    payloads = [
        {
            "message": {
                "items": [
                    {
                        "title": ["Leadership at work"],
                        "DOI": "10.10/one",
                        "published": {"date-parts": [[2001, 2, 3]]},
                        "container-title": ["Journal One"],
                    }
                ],
                "next-cursor": "cursor-2",
            }
        },
        {
            "message": {
                "items": [
                    {
                        "title": ["Teams at work"],
                        "DOI": "10.10/two",
                        "published": {"date-parts": [[2001, 2, 4]]},
                        "container-title": ["Journal Two"],
                    }
                ]
            }
        },
    ]

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"].copy())
        return fake_response(payloads[len(calls) - 1])

    monkeypatch.setattr(research_agent, "_get", fake_get)
    monkeypatch.setattr(research_agent, "pace_source_request", lambda *a, **k: 0)

    papers = research_agent.search_crossref_window(
        "leadership workplace",
        research_agent.date(2001, 2, 1),
        research_agent.date(2001, 2, 28),
        max_records=2,
        page_size=1,
    )

    assert [paper["doi"] for paper in papers] == ["10.10/two", "10.10/one"] or {
        paper["doi"] for paper in papers
    } == {"10.10/one", "10.10/two"}
    assert calls[0]["cursor"] == "*"
    assert calls[1]["cursor"] == "cursor-2"
    assert "from-pub-date:2001-02-01" in calls[0]["filter"]


def test_pubmed_parser_uses_ncbi_esearch_and_esummary(monkeypatch, fake_response):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs.get("params") or {}))
        if "esearch.fcgi" in url:
            return fake_response({"esearchresult": {"idlist": ["12345"]}})
        return fake_response(
            {
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "title": "Psychological safety at work",
                        "pubdate": "2025 Mar 04",
                        "fulljournalname": "Journal of Occupational Health",
                        "authors": [{"name": "A. Rivera"}, {"name": "B. Smith"}],
                        "pubtype": ["Journal Article"],
                        "articleids": [
                            {"idtype": "pubmed", "value": "12345"},
                            {"idtype": "doi", "value": "10.1000/PUBMED"},
                        ],
                    },
                }
            }
        )

    monkeypatch.setenv("NCBI_EMAIL", "researcher@example.test")
    monkeypatch.setenv("NCBI_API_KEY", "test-key")
    monkeypatch.setattr(research_agent, "_get", fake_get)
    monkeypatch.setattr(research_agent, "pace_source_request", lambda *a, **k: 0)

    papers = research_agent.search_pubmed("psychological safety", days=365, per_page=5)

    assert len(papers) == 1
    paper = papers[0]
    assert paper["source"] == "PubMed"
    assert paper["doi"] == "10.1000/pubmed"
    assert paper["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert paper["published_date"] == "2025-03-04"
    assert "A. Rivera" in paper["authors"]
    assert calls[0][1]["api_key"] == "test-key"
    assert calls[1][1]["api_key"] == "test-key"


def test_crossref_journal_window_uses_exact_container_filter(monkeypatch, fake_response):
    captured = []

    def fake_get(url, **kwargs):
        captured.append(kwargs["params"].copy())
        return fake_response(
            {
                "message": {
                    "items": [
                        {
                            "title": ["A new construct at work"],
                            "DOI": "10.10/journal-watch",
                            "published": {"date-parts": [[2026, 8, 1]]},
                            "container-title": ["Journal of Applied Psychology"],
                            "type": "journal-article",
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(research_agent, "_get", fake_get)
    monkeypatch.setattr(research_agent, "pace_source_request", lambda *a, **k: 0)

    papers = research_agent.search_crossref_journal_window(
        "Journal of Applied Psychology",
        research_agent.date(2026, 8, 1),
        research_agent.date(2026, 8, 31),
        max_records=10,
    )

    assert len(papers) == 1
    assert papers[0]["doi"] == "10.10/journal-watch"
    assert papers[0]["discovered_via"] == "Crossref PIO journal watch"
    assert "container-title:Journal of Applied Psychology" in captured[0]["filter"]


def test_europe_pmc_parser_handles_open_access_and_empty_results(monkeypatch, fake_response):
    payload = {"resultList": {"result": [{
        "id": "1", "pmcid": "PMC1", "source": "MED", "title": "Wellbeing", "pubYear": "2025",
        "firstPublicationDate": "2025-02-01", "authorString": "A. Autor", "abstractText": "Text",
        "isOpenAccess": "Y", "journalInfo": {"journal": {"title": "Health"}}, "citedByCount": 3,
    }]}}
    monkeypatch.setattr(research_agent, "_get", lambda *a, **k: fake_response(payload))
    paper = research_agent.search_europe_pmc("wellbeing")[0]
    assert paper["pdf_url"].endswith("?pdf=render")
    monkeypatch.setattr(research_agent, "_get", lambda *a, **k: fake_response({}))
    assert research_agent.search_europe_pmc("none") == []


def test_semantic_scholar_parser_and_optional_key(monkeypatch, fake_response):
    captured = {}
    payload = {"data": [{
        "paperId": "S1", "title": "Teams", "authors": None, "year": 2024, "publicationDate": None,
        "externalIds": {}, "openAccessPdf": None, "publicationTypes": None, "fieldsOfStudy": None,
        "citationCount": None, "venue": None, "abstract": None,
    }]}
    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return fake_response(payload)
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "fake-key")
    monkeypatch.setattr(research_agent, "_get", fake_get)
    paper = research_agent.search_semantic_scholar("teams")[0]
    assert captured["headers"] == {"x-api-key": "fake-key"}
    assert paper["published_date"] == "2024-01-01"
    assert paper["authors"] == paper["abstract"] == ""


def test_arxiv_parser_uses_mock_feed_and_filters_old_records(monkeypatch, fake_response):
    recent = SimpleNamespace(
        published="2099-01-02", title="AI &amp; Work", id="https://arxiv.org/abs/1",
        authors=[SimpleNamespace(name="Ada")], summary="<p>Summary</p>",
        links=[SimpleNamespace(type="application/pdf", href="https://arxiv.org/pdf/1")],
        tags=[{"term": "cs.HC"}],
    )
    old = SimpleNamespace(published="2000-01-01", title="Old", id="old", authors=[], links=[], tags=[], summary="")
    monkeypatch.setattr(research_agent.requests, "get", lambda *a, **k: fake_response(text="feed"))
    monkeypatch.setattr(research_agent.feedparser, "parse", lambda text: SimpleNamespace(entries=[recent, old]))
    papers = research_agent.search_arxiv("AI", days=365, per_page=2)
    assert len(papers) == 1
    assert papers[0]["pdf_url"].endswith("/1")


def test_http_errors_bad_json_rate_limit_and_timeout_are_propagated(monkeypatch, fake_response):
    for error in (requests.Timeout("timeout"), requests.HTTPError("429 rate limit")):
        monkeypatch.setattr(research_agent.requests, "get", lambda *a, _error=error, **k: fake_response(error=_error))
        with pytest.raises(type(error)):
            research_agent._get("https://example.test")
    monkeypatch.setattr(research_agent, "_get", lambda *a, **k: fake_response(ValueError("bad json")))
    with pytest.raises(ValueError, match="bad json"):
        research_agent.search_openalex("query")


def test_spanish_academic_query_variants_and_relevance():
    variants = research_agent.academic_query_variants(
        "desarrollo organizacional y liderazgo"
    )
    assert variants == [
        "desarrollo organizacional y liderazgo",
        "organizational development and leadership",
    ]
    assert research_agent.academic_query_variants("leadership effectiveness") == [
        "leadership effectiveness"
    ]

    paper = {
        "title": "Psychological safety and leadership in teams",
        "topics": "psychological safety, leadership",
        "abstract": "Team psychological safety predicts learning behavior.",
    }
    assert (
        research_agent.topic_relevance_percent(
            paper, "seguridad psicológica y liderazgo"
        )
        >= 70
    )


def test_spanish_search_queries_original_and_english_variant(monkeypatch):
    calls = []

    def searcher(query, days, per_page):
        calls.append(query)
        return [
            {
                "id": f"id-{len(calls)}",
                "title": "Organizational development and leadership",
                "relevance_score": 1,
            }
        ]

    monkeypatch.setattr(research_agent, "SEARCHERS", {"OpenAlex": searcher})
    monkeypatch.setattr(research_agent.time, "sleep", lambda _: None)

    papers, errors = research_agent.search_all_sources(
        "desarrollo organizacional y liderazgo", 30, 5, ["OpenAlex"]
    )

    assert calls == [
        "desarrollo organizacional y liderazgo",
        "organizational development and leadership",
    ]
    assert errors == []
    assert papers
    assert papers[0]["matched_query"] == "desarrollo organizacional y liderazgo"


def test_search_all_sources_collects_errors_without_sleep(monkeypatch):
    def good(*args, **kwargs):
        return [{"id": "1", "title": "One", "relevance_score": 1}]
    def bad(*args, **kwargs):
        raise requests.Timeout("offline")
    monkeypatch.setattr(research_agent, "SEARCHERS", {"Good": good, "Bad": bad})
    sleeps = []
    monkeypatch.setattr(research_agent.time, "sleep", sleeps.append)
    papers, errors = research_agent.search_all_sources("q", 5, 2, ["Good", "Unknown", "Bad"])
    assert len(papers) == 1
    assert errors == ["Bad: Timeout: offline"]
    assert sleeps == []


def test_ai_helpers_without_secret_and_with_fake_client(monkeypatch, sample_paper):
    assert research_agent.get_client() is None
    assert research_agent.ai_text("hello").startswith("Configura OPENAI_API_KEY")
    analysis = research_agent.analyze_paper(sample_paper)
    assert analysis["summary"].startswith("Evidencia")

    response = SimpleNamespace(output_text=' {"summary": "ok"} ')
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setattr(research_agent, "get_client", lambda: client)
    assert research_agent.ai_text("hello") == '{"summary": "ok"}'
    assert research_agent._json_from_ai("prompt") == {"summary": "ok"}
    monkeypatch.setattr(research_agent, "ai_text", lambda *a, **k: "not-json")
    assert research_agent._json_from_ai("prompt") == {"summary": "not-json"}


def test_library_trends_and_source_links(sample_paper):
    context = research_agent.build_library_context([sample_paper])
    assert sample_paper["title"] in context
    assert research_agent.build_library_context([]) == ""
    trends = dict(research_agent.extract_trends([sample_paper]))
    assert trends["liderazgo"] >= 1
    links = dict(research_agent.source_search_links("seguridad psicológica"))
    assert "seguridad%20psicol%C3%B3gica" in links["Google Scholar"]
