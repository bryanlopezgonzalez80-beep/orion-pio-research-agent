"""Daily Radar at 06:00 Puerto Rico; the full cloud sweep runs separately."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from data_store import log_radar_run, upsert_papers, verify_database_backend
from deep_harvest import coverage_queries, run_deep_harvest
from harvest_coordinator import heartbeat_harvest
from orion_platform import execute_academic_search, route_query
from platform_store import alerts_due, mark_alert_run
from research_agent import DEFAULT_SOURCES

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

# Kept as a compact compatibility list for tests and explicit alert behavior.
CORE_TOPICS = [
    "leadership effectiveness",
    "employee engagement",
    "organizational development",
    "psychological safety workplace",
    "training transfer",
    "workplace wellbeing",
    "team effectiveness",
    "AI human resources workplace",
]


def _run(query, sources=None):
    return execute_academic_search(
        query,
        days=45,
        per_source=12,
        sources=sources,
        max_keep=180,
        retries=2,
        cache_ttl_hours=4,
        force_refresh=True,
    )


def core_daily_sweep():
    summaries = []
    received = 0
    seen = set()
    errors = []
    for query in CORE_TOPICS:
        heartbeat_harvest()
        try:
            outcome = _run(query)
        except Exception as exc:
            errors.append(query + ": " + type(exc).__name__)
            summaries.append(query)
            continue
        papers = outcome.get("results") or []
        if papers:
            upsert_papers(papers)
            seen.update(str(p.get("id")) for p in papers if p.get("id"))
        received += int(outcome.get("received") or 0)
        errors.extend(query + ": " + str(error) for error in outcome.get("errors") or [])
        summaries.append(query)
    return {
        "coverage_query_count": len(CORE_TOPICS),
        "live": {
            "queries_processed": len(summaries), "queries_total": len(CORE_TOPICS),
            "received": received, "unique_seen": len(seen), "errors": errors,
            "source_totals": {}, "secondary_sources": [],
        },
        "geography": {}, "backfill": None,
    }


def main(*, core_only=False, include_backfill=True):
    verify_database_backend()

    # The scheduled Daily is compact; the separate cloud job handles the full
    # taxonomy and geography. Preserve full-sweep compatibility for old callers.
    deep = core_daily_sweep() if core_only else run_deep_harvest(include_backfill=include_backfill)

    alert_results = []
    summaries = []
    errors = list((deep.get("live") or {}).get("errors") or [])
    errors.extend((deep.get("backfill") or {}).get("errors") or [])
    errors.extend((deep.get("geography") or {}).get("errors") or [])

    summaries.append(
        {
            "query": "PIO deep live sweep",
            "received": (deep.get("live") or {}).get("received", 0),
            "unique": (deep.get("live") or {}).get("unique_seen", 0),
            "errors": len((deep.get("live") or {}).get("errors") or []),
            "coverage": (
                f"{(deep.get('live') or {}).get('queries_processed', 0)}/"
                f"{(deep.get('live') or {}).get('queries_total', 0)}"
            ),
        }
    )
    if deep.get("backfill"):
        summaries.append(
            {
                "query": "Historical Crossref backfill",
                "received": deep["backfill"].get("received", 0),
                "unique": deep["backfill"].get("unique_seen", 0),
                "errors": len(deep["backfill"].get("errors") or []),
                "coverage": f"{deep['backfill'].get('months_processed', 0)} month windows",
            }
        )
    geography = deep.get("geography") or {}
    if geography:
        for label, totals in (geography.get("geography_totals") or {}).items():
            summaries.append(
                {
                    "query": f"Geographic Intelligence — {label}",
                    "received": totals.get("received", 0),
                    "unique": totals.get("unique_seen", 0),
                    "errors": totals.get("errors", 0),
                    "coverage": (
                        f"{totals.get('queries_processed', 0)} geographic queries"
                    ),
                }
            )

    # User-created alerts remain additive to the broad daily sweep.
    for alert in alerts_due():
        plan = route_query(alert["query"], alert.get("domain") or "auto")
        if plan["domain"] != "academic":
            summaries.append(
                {
                    "query": alert["query"],
                    "status": "legal-review",
                    "sources": plan["manual_sources"],
                }
            )
            mark_alert_run(alert["id"])
            continue
        try:
            sources = (
                json.loads(alert.get("sources_json") or "[]")
                or plan["automated_sources"]
            )
        except Exception:
            sources = plan["automated_sources"]
        print(f"[alert] {alert['query']}")
        out = _run(alert["query"], sources)
        alert_results.extend(out["results"])
        errors.extend([f"alert {alert['query']}: {e}" for e in out["errors"]])
        summaries.append(
            {
                "query": alert["query"],
                "received": out["received"],
                "unique": out["unique"],
                "errors": len(out["errors"]),
            }
        )
        mark_alert_run(alert["id"])

    if alert_results:
        upsert_papers(alert_results)

    live = deep.get("live") or {}
    backfill = deep.get("backfill") or {}
    geography = deep.get("geography") or {}
    total_seen = (
        int(live.get("received") or 0)
        + int(backfill.get("received") or 0)
        + int(geography.get("received") or 0)
        + len(alert_results)
    )
    total_unique = (
        int(live.get("unique_seen") or 0)
        + int(backfill.get("unique_seen") or 0)
        + int(geography.get("unique_seen") or 0)
        + len({p.get("id") for p in alert_results if p.get("id")})
    )

    log_radar_run(
        DEFAULT_SOURCES,
        CORE_TOPICS if core_only else coverage_queries(),
        total_seen,
        total_unique,
        errors,
    )

    payload = {
        "date": date.today().isoformat(),
        "deep_harvest": deep,
        "queries": summaries,
        "results_seen": total_seen,
        "unique_seen": total_unique,
        "errors": errors,
    }
    (REPORTS / f"daily_{date.today().isoformat()}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        f"# Orion Daily Deep Radar — {date.today().isoformat()}",
        "",
        f"Taxonomía PIO: {deep.get('coverage_query_count', 0)} consultas.",
        (
            "Cobertura en vivo: "
            f"{live.get('queries_processed', 0)}/{live.get('queries_total', 0)}."
        ),
        f"Registros vistos: {total_seen}.",
        f"Registros únicos de esta corrida: {total_unique}.",
        "",
        "## Fuentes automáticas",
    ]
    for source, values in sorted((live.get("source_totals") or {}).items()):
        md.append(
            f"- **{source}** — {values.get('results', 0)} resultados; "
            f"{values.get('network_requests', 0)} requests; "
            f"{values.get('retries', 0)} reintentos; "
            f"{values.get('rate_limited_queries', 0)} consultas con 429."
        )

    md += ["", "## Geographic Evidence Intelligence"]
    for label, values in (geography.get("geography_totals") or {}).items():
        md.append(
            f"- **{label}** — {values.get('queries_processed', 0)} consultas; "
            f"{values.get('received', 0)} resultados; "
            f"{values.get('unique_seen', 0)} únicos."
        )

    md += ["", "## Fuentes complementarias"]
    for source in live.get("secondary_sources") or []:
        md.append(f"- {source}")

    if backfill:
        md += [
            "",
            "## Backfill histórico",
            (
                f"Ventanas procesadas: {backfill.get('months_processed', 0)}; "
                f"siguiente cursor: {backfill.get('next_cursor', '—')}."
            ),
        ]

    md += ["", "## Resumen"]
    for item in summaries:
        md.append(
            f"- **{item['query']}** — {item.get('unique', '—')} únicos; "
            f"{item.get('errors', 0)} avisos"
            + (f"; cobertura {item['coverage']}" if item.get("coverage") else "")
        )
    if errors:
        md += ["", "## Avisos"] + [f"- {e}" for e in errors[:200]]

    (REPORTS / f"daily_{date.today().isoformat()}.md").write_text(
        "\n".join(md), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False))
    return payload


if __name__ == "__main__":
    main()
