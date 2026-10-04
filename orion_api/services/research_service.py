from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import data_store
from orion_platform import ACADEMIC_AUTOMATED, execute_academic_search, route_query, source_search_url
from research_agent import academic_query_variants, deduplicate, score_record

from . import paper_service

RESULT_FLOOR = 100
RESULT_CAP = 500
DEFAULT_DAYS = 60


def _execute_search(query: str, **kwargs: Any) -> dict[str, Any]:
    try:
        return execute_academic_search(query, **kwargs)
    except TypeError as exc:
        # Preserve compatibility with lightweight test doubles and older adapters
        # that only accepted (query, max_keep).
        if "unexpected keyword argument" not in str(exc):
            raise
        return execute_academic_search(query, max_keep=kwargs.get("max_keep"))

    
def _run_query(query: str, *, days: int, per_source: int, sources: list[str] | None, max_keep: int) -> dict[str, Any] | None:
    return _execute_search(
        query,
        days=days,
        per_source=per_source,
        sources=sources,
        max_keep=max_keep,
        retries=1,
        cache_ttl_hours=24,
    )


def _parallel_search(queries: list[str], *, days: int, per_source: int, sources: list[str] | None, max_keep: int) -> list[dict[str, Any] | None]:
    if len(queries) <= 1:
        return [_run_query(queries[0], days=days, per_source=per_source, sources=sources, max_keep=max_keep)] if queries else []
    workers = min(len(queries), 3)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="orion-search") as pool:
        futures = [pool.submit(_run_query, query, days=days, per_source=per_source, sources=sources, max_keep=max_keep) for query in queries]
        return [future.result() for future in futures]


def _merge_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = [outcome for outcome in outcomes if outcome]
    results = deduplicate(
        paper
        for outcome in outcomes
        for paper in outcome.get("results", [])
    )
    return {
        "results": results,
        "domain": outcomes[0].get("domain", "academic") if outcomes else "academic",
        "sources": sorted({source for outcome in outcomes for source in outcome.get("sources", [])}),
        "source_meta": [
            item for outcome in outcomes for item in outcome.get("source_meta", [])
        ],
        "errors": [error for outcome in outcomes for error in outcome.get("errors", [])],
        "duration_ms": sum(int(outcome.get("duration_ms") or 0) for outcome in outcomes),
        "query_expanded": any(outcome.get("query_expanded") for outcome in outcomes),
        "query_variants": [
            variant for outcome in outcomes for variant in outcome.get("query_variants", [])
        ],
    }


def search(
    query: str,
    limit: int,
    *,
    days: int = DEFAULT_DAYS,
    per_source: int = 25,
    sources: list[str] | None = None,
    include_pr: bool = False,
) -> dict[str, Any]:
    # The UI's page-size value must not silently collapse a broad search to six
    # records. Keep an intentionally wide result window while retaining a hard cap.
    effective_limit = min(max(int(limit), RESULT_FLOOR), RESULT_CAP)
    query_variants = academic_query_variants(query) or [query]
    plan = route_query(query)
    selected = list(sources or plan.get("automated_sources") or [])
    automated_sources = [source for source in selected if source in ACADEMIC_AUTOMATED]
    manual_sources = [source for source in plan.get("manual_sources") or [] if source not in selected]
    unavailable_selected = [source for source in selected if source not in ACADEMIC_AUTOMATED]
    manual_sources.extend(unavailable_selected)

    pr_query = f"{query} Puerto Rico puertorriqueño boricua" if include_pr else None
    search_queries = [query]
    if pr_query and pr_query.casefold() != query.casefold():
        search_queries.append(pr_query)
    if include_pr:
        for source in (
            "Universidad de Puerto Rico",
            "UPR Biblioteca",
            "Centro de Investigaciones Sociales UPR",
            "Asociación de Psicología de Puerto Rico",
            "Departamento de Psicología UPR",
        ):
            if source not in manual_sources:
                manual_sources.append(source)

    manual_links = [
        {"name": source, "url": source_search_url(source, query)}
        for source in manual_sources
    ]

    existing_by_id: dict[str, dict] = {}
    for variant in query_variants:
        for paper in paper_service.list_papers(limit=effective_limit, offset=0, query=variant):
            existing_by_id.setdefault(paper["id"], paper)
    existing = [
        score_record(dict(paper), query, days)
        for paper in list(existing_by_id.values())[:effective_limit]
    ]

    # Preserve the lightweight library behavior for legacy callers that did not
    # request broad search controls; API requests use the explicit 20-year default.
    if existing and days == DEFAULT_DAYS and per_source == 25 and sources is None and not include_pr:
        return {
            "query": query,
            "origin": "library",
            "results": existing,
            "count": len(existing),
            "metadata": {"external_search": False, "query_expanded": len(query_variants) > 1, "query_variants": query_variants, "manual_sources": manual_sources, "manual_links": manual_links, "fallback_used": False},
        }

    if plan["domain"] != "academic":
        return {
            "query": query,
            "origin": "library" if existing else "manual_sources",
            "results": existing,
            "count": len(existing),
            "metadata": {
                "domain": plan["domain"],
                "external_search": False,
                "manual_sources": manual_sources,
                "manual_links": manual_links,
                "fallback_used": False,
            },
        }

    outcomes = _parallel_search(
        search_queries,
        days=days,
        per_source=per_source,
        sources=automated_sources or None,
        max_keep=effective_limit,
    )
    outcome = _merge_outcomes(outcomes)
    external_results = outcome["results"]

    if not external_results and days < 46_000:
        historical = _parallel_search(
            search_queries,
            days=46_000,
            per_source=per_source,
            sources=automated_sources or None,
            max_keep=effective_limit,
        )
        outcome = _merge_outcomes(historical)
        external_results = outcome["results"]

    results = deduplicate([*existing, *external_results])[:effective_limit]
    fallback = []
    if not results:
        fallback = paper_service.list_papers(limit=effective_limit, offset=0)
        results = fallback[:effective_limit]
    if results:
        data_store.upsert_papers(results)
    origin = "research" if external_results else ("library" if existing else "radar_fallback")
    metadata = {
        "domain": outcome["domain"],
        "sources": outcome["sources"],
        "source_meta": outcome["source_meta"],
        "error_count": len(outcome["errors"]),
        "duration_ms": outcome["duration_ms"],
        "external_search": True,
        "historical_search": bool(not external_results and days < 46_000),
        "query_expanded": len(search_queries) > 1 or outcome["query_expanded"],
        "query_variants": outcome["query_variants"] or search_queries,
        "manual_sources": manual_sources,
        "manual_links": manual_links,
        "selected_sources": selected,
        "automated_sources": automated_sources,
        "unavailable_selected_sources": unavailable_selected,
        "include_pr": include_pr,
        "pr_complement_used": bool(pr_query),
        "requested_limit": int(limit),
        "effective_limit": effective_limit,
        "days": days,
        "per_source": per_source,
        "fallback_used": bool(fallback),
        "fallback_reason": "no_direct_results" if fallback else None,
    }
    return {
        "query": query,
        "origin": origin,
        "results": results,
        "count": len(results),
        "metadata": metadata,
    }
