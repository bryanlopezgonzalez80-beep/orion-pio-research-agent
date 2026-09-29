from __future__ import annotations

import os
from collections import Counter
from datetime import date
from typing import Iterable

from coverage_catalog import COVERAGE_TOPICS, CoverageTopic
from data_store import upsert_papers
from orion_platform import execute_academic_search
from platform_store import create_coverage_run, update_coverage_run
from research_agent import deduplicate


DEFAULT_RECENT_DAYS = 4
DEFAULT_PER_SOURCE = 40
OPENALEX_DAILY_QUERY_BUDGET_NO_KEY = 40
OPENALEX_DAILY_QUERY_BUDGET_WITH_KEY = 100
ARXIV_DAILY_QUERY_BUDGET = 16
EUROPE_PMC_DAILY_QUERY_BUDGET = 28
SEMANTIC_DAILY_QUERY_BUDGET = 60


def _source_plan(topic: CoverageTopic, counters: Counter) -> list[str]:
    sources = ["Crossref"]

    openalex_budget = (
        OPENALEX_DAILY_QUERY_BUDGET_WITH_KEY
        if os.getenv("OPENALEX_API_KEY")
        else OPENALEX_DAILY_QUERY_BUDGET_NO_KEY
    )
    if counters["OpenAlex"] < openalex_budget and topic.priority <= 2:
        sources.append("OpenAlex")

    if os.getenv("SEMANTIC_SCHOLAR_API_KEY") and counters["Semantic Scholar"] < SEMANTIC_DAILY_QUERY_BUDGET:
        sources.append("Semantic Scholar")

    if topic.biomedical and counters["Europe PMC"] < EUROPE_PMC_DAILY_QUERY_BUDGET:
        sources.append("Europe PMC")

    if topic.technology and counters["arXiv"] < ARXIV_DAILY_QUERY_BUDGET:
        sources.append("arXiv")

    return sources


def _safe_unique(papers: Iterable[dict]) -> list[dict]:
    # Remove obviously unusable metadata without imposing a high topical
    # threshold that could hide niche but legitimate I-O work.
    usable = []
    for paper in papers:
        if not (paper.get("title") or "").strip():
            continue
        if not any((paper.get("doi"), paper.get("url"), paper.get("oa_url"), paper.get("pdf_url"))):
            continue
        usable.append(paper)
    return deduplicate(usable)


def run_comprehensive_refresh(
    *,
    trigger: str = "scheduled",
    days: int = DEFAULT_RECENT_DAYS,
    per_source: int = DEFAULT_PER_SOURCE,
    topics: Iterable[CoverageTopic] | None = None,
) -> dict:
    selected = list(topics or COVERAGE_TOPICS)
    run_id = create_coverage_run(trigger, len(selected))
    source_requests = Counter()
    source_results = Counter()
    domain_results = Counter()
    errors: list[str] = []
    all_results: list[dict] = []
    processed_ids: set[str] = set()
    completed = 0

    try:
        for topic in selected:
            sources = _source_plan(topic, source_requests)
            for source in sources:
                source_requests[source] += 1

            outcome = execute_academic_search(
                topic.query,
                days=days,
                per_source=per_source,
                sources=sources,
                max_keep=max(100, per_source * max(1, len(sources))),
                retries=2,
                cache_ttl_hours=4,
                force_refresh=True,
            )
            all_results.extend(outcome["results"])
            domain_results[topic.domain] += len(outcome["results"])
            for meta in outcome.get("source_meta", []):
                source_results[meta.get("source") or "unknown"] += int(meta.get("count") or 0)
            errors.extend(f"{topic.query}: {err}" for err in outcome.get("errors", []))
            completed += 1

            # Persist in chunks so a later provider failure cannot erase work
            # already harvested during this run.
            if len(all_results) >= 500:
                unique_chunk = _safe_unique(all_results)
                upsert_papers(unique_chunk)
                processed_ids.update(str(p.get("id") or "") for p in unique_chunk if p.get("id"))
                all_results.clear()

            if completed % 10 == 0 or completed == len(selected):
                update_coverage_run(
                    run_id,
                    topics_completed=completed,
                    results_seen=sum(source_results.values()),
                    source_counts=dict(source_results),
                    domain_counts=dict(domain_results),
                    errors=errors[-100:],
                )

        final_unique = _safe_unique(all_results)
        upsert_papers(final_unique)
        processed_ids.update(str(p.get("id") or "") for p in final_unique if p.get("id"))
        total_unique = len(processed_ids)
        update_coverage_run(
            run_id,
            status="success" if not errors else "success_with_warnings",
            topics_completed=completed,
            results_seen=sum(source_results.values()),
            unique_processed=total_unique,
            source_counts=dict(source_results),
            domain_counts=dict(domain_results),
            errors=errors[-200:],
            completed=True,
        )
        return {
            "run_id": run_id,
            "date": date.today().isoformat(),
            "trigger": trigger,
            "status": "success" if not errors else "success_with_warnings",
            "topics_total": len(selected),
            "topics_completed": completed,
            "source_query_counts": dict(source_requests),
            "source_result_counts": dict(source_results),
            "domain_result_counts": dict(domain_results),
            "results_seen": sum(source_results.values()),
            "final_batch_unique": total_unique,
            "error_count": len(errors),
            "errors": errors,
        }
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        # Preserve any final in-memory work even if the run aborts.
        partial_unique = _safe_unique(all_results)
        if partial_unique:
            upsert_papers(partial_unique)
            processed_ids.update(str(p.get("id") or "") for p in partial_unique if p.get("id"))
        update_coverage_run(
            run_id,
            status="failed",
            topics_completed=completed,
            results_seen=sum(source_results.values()),
            unique_processed=len(processed_ids),
            source_counts=dict(source_results),
            domain_counts=dict(domain_results),
            errors=errors[-200:],
            completed=True,
        )
        raise
