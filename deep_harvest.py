"""High-recall PIO discovery and historical backfill for Orion.

The goal is maximum practical coverage across official/open scholarly APIs while
respecting provider limits. This cannot index literally every page on the web or
licensed databases that do not expose a permitted API.
"""
from __future__ import annotations

import os
import random
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from data_store import db_stats, evidence_observability, upsert_papers
from source_registry import public_source_registry
from geographic_intelligence import geography_status, run_geographic_booster
from orion_platform import TOPIC_GROUPS, execute_academic_search, route_query, source_search_url
from platform_store import checkpoint_summary, enrichment_summary, get_checkpoint, get_setting, get_source_metrics, set_checkpoint, set_setting
from research_agent import (
    deduplicate,
    search_crossref_journal_window,
    search_crossref_window,
)

STATE_PREFIX = "deep_harvest"
BACKFILL_FLOOR_YEAR = int(os.getenv("ORION_BACKFILL_FLOOR_YEAR", "1900"))

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

EXPANSION_QUERIES = [
    "organizational psychology",
    "occupational psychology",
    "work psychology",
    "organizational behavior",
    "human resource management",
    "transactional leadership",
    "destructive leadership",
    "resistance to change",
    "organization development intervention",
    "organizational transformation",
    "change management workplace",
    "organizational learning",
    "organizational innovation",
    "psychological climate workplace",
    "procedural justice workplace",
    "speak up behavior workplace",
    "ethical climate organization",
    "innovation climate workplace",
    "team performance workplace",
    "team diversity performance",
    "team learning",
    "collaboration workplace",
    "knowledge sharing workplace",
    "personnel selection",
    "structured employment interview",
    "assessment center employee selection",
    "cognitive ability job performance",
    "personality job performance",
    "employee turnover",
    "onboarding employee",
    "job performance",
    "performance appraisal",
    "goal setting workplace",
    "work motivation",
    "self determination work",
    "job satisfaction",
    "organizational commitment",
    "learning transfer workplace",
    "employee development",
    "leadership training",
    "coaching workplace",
    "mentoring workplace",
    "career adaptability",
    "continuous learning workplace",
    "occupational fatigue",
    "psychosocial safety climate",
    "diversity inclusion workplace",
    "belonging workplace",
    "workplace discrimination",
    "gender bias workplace",
    "racial bias workplace",
    "age discrimination workplace",
    "disability inclusion workplace",
    "sexual harassment workplace",
    "employee ethics behavior",
    "corporate social responsibility employees",
    "artificial intelligence human resources workplace",
    "AI hiring employee selection",
    "employee monitoring technology",
    "human AI collaboration workplace",
    "automation jobs workplace",
    "digital transformation employees",
    "remote work employees",
    "hybrid work employees",
    "flexible work arrangements",
    "telework employee outcomes",
    "gig work psychology",
    "shift work employee outcomes",
    "four day workweek employees",
    "return to office employees",
    "occupational safety behavior",
    "safety climate workplace",
    "human factors work performance",
    "ergonomics employee performance",
    "human error workplace",
    "safety leadership workplace",
    "workplace Puerto Rico employees organizational",
    "psicología industrial organizacional Puerto Rico",
    "desarrollo organizacional Puerto Rico",
    "liderazgo empleados Puerto Rico",
    "recursos humanos América Latina",
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
    "work psychology Europe",
    "work psychology Asia Pacific",
    "organizational psychology Africa",
    "organizational behavior Middle East",
    "work psychology Australia New Zealand",
    "workplace psychology international employees",
    "psicología industrial organizacional",
    "psicología del trabajo organizaciones",
    "psicologia organizacional trabalho",
    "psychologie du travail organisation",
    "Arbeits und Organisationspsychologie",
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


# Exact Crossref container-title watch. This captures new papers from central
# work/organizational journals even when their titles use novel terminology
# that does not match Orion's concept queries.
PIO_JOURNALS = [
    "Journal of Applied Psychology",
    "Personnel Psychology",
    "Journal of Organizational Behavior",
    "Organizational Behavior and Human Decision Processes",
    "Human Relations",
    "Journal of Management",
    "The Leadership Quarterly",
    "Human Resource Management",
    "Applied Psychology",
    "Work & Stress",
    "Journal of Occupational Health Psychology",
    "European Journal of Work and Organizational Psychology",
    "Industrial and Organizational Psychology",
    "International Journal of Selection and Assessment",
    "Organizational Research Methods",
    "Academy of Management Journal",
    "Academy of Management Review",
    "Journal of Business and Psychology",
    "Journal of Vocational Behavior",
    "Journal of Occupational and Organizational Psychology",
    "Human Performance",
    "Group & Organization Management",
    "Occupational Health Science",
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
    # Puerto Rico psychology topics have their own rotating geographic booster.
    # Keeping them out of the global contract prevents a catalogue expansion
    # from turning every refresh into hundreds of additional provider calls.
    global_topic_groups = (
        topics for name, topics in TOPIC_GROUPS.items()
        if name not in {
            "Psicología y sociedad en Puerto Rico",
            "Práctica psicológica en Puerto Rico",
        }
    )
    for query in UMBRELLA_QUERIES + [
        topic for topics in global_topic_groups for topic in topics
    ] + EXPANSION_QUERIES + GEOGRAPHIC_QUERIES:
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
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """Sweep the full PIO taxonomy and persist results incrementally."""
    queries = coverage_queries()
    started_at = _utcnow()
    started = time.monotonic()

    # Keep the live catalog fair even if a provider slowdown causes the runtime
    # budget to expire. The next run resumes from the next unprocessed query
    # instead of repeatedly starving the tail of the taxonomy.
    live_rotation = int(get_setting(f"{STATE_PREFIX}.live_rotation", 0) or 0)
    if queries:
        live_rotation %= len(queries)
        ordered_queries = queries[live_rotation:] + queries[:live_rotation]
    else:
        live_rotation = 0
        ordered_queries = []

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
    taxonomy_budget_seconds = max_runtime_seconds * 0.80
    received = 0
    unique_seen: dict[str, dict] = {}
    stopped_for_budget = False

    def emit_progress(phase: str = "taxonomy") -> None:
        if progress_callback is None:
            return
        payload = {
            "phase": phase,
            "queries_processed": processed,
            "queries_total": len(queries),
            "queries_remaining": max(0, len(queries) - processed),
            "received": received,
            "unique_seen": len(unique_seen),
            "source_totals": {
                name: dict(values) for name, values in source_totals.items()
            },
            "journal_watch_processed": 0,
            "journal_watch_total": len(PIO_JOURNALS),
        }
        try:
            progress_callback(payload)
        except Exception:
            # Progress reporting must never abort academic harvesting.
            pass

    emit_progress("taxonomy")

    for query in ordered_queries:
        if time.monotonic() - started >= taxonomy_budget_seconds:
            stopped_for_budget = True
            break
        sources = _live_sources(query, openalex_queries)
        emit_progress("query_started")
        try:
            outcome = execute_academic_search(
                query,
                days=days,
                per_source=per_source,
                sources=sources,
                max_keep=max(100, per_source * len(sources)),
                retries=1,
                cache_ttl_hours=4,
                force_refresh=True,
                progress_callback=lambda event, current=query: progress_callback({
                    "phase": event.get("phase") or "source",
                    "current_query": current,
                    "current_source": event.get("source") or "",
                    "queries_processed": processed,
                    "queries_total": len(queries),
                    "queries_remaining": max(0, len(queries) - processed),
                    "received": received,
                    "unique_seen": len(unique_seen),
                    "source_totals": {name: dict(values) for name, values in source_totals.items()},
                }) if progress_callback is not None else None,
            )
        except Exception as exc:
            errors.append(f"{query}: {type(exc).__name__}: {exc}")
            processed += 1
            emit_progress("taxonomy")
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
        emit_progress("taxonomy")

    journal_watch_received = 0
    journal_watch_unique = 0
    journal_watch_processed = 0
    journal_start = date.today() - timedelta(days=days)
    journal_rotation = int(get_setting(f"{STATE_PREFIX}.journal_rotation", 0) or 0)
    if PIO_JOURNALS:
        journal_rotation %= len(PIO_JOURNALS)
        ordered_journals = (
            PIO_JOURNALS[journal_rotation:] + PIO_JOURNALS[:journal_rotation]
        )
    else:
        journal_rotation = 0
        ordered_journals = []

    if time.monotonic() - started < max_runtime_seconds:
        journal_batch: list[dict] = []
        for journal in ordered_journals:
            if time.monotonic() - started >= max_runtime_seconds:
                stopped_for_budget = True
                break
            try:
                papers = None
                for attempt in range(3):
                    try:
                        papers = search_crossref_journal_window(
                            journal,
                            journal_start,
                            date.today(),
                            max_records=250,
                            page_size=200,
                        )
                        break
                    except Exception as exc:
                        delay = _backfill_retry_delay(exc, attempt)
                        if delay is None or attempt >= 2:
                            raise
                        time.sleep(delay)
                papers = papers or []
                journal_watch_received += len(papers)
                journal_batch.extend(papers)
            except Exception as exc:
                errors.append(
                    f"journal watch {journal}: {type(exc).__name__}: {exc}"
                )
            finally:
                journal_watch_processed += 1
                if progress_callback is not None:
                    try:
                        progress_callback(
                            {
                                "phase": "journals",
                                "queries_processed": processed,
                                "queries_total": len(queries),
                                "queries_remaining": max(0, len(queries) - processed),
                                "received": received + journal_watch_received,
                                "unique_seen": len(unique_seen),
                                "source_totals": {
                                    name: dict(values)
                                    for name, values in source_totals.items()
                                },
                                "journal_watch_processed": journal_watch_processed,
                                "journal_watch_total": len(PIO_JOURNALS),
                            }
                        )
                    except Exception:
                        pass
        journal_unique = deduplicate(journal_batch)
        if journal_unique:
            upsert_papers(journal_unique)
            before = len(unique_seen)
            for paper in journal_unique:
                paper_id = str(paper.get("id") or "")
                if paper_id:
                    unique_seen[paper_id] = paper
            journal_watch_unique = len(unique_seen) - before

    next_journal_rotation = (
        (journal_rotation + journal_watch_processed) % len(PIO_JOURNALS)
        if PIO_JOURNALS
        else 0
    )
    set_setting(f"{STATE_PREFIX}.journal_rotation", next_journal_rotation)

    if not os.getenv("OPENALEX_API_KEY"):
        set_setting(f"{STATE_PREFIX}.openalex_rotation", next_rotation)

    next_live_rotation = (
        (live_rotation + processed) % len(queries)
        if queries
        else 0
    )
    set_setting(f"{STATE_PREFIX}.live_rotation", next_live_rotation)

    result = {
        "mode": "live_sweep",
        "started_at": started_at.isoformat(timespec="seconds"),
        "completed_at": _utcnow().isoformat(timespec="seconds"),
        "queries_total": len(queries),
        "queries_processed": processed,
        "queries_remaining": max(0, len(queries) - processed),
        "query_rotation_start": live_rotation,
        "next_query_rotation": next_live_rotation,
        "received": received + journal_watch_received,
        "unique_seen": len(unique_seen),
        "errors": errors,
        "stopped_for_runtime_budget": stopped_for_budget,
        "openalex_queries_this_run": len(openalex_queries),
        "journal_watch_count": len(PIO_JOURNALS),
        "journal_watch_processed": journal_watch_processed,
        "journal_rotation_start": journal_rotation,
        "next_journal_rotation": next_journal_rotation,
        "journal_watch_received": journal_watch_received,
        "journal_watch_unique": journal_watch_unique,
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


def _backfill_retry_delay(exc: Exception, attempt: int) -> float | None:
    """Return a bounded delay for Crossref 429 and transient 5xx responses."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code != 429 and not (
        isinstance(status_code, int) and 500 <= status_code <= 599
    ):
        return None
    raw = (getattr(response, "headers", None) or {}).get("Retry-After")
    if raw:
        try:
            return min(30.0, max(0.0, float(raw)))
        except (TypeError, ValueError):
            pass
    base = 1.0 if status_code == 429 else 2.0
    return min(20.0, base * (2 ** max(0, attempt)) + random.random() * 0.25)


def _is_rate_limited(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    detail = str(exc).casefold()
    return "429" in detail or "rate limit" in detail


def run_historical_backfill(
    *,
    months_per_run: int | None = None,
    records_per_query_month: int = 500,
    progress_callback: Callable[[dict], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict:
    """Backfill older Crossref literature in resumable month-sized windows."""
    months = max(
        0,
        int(
            months_per_run
            if months_per_run is not None
                else os.getenv(
                    "ORION_BACKFILL_TARGET_MONTHS_PER_RUN",
                    os.getenv("ORION_BACKFILL_MONTHS_PER_RUN", "12"),
                )
        ),
    )
    cursor = _parse_cursor(get_setting(f"{STATE_PREFIX}.backfill_cursor"))
    errors: list[str] = []
    windows: list[dict] = []
    total_received = 0
    unique_ids: set[str] = set()
    run_tasks_completed = 0

    for _ in range(months):
        month_end = cursor - timedelta(days=1)
        month_start = month_end.replace(day=1)
        if month_start.year < BACKFILL_FLOOR_YEAR:
            break

        month_results: list[dict] = []
        month_errors: list[str] = []
        tasks = [
            ("query", query, search_crossref_window, records_per_query_month)
            for query in BACKFILL_QUERIES
        ] + [
            ("journal", journal, search_crossref_journal_window, 250)
            for journal in PIO_JOURNALS
        ]
        month_key = month_start.isoformat()
        completed_tasks = 0
        for task_type, task_key, _fetch, _max_records in tasks:
            if get_checkpoint(month_key, "Crossref", task_type, task_key) is None:
                set_checkpoint(month_key, "Crossref", task_type, task_key, "PENDING")
        for task_type, task_key, fetch, max_records in tasks:
            checkpoint = get_checkpoint(month_key, "Crossref", task_type, task_key)
            if checkpoint and checkpoint.get("status") == "COMPLETED":
                completed_tasks += 1
                run_tasks_completed += 1
                continue
            set_checkpoint(month_key, "Crossref", task_type, task_key, "RUNNING")
            try:
                papers = None
                for attempt in range(3):
                    try:
                        papers = fetch(
                            task_key,
                            month_start,
                            month_end,
                            max_records=max_records,
                            page_size=200,
                        )
                        break
                    except Exception as exc:
                        delay = _backfill_retry_delay(exc, attempt)
                        if delay is None or attempt >= 2:
                            raise
                        sleep_fn(delay)
                papers = papers or []
                month_results.extend(papers)
                if papers:
                    unique_task = deduplicate(papers)
                    upsert_papers(unique_task)
                    unique_ids.update(str(p.get("id") or "") for p in unique_task if p.get("id"))
                set_checkpoint(
                    month_key, "Crossref", task_type, task_key, "COMPLETED",
                    records_received=len(papers),
                )
                completed_tasks += 1
                run_tasks_completed += 1
            except Exception as exc:
                safe_detail = str(exc)[:200]
                msg = f"{task_type} {task_key}: {type(exc).__name__}: {safe_detail}"
                month_errors.append(msg)
                errors.append(f"{month_start.isoformat()}: {msg}")
                rate_limited = _is_rate_limited(exc)
                set_checkpoint(
                    month_key, "Crossref", task_type, task_key,
                    "RATE_LIMITED" if rate_limited else "FAILED_RETRYABLE",
                    error=type(exc).__name__,
                )
                if rate_limited:
                    # Crossref stress is provider-wide. Leave remaining tasks
                    # PENDING for the next run instead of amplifying a 429.
                    if progress_callback is not None:
                        progress_callback({
                            "phase": "backfill", "backfill_month": month_key,
                            "backfill_tasks_completed": completed_tasks,
                            "backfill_tasks_total": len(tasks),
                            "backfill_month_tasks_completed": completed_tasks,
                            "backfill_month_tasks_total": len(tasks),
                            "backfill_tasks_completed_total": run_tasks_completed,
                            "backfill_rate_limited": True,
                        })
                    break
            if progress_callback is not None:
                progress_callback({
                    "phase": "backfill", "backfill_month": month_key,
                    "backfill_tasks_completed": completed_tasks,
                    "backfill_tasks_total": len(tasks),
                    "backfill_month_tasks_completed": completed_tasks,
                    "backfill_month_tasks_total": len(tasks),
                    "backfill_tasks_completed_total": run_tasks_completed,
                    "backfill_records_received": len(month_results),
                })

        unique = deduplicate(month_results)
        if unique:
            unique_ids.update(str(p.get("id") or "") for p in unique if p.get("id"))
        total_received += len(month_results)
        windows.append(
            {
                "start": month_start.isoformat(),
                "end": month_end.isoformat(),
                "received": len(month_results),
                "unique": len(unique),
                "errors": len(month_errors),
                "tasks_total": len(tasks),
                "tasks_completed": completed_tasks,
            }
        )

        # Do not skip a historical window after a transient provider failure.
        # Successful records are already persisted, so retrying the same month
        # on the next run is safe and improves completeness.
        if completed_tasks < len(tasks):
            break
        cursor = month_start
        set_setting(f"{STATE_PREFIX}.backfill_cursor", cursor.isoformat())

    result = {
        "mode": "historical_backfill",
        "floor_year": BACKFILL_FLOOR_YEAR,
        "journal_watch_count": len(PIO_JOURNALS),
        "next_cursor": cursor.isoformat(),
        "months_processed": len(windows),
        "received": total_received,
        "unique_seen": len(unique_ids),
        "windows": windows,
        "errors": errors,
        "checkpoint_summary": checkpoint_summary(),
    }
    set_setting(f"{STATE_PREFIX}.last_backfill", result)
    return result


def run_deep_harvest(
    *,
    include_backfill: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    progress_state: dict = {}
    monotonic_fields = {
        "queries_processed", "queries_total", "received", "unique_seen",
        "journal_watch_processed", "journal_watch_total",
        "geo_queries_processed", "geo_queries_total",
        "backfill_tasks_completed_total", "backfill_records_received",
    }

    def cumulative_progress(snapshot: dict) -> None:
        if progress_callback is None:
            return
        previous_month = progress_state.get("backfill_month")
        incoming_month = snapshot.get("backfill_month")
        if incoming_month and incoming_month != previous_month:
            for key in (
                "backfill_tasks_completed", "backfill_tasks_total",
                "backfill_month_tasks_completed", "backfill_month_tasks_total",
            ):
                progress_state.pop(key, None)
        for key, value in snapshot.items():
            if key in monotonic_fields:
                progress_state[key] = max(int(progress_state.get(key) or 0), int(value or 0))
            elif isinstance(value, dict) and isinstance(progress_state.get(key), dict):
                progress_state[key] = {**progress_state[key], **value}
            else:
                progress_state[key] = value
        progress_callback(dict(progress_state))

    corpus_before = int(db_stats().get("papers") or 0)
    configured_live_runtime = os.getenv("ORION_LIVE_SWEEP_RUNTIME_SECONDS")
    live_kwargs = {"progress_callback": cumulative_progress}
    if configured_live_runtime:
        live_kwargs["max_runtime_seconds"] = int(configured_live_runtime)
    live = run_live_sweep(**live_kwargs)
    geography = run_geographic_booster(progress_callback=cumulative_progress)
    backfill = run_historical_backfill(progress_callback=cumulative_progress) if include_backfill else None
    corpus_after = int(db_stats().get("papers") or 0)
    warnings = (
        len(live.get("errors") or []) + len(geography.get("errors") or [])
        + len((backfill or {}).get("errors") or [])
    )
    result = {
        "completed_at": _utcnow().isoformat(timespec="seconds"),
        "coverage_query_count": len(coverage_queries()),
        "journal_watch_count": len(PIO_JOURNALS),
        "live": live,
        "geography": geography,
        "backfill": backfill,
        "status": "COMPLETED_WITH_WARNINGS" if warnings else "COMPLETED",
        "total_papers_persisted": corpus_after,
        "new_papers_this_run": max(0, corpus_after - corpus_before),
        "records_received_this_run": int(live.get("received") or 0) + int(geography.get("received") or 0) + int((backfill or {}).get("received") or 0),
        "unique_seen_this_run": int(live.get("unique_seen") or 0) + int(geography.get("unique_seen") or 0) + int((backfill or {}).get("unique_seen") or 0),
    }
    set_setting(f"{STATE_PREFIX}.last_run", result)
    return result


def harvest_status() -> dict:
    facets = evidence_observability()
    last_run = get_setting(f"{STATE_PREFIX}.last_run") or {}
    last_backfill = get_setting(f"{STATE_PREFIX}.last_backfill") or {}
    checkpoints = checkpoint_summary()
    checkpoint_totals: dict[str, int] = Counter()
    completed_months: set[str] = set()
    months_with_pending: set[str] = set()
    for item in checkpoints:
        status = str(item.get("status") or "")
        checkpoint_totals[status] += int(item.get("total") or 0)
        if status == "COMPLETED":
            completed_months.add(str(item.get("month") or ""))
        else:
            months_with_pending.add(str(item.get("month") or ""))
    oldest_completed = min(completed_months - months_with_pending, default=None)
    provider_health = get_source_metrics()
    provider_registry = public_source_registry()
    provider_lifecycle = {
        field: sum(1 for provider in provider_registry if provider.get(field) is True)
        for field in ("registered", "implemented", "configured", "authorized", "active")
    }
    enrichment = enrichment_summary()
    run_metrics = {
        "new_papers_this_run": int(last_run.get("new_papers_this_run") or 0),
        "records_received_this_run": int(last_run.get("records_received_this_run") or 0),
        "unique_seen_this_run": int(last_run.get("unique_seen_this_run") or 0),
    }
    return {
        "coverage_query_count": len(coverage_queries()),
        "last_run": last_run or None,
        "last_live_sweep": get_setting(f"{STATE_PREFIX}.last_live_sweep"),
        "last_backfill": last_backfill or None,
        "backfill_cursor": get_setting(f"{STATE_PREFIX}.backfill_cursor"),
        "openalex_key_configured": bool(os.getenv("OPENALEX_API_KEY")),
        "semantic_scholar_key_configured": bool(os.getenv("SEMANTIC_SCHOLAR_API_KEY")),
        "geography": geography_status(),
        "corpus": {
            "total_papers": facets["total_papers"],
            "total_papers_persisted": facets["total_papers"],
            "new_this_run": run_metrics["new_papers_this_run"],
        },
        "run": run_metrics,
        "geography_summary": {key: facets[key] for key in ("puerto_rico", "united_states", "latam_caribbean", "global_or_unknown")},
        "historical": {
            "floor_year": BACKFILL_FLOOR_YEAR,
            "current_month": last_backfill.get("next_cursor") or get_setting(f"{STATE_PREFIX}.backfill_cursor"),
            "oldest_completed_month": oldest_completed,
            "target_months_per_run": int(os.getenv("ORION_BACKFILL_TARGET_MONTHS_PER_RUN", "12")),
            "months_completed_this_run": int(last_backfill.get("months_processed") or 0),
            "tasks_completed": checkpoint_totals.get("COMPLETED", 0),
            "tasks_pending": sum(checkpoint_totals.get(value, 0) for value in ("PENDING", "RUNNING", "RATE_LIMITED", "FAILED_RETRYABLE")),
            "estimated_months_remaining": None,
        },
        "evidence": {key: facets[key] for key in ("peer_reviewed", "preprints", "systematic_reviews", "meta_analyses", "retracted")},
        "access": {key: facets[key] for key in ("open_access", "institutional_access", "provider_login", "metadata_only", "requires_login")},
        "enrichment": enrichment,
        "citation_graph": {"papers_discovered": int(get_setting(f"{STATE_PREFIX}.citation_papers_discovered", 0) or 0)},
        "historical_target_months": int(os.getenv("ORION_BACKFILL_TARGET_MONTHS_PER_RUN", "12")),
        "checkpoints": checkpoints,
        "provider_registry": provider_registry,
        "provider_health": provider_health,
        "providers": {
            "health": provider_health,
            "registry": provider_registry,
            **provider_lifecycle,
        },
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
