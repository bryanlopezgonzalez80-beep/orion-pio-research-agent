"""Orion daily comprehensive I-O research refresh for 07:00 Puerto Rico (AST)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from coverage_engine import run_comprehensive_refresh
from data_store import upsert_papers, verify_database_backend
from orion_platform import execute_academic_search, route_query
from platform_store import alerts_due, mark_alert_run

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


def _run_alert(query, sources=None):
    return execute_academic_search(
        query,
        days=14,
        per_source=20,
        sources=sources,
        max_keep=180,
        retries=2,
        cache_ttl_hours=4,
        force_refresh=True,
    )


def main():
    verify_database_backend()

    print("[coverage] starting comprehensive PIO sweep")
    coverage = run_comprehensive_refresh(trigger="scheduled")
    alert_summaries = []
    alert_errors = []

    for alert in alerts_due():
        plan = route_query(alert["query"], alert.get("domain") or "auto")
        if plan["domain"] != "academic":
            alert_summaries.append(
                {
                    "query": alert["query"],
                    "status": "legal-review",
                    "sources": plan["manual_sources"],
                }
            )
            mark_alert_run(alert["id"])
            continue

        try:
            sources = json.loads(alert.get("sources_json") or "[]") or plan["automated_sources"]
        except Exception:
            sources = plan["automated_sources"]

        print(f"[alert] {alert['query']}")
        outcome = _run_alert(alert["query"], sources)
        upsert_papers(outcome["results"])
        alert_errors.extend(
            [f"alert {alert['query']}: {error}" for error in outcome["errors"]]
        )
        alert_summaries.append(
            {
                "query": alert["query"],
                "received": outcome["received"],
                "unique": outcome["unique"],
                "errors": len(outcome["errors"]),
            }
        )
        mark_alert_run(alert["id"])

    payload = {
        "date": date.today().isoformat(),
        "coverage": coverage,
        "alerts": alert_summaries,
        "alert_errors": alert_errors,
    }
    (REPORTS / f"daily_{date.today().isoformat()}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"# Orion Daily Radar — {date.today().isoformat()}",
        "",
        "## Comprehensive PIO coverage",
        f"- Topics completed: {coverage['topics_completed']} / {coverage['topics_total']}",
        f"- Provider records seen: {coverage['results_seen']}",
        f"- Unique papers processed: {coverage['final_batch_unique']}",
        f"- Provider warnings: {coverage['error_count']}",
        "",
        "### Results by source",
    ]
    for source, count in sorted(
        coverage["source_result_counts"].items(), key=lambda item: item[1], reverse=True
    ):
        lines.append(f"- **{source}** — {count}")

    lines += ["", "### Results by PIO domain"]
    for domain, count in sorted(
        coverage["domain_result_counts"].items(), key=lambda item: item[1], reverse=True
    ):
        lines.append(f"- **{domain}** — {count}")

    if alert_summaries:
        lines += ["", "## User alerts"]
        for item in alert_summaries:
            lines.append(
                f"- **{item['query']}** — {item.get('unique', '—')} unique; "
                f"{item.get('errors', 0)} warnings"
            )

    all_errors = coverage["errors"] + alert_errors
    if all_errors:
        lines += ["", "## Technical warnings"] + [f"- {error}" for error in all_errors[:100]]

    (REPORTS / f"daily_{date.today().isoformat()}.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
