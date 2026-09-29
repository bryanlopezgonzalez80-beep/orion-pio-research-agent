"""High-recall PIO discovery and historical backfill for Orion.

The goal is maximum practical coverage across official/open scholarly APIs while
respecting provider limits. This cannot index literally every page on the web or
licensed databases that do not expose a permitted API.
"""
from __future__ import annotations

import os
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from data_store import upsert_papers
from orion_platform import TOPIC_GROUPS, execute_academic_search, route_query, source_search_url
from platform_store import get_setting, set_setting
from research_agent import deduplicate, search_crossref_window

STATE_PREFIX = "deep_harvest"
BACKFILL_FLOOR_YEAR = int(os.getenv("ORION_BACKFILL_FLOOR_YEAR", "1950"))

# Broad anchors catch work that uses neighboring terminology instead of a
# canonical I-O Psychology label. TOPIC_GROUPS contributes the detailed layer.
UMBRELLA_QUERIES = [
    "industrial organizational psychology",
    "industrial and organizational psychology",
    "work psychology employees",
    "occupational psychology workplace",
    "organizational behavior employees",
    "human resource management employees",
    "personnel psychology",
    "work motivation job attitudes",
    "leadership workplace employees",
    "teams workplace performance",
    "training development employees",
    "employee selection assessment",
    "performance management employees",
    "organizational development change",
    "organizational culture climate",
    "employee wellbeing occupational stress",
    "future of work human resources",
]

GEOGRAPHIC_QUERIES = [
    "industrial organizational psychology Puerto Rico",
    "organizational psychology Puerto Rico",
    "recursos humanos Puerto Rico empleados",
    "liderazgo Puerto Rico organizaciones",
    "work psychology Caribbean",
    "organizational psychology Latin America",
    "psicología organizacional América Latina",
    "industrial organizational psychology United States",
    "workplace psychology international employees",
]

# Historical Crossref backfill uses fewer, broader anchors and cursor paging.
BACKFILL_QUERIES = [
    "industrial organizational psychology",
    "work psychology employees",
    "organizational behavior employees",
    "human resource management employees",
    "leadership workplace",
    "training development employees",
    "employee selection assessment",
    "organizational development change",
    "employee wellbeing occupational stress",
    "teams workplace performance",
]

