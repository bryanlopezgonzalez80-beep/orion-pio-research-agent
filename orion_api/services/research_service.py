from __future__ import annotations

from typing import Any

import data_store
from orion_platform import execute_academic_search, route_query, source_search_url
from research_agent import academic_query_variants

from . import paper_service


def search(query: str, limit: int) -> dict[str, Any]:
    query_variants = academic_query_variants(query) or [query]
    plan = route_query(query)
    manual_sources = list(plan.get("manual_sources") or [])
    manual_links = [
        {"name": source, "url": source_search_url(source, query)}
        for source in manual_sources
    ]

    existing_by_id: dict[str, dict] = {}
    for variant in query_variants:
        for paper in paper_service.list_papers(limit=limit, offset=0, query=variant):
            existing_by_id.setdefault(paper["id"], paper)
            if len(existing_by_id) >= limit:
                break
        if len(existing_by_id) >= limit:
            break
    existing = list(existing_by_id.values())[:limit]
    if existing:
        return {
            "query": query,
            "origin": "library",
            "results": existing,
            "count": len(existing),
            "metadata": {
                "external_search": False,
                "query_expanded": len(query_variants) > 1,
                "query_variants": query_variants,
                "manual_sources": manual_sources,
                "manual_links": manual_links,
                "fallback_used": False,
            },
        }

    if plan["domain"] != "academic":
        return {
            "query": query,
            "origin": "manual_sources",
            "results": [],
            "count": 0,
            "metadata": {
                "domain": plan["domain"],
                "external_search": False,
                "manual_sources": manual_sources,
                "manual_links": manual_links,
                "fallback_used": False,
            },
        }

    outcome = execute_academic_search(query, max_keep=limit)
    results = outcome["results"][:limit]
    if results:
        data_store.upsert_papers(results)
        return {
            "query": query,
            "origin": "research",
            "results": results,
            "count": len(results),
            "metadata": {
                "domain": outcome["domain"],
                "sources": outcome["sources"],
                "source_meta": outcome.get("source_meta", []),
                "error_count": len(outcome["errors"]),
                "duration_ms": outcome["duration_ms"],
                "external_search": True,
                "query_expanded": bool(outcome.get("query_expanded")),
                "query_variants": outcome.get("query_variants", [query]),
                "manual_sources": manual_sources,
                "manual_links": manual_links,
                "fallback_used": False,
            },
        }

    # A live provider miss must not leave Radar visually empty when Orion
    # already has a persisted research library. These are explicitly marked
    # as accumulated Radar fallback rather than query matches.
    fallback = paper_service.list_papers(limit=limit, offset=0)
    return {
        "query": query,
        "origin": "radar_fallback" if fallback else "research",
        "results": fallback,
        "count": len(fallback),
        "metadata": {
            "domain": outcome["domain"],
            "sources": outcome["sources"],
            "source_meta": outcome.get("source_meta", []),
            "error_count": len(outcome["errors"]),
            "duration_ms": outcome["duration_ms"],
            "external_search": True,
            "query_expanded": bool(outcome.get("query_expanded")),
            "query_variants": outcome.get("query_variants", [query]),
            "manual_sources": manual_sources,
            "manual_links": manual_links,
            "fallback_used": bool(fallback),
            "fallback_reason": "no_direct_results" if fallback else "no_results_available",
        },
    }