TECH_HINTS = (
    "ai ", "artificial intelligence", "algorithm", "automation", "digital",
    "analytics", "future of work", "human ai", "information systems",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def coverage_queries() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for query in UMBRELLA_QUERIES + [
        topic for topics in TOPIC_GROUPS.values() for topic in topics
    ] + GEOGRAPHIC_QUERIES:
        cleaned = " ".join(str(query).split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def _rotating_subset(items: list[str], start: int, count: int) -> tuple[list[str], int]:
    if not items or count <= 0:
        return [], 0
    n = len(items)
    count = min(count, n)
    selected = [items[(start + i) % n] for i in range(count)]
    return selected, (start + count) % n


def _live_sources(query: str, openalex_queries: set[str]) -> list[str]:
    # Crossref + PubMed + Europe PMC are swept for every taxonomy query.
    # This intentionally favors recall; DOI/native-ID dedupe keeps storage sane.
    sources = ["Crossref", "PubMed", "Europe PMC"]
    if query in openalex_queries:
        sources.append("OpenAlex")
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
        sources.append("Semantic Scholar")
    q = query.casefold()
    if any(hint in q for hint in TECH_HINTS):
        sources.append("arXiv")
    return list(dict.fromkeys(sources))


def _aggregate_source_meta(total: dict[str, Counter], source_meta: list[dict]) -> None:
    for meta in source_meta:
        source = str(meta.get("source") or "unknown")
        bucket = total.setdefault(source, Counter())
        bucket["queries"] += 1
        bucket["results"] += int(meta.get("count") or 0)
        bucket["network_requests"] += int(meta.get("network_requests") or 0)
        bucket["cache_hits"] += int(meta.get("cache_hits") or 0)
        bucket["retries"] += int(meta.get("retries") or 0)
        if meta.get("rate_limited"):
            bucket["rate_limited_queries"] += 1
        if meta.get("status") == "error":
            bucket["errors"] += 1
        if meta.get("status") == "circuit_open":
            bucket["circuits_open"] += 1


def run_live_sweep(
    *,
    days: int = 45,
    per_source: int = 25,
    max_runtime_seconds: int = 20 * 60,
) -> dict:
    """Sweep the full PIO taxonomy and persist results incrementally."""
    queries = coverage_queries()
    started_at = _utcnow()
    started = time.monotonic()

    # Anonymous OpenAlex usage has a much smaller daily budget. Without a key,
    # rotate a bounded share of topics while Crossref/PubMed/Europe PMC still
    # sweep the entire taxonomy every run.
    if os.getenv("OPENALEX_API_KEY"):
        openalex_queries = set(queries)
        next_rotation = 0
    else:
        rotation = int(get_setting(f"{STATE_PREFIX}.openalex_rotation", 0) or 0)
        budget = max(0, int(os.getenv("ORION_OPENALEX_QUERIES_PER_RUN", "12")))
        selected, next_rotation = _rotating_subset(queries, rotation, budget)
        openalex_queries = set(selected)

    errors: list[str] = []
    source_totals: dict[str, Counter] = {}
    processed = 0
    received = 0
    unique_seen: dict[str, dict] = {}
    stopped_for_budget = False

    for query in queries:
        if time.monotonic() - started >= max_runtime_seconds:
            stopped_for_budget = True
            break
        sources = _live_sources(query, openalex_queries)
        try:
            outcome = execute_academic_search(
                query,
                days=days,
                per_source=per_source,
                sources=sources,
                max_keep=max(100, per_source * len(sources)),
                retries=2,
                cache_ttl_hours=4,
                force_refresh=True,
            )
        except Exception as exc:
            errors.append(f"{query}: {type(exc).__name__}: {exc}")
            processed += 1
            continue

        processed += 1
        received += int(outcome.get("received") or 0)
        _aggregate_source_meta(source_totals, outcome.get("source_meta") or [])
        errors.extend(f"{query}: {err}" for err in outcome.get("errors") or [])

        # Persist after each query: a late-source failure cannot discard earlier work.
        papers = outcome.get("results") or []
        if papers:
            upsert_papers(papers)
            for paper in papers:
                paper_id = str(paper.get("id") or "")
                if paper_id:
                    unique_seen[paper_id] = paper

    if not os.getenv("OPENALEX_API_KEY"):
        set_setting(f"{STATE_PREFIX}.openalex_rotation", next_rotation)

    result = {
        "mode": "live_sweep",
        "started_at": started_at.isoformat(timespec="seconds"),
        "completed_at": _utcnow().isoformat(timespec="seconds"),
        "queries_total": len(queries),
        "queries_processed": processed,
        "queries_remaining": max(0, len(queries) - processed),
        "received": received,
        "unique_seen": len(unique_seen),
        "errors": errors,
        "stopped_for_runtime_budget": stopped_for_budget,
        "openalex_queries_this_run": len(openalex_queries),
        "source_totals": {name: dict(values) for name, values in source_totals.items()},
        "secondary_sources": list(
            route_query("industrial organizational psychology", "academic")["manual_sources"]
        ),
    }
    set_setting(f"{STATE_PREFIX}.last_live_sweep", result)
    return result


def _parse_cursor(value) -> date:
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
            return parsed.replace(day=1)
        except Exception:
            pass
    return date.today().replace(day=1)


def run_historical_backfill(
    *,
    months_per_run: int | None = None,
    records_per_query_month: int = 500,
) -> dict:
    """Backfill older Crossref literature in resumable month-sized windows."""
    months = max(
        0,
        int(
            months_per_run
            if months_per_run is not None
            else os.getenv("ORION_BACKFILL_MONTHS_PER_RUN", "4")
        ),
    )
    cursor = _parse_cursor(get_setting(f"{STATE_PREFIX}.backfill_cursor"))
    errors: list[str] = []
    windows: list[dict] = []
    total_received = 0
    unique_ids: set[str] = set()

    for _ in range(months):
        month_end = cursor - timedelta(days=1)
        month_start = month_end.replace(day=1)
        if month_start.year < BACKFILL_FLOOR_YEAR:
            break

        month_results: list[dict] = []
        month_errors: list[str] = []
        for query in BACKFILL_QUERIES:
            try:
                papers = search_crossref_window(
                    query,
                    month_start,
                    month_end,
                    max_records=records_per_query_month,
                    page_size=200,
                )
                month_results.extend(papers)
            except Exception as exc:
                msg = f"{query}: {type(exc).__name__}: {exc}"
                month_errors.append(msg)
                errors.append(f"{month_start.isoformat()}: {msg}")

        unique = deduplicate(month_results)
        if unique:
            upsert_papers(unique)
            unique_ids.update(str(p.get("id") or "") for p in unique if p.get("id"))
        total_received += len(month_results)
        windows.append(
            {
                "start": month_start.isoformat(),
                "end": month_end.isoformat(),
                "received": len(month_results),
                "unique": len(unique),
                "errors": len(month_errors),
            }
        )

        # Advance only after the month has been fully attempted and persisted.
        cursor = month_start
        set_setting(f"{STATE_PREFIX}.backfill_cursor", cursor.isoformat())

    result = {
        "mode": "historical_backfill",
        "floor_year": BACKFILL_FLOOR_YEAR,
        "next_cursor": cursor.isoformat(),
        "months_processed": len(windows),
        "received": total_received,
        "unique_seen": len(unique_ids),
        "windows": windows,
        "errors": errors,
    }
    set_setting(f"{STATE_PREFIX}.last_backfill", result)
    return result


def run_deep_harvest(*, include_backfill: bool = True) -> dict:
    live = run_live_sweep()
    backfill = run_historical_backfill() if include_backfill else None
    result = {
        "completed_at": _utcnow().isoformat(timespec="seconds"),
        "coverage_query_count": len(coverage_queries()),
        "live": live,
        "backfill": backfill,
    }
    set_setting(f"{STATE_PREFIX}.last_run", result)
    return result


def harvest_status() -> dict:
    return {
        "coverage_query_count": len(coverage_queries()),
        "last_run": get_setting(f"{STATE_PREFIX}.last_run"),
        "last_live_sweep": get_setting(f"{STATE_PREFIX}.last_live_sweep"),
        "last_backfill": get_setting(f"{STATE_PREFIX}.last_backfill"),
        "backfill_cursor": get_setting(f"{STATE_PREFIX}.backfill_cursor"),
        "openalex_key_configured": bool(os.getenv("OPENALEX_API_KEY")),
        "semantic_scholar_key_configured": bool(os.getenv("SEMANTIC_SCHOLAR_API_KEY")),
        "secondary_sources": [
            {
                "name": name,
                "url": source_search_url(name, "industrial organizational psychology"),
            }
            for name in route_query(
                "industrial organizational psychology", "academic"
            )["manual_sources"]
        ],
    }
