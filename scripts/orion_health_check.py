"""Read-only Orion system health monitor for local use and GitHub Actions."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping

import requests

from database.config import get_database_config
from database.connection import connect_database, first_value, list_tables

DEFAULT_API_URL = "https://orion-pio-api.onrender.com/health"
MAIN_TABLES = {
    "papers",
    "orion_search_history",
    "orion_source_health",
    "radar_runs",
}


def _result(status: str, summary: str, **metrics) -> dict:
    return {"status": status, "summary": summary, "metrics": metrics}


def _safe_exception(exc: Exception) -> str:
    """Return only an exception type, never its potentially sensitive message."""
    return type(exc).__name__


def check_api(
    *,
    api_url: str = DEFAULT_API_URL,
    timeout: float = 15.0,
    retries: int = 3,
    session=requests,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict:
    last_problem = "request failed"
    for attempt in range(max(1, retries)):
        try:
            response = session.get(api_url, timeout=timeout)
            if response.status_code != 200:
                last_problem = f"HTTP {response.status_code}"
            else:
                payload = response.json()
                database = payload.get("database") if isinstance(payload, dict) else None
                valid = (
                    payload.get("status") == "ok"
                    and isinstance(database, dict)
                    and database.get("engine") == "postgres"
                    and database.get("reachable") is True
                )
                if valid:
                    return _result(
                        "OK",
                        "API healthy with reachable PostgreSQL",
                        http_status=200,
                        engine="postgres",
                        database_reachable=True,
                    )
                last_problem = "health payload failed validation"
        except Exception as exc:
            last_problem = f"request failed ({_safe_exception(exc)})"
        if attempt + 1 < max(1, retries):
            sleep_fn(min(2.0, 0.5 * (2**attempt)))
    return _result("CRITICAL", last_problem, attempts=max(1, retries))


def _parse_timestamp(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _freshness_result(
    label: str,
    latest,
    *,
    now: datetime,
    warning_after: timedelta,
    critical_after: timedelta,
) -> dict:
    timestamp = _parse_timestamp(latest)
    if timestamp is None:
        return _result("WARNING", f"{label} timestamp unavailable")
    age = max(timedelta(0), now - timestamp)
    age_hours = round(age.total_seconds() / 3600, 2)
    safe_timestamp = timestamp.isoformat()
    if age >= critical_after:
        status = "CRITICAL"
    elif age >= warning_after:
        status = "WARNING"
    else:
        status = "OK"
    return _result(
        status,
        f"{label} activity age is {age_hours} hours",
        latest=safe_timestamp,
        age_hours=age_hours,
    )


def _skipped_database_checks() -> dict[str, dict]:
    reason = "DATABASE_URL not configured; SQLite fallback disabled for cloud monitoring"
    return {
        name: _result("SKIPPED", reason)
        for name in ("database", "papers", "daily_radar", "weekly_radar", "source_health")
    }


def check_database(
    *,
    environ: Mapping[str, str] | None = None,
    connector=connect_database,
    table_lister=list_tables,
    now: datetime | None = None,
) -> dict[str, dict]:
    env = os.environ if environ is None else environ
    if not (env.get("DATABASE_URL") or "").strip():
        return _skipped_database_checks()

    connection = None
    try:
        config = get_database_config(environ=dict(env))
        if config.engine != "postgres":
            return _skipped_database_checks()
        connection = connector(config)
        connection.execute("SET TRANSACTION READ ONLY")
        tables = set(table_lister(connection))
        missing = sorted(MAIN_TABLES - tables)
        if missing:
            summary = "Required PostgreSQL tables missing: " + ", ".join(missing)
            unavailable = _result("CRITICAL", summary)
            return {
                "database": unavailable,
                "papers": _result("SKIPPED", "Papers table unavailable"),
                "daily_radar": _result("SKIPPED", "Search history unavailable"),
                "weekly_radar": _result("SKIPPED", "Radar history unavailable"),
                "source_health": _result("SKIPPED", "Source health unavailable"),
            }

        papers_count = int(first_value(connection.execute("SELECT COUNT(*) AS count FROM papers").fetchone()) or 0)
        search_count = int(first_value(connection.execute("SELECT COUNT(*) AS count FROM orion_search_history").fetchone()) or 0)
        source_count = int(first_value(connection.execute("SELECT COUNT(*) AS count FROM orion_source_health").fetchone()) or 0)
        latest_paper = first_value(connection.execute("SELECT MAX(updated_at) AS latest FROM papers").fetchone())
        latest_search = first_value(connection.execute("SELECT MAX(created_at) AS latest FROM orion_search_history").fetchone())
        latest_weekly = first_value(connection.execute("SELECT MAX(run_at) AS latest FROM radar_runs").fetchone())
        source_rows = connection.execute(
            "SELECT source,last_status,success_count,failure_count,consecutive_failures,"
            "circuit_open_until,last_checked FROM orion_source_health ORDER BY source"
        ).fetchall()

        checked_at = now or datetime.now(timezone.utc)
        healthy = 0
        failing = 0
        inactive = 0
        circuits_open = 0
        sources = []
        # Provider freshness is independent from the newest search-history row.
        # A targeted/manual search must not make unrelated providers look stale.
        # Daily Radar runs once per day, so allow a 30-hour freshness window.
        inactive_before = checked_at - timedelta(hours=30)
        for row in source_rows:
            item = dict(row)
            consecutive = int(item.get("consecutive_failures") or 0)
            circuit_until = _parse_timestamp(item.get("circuit_open_until"))
            last_checked = _parse_timestamp(item.get("last_checked"))
            circuit_open = bool(circuit_until and circuit_until > checked_at)
            is_inactive = bool(
                inactive_before is not None
                and last_checked is not None
                and last_checked < inactive_before
                and not circuit_open
            )
            is_failing = (
                not is_inactive
                and (item.get("last_status") == "error" or consecutive > 0)
            )
            healthy += int(not is_failing and not circuit_open and not is_inactive)
            failing += int(is_failing)
            inactive += int(is_inactive)
            circuits_open += int(circuit_open)
            sources.append(
                {
                    "source": str(item.get("source") or "unknown"),
                    "status": (
                        "inactive"
                        if is_inactive
                        else str(item.get("last_status") or "unknown")
                    ),
                    "consecutive_failures": consecutive,
                    "circuit_open": circuit_open,
                    "last_checked": last_checked.isoformat() if last_checked else None,
                }
            )

        if circuits_open:
            source_status = "CRITICAL"
        elif failing or source_count == 0:
            source_status = "WARNING"
        else:
            source_status = "OK"

        daily_freshness = _freshness_result(
            "Daily Radar",
            latest_search,
            now=checked_at,
            warning_after=timedelta(hours=48),
            critical_after=timedelta(hours=72),
        )
        daily_freshness["metrics"] = {
            "search_history_count": search_count,
            **daily_freshness["metrics"],
        }
        return {
            "database": _result(
                "OK", "PostgreSQL reachable in read-only transaction", tables_checked=len(MAIN_TABLES)
            ),
            "papers": _result(
                "OK" if papers_count else "WARNING",
                f"{papers_count} papers persisted",
                count=papers_count,
                latest_updated_at=(
                    _parse_timestamp(latest_paper).isoformat()
                    if _parse_timestamp(latest_paper)
                    else None
                ),
            ),
            "daily_radar": daily_freshness,
            "weekly_radar": _freshness_result(
                "Weekly Radar",
                latest_weekly,
                now=checked_at,
                warning_after=timedelta(days=9),
                critical_after=timedelta(days=14),
            ),
            "source_health": _result(
                source_status,
                f"{healthy} healthy, {failing} failing, {inactive} inactive, {circuits_open} circuits open",
                total=source_count,
                healthy=healthy,
                failing=failing,
                inactive=inactive,
                circuits_open=circuits_open,
                sources=sources,
            ),
        }
    except Exception as exc:
        safe = f"PostgreSQL unavailable ({_safe_exception(exc)})"
        return {
            "database": _result("CRITICAL", safe),
            "papers": _result("SKIPPED", "Database unavailable"),
            "daily_radar": _result("SKIPPED", "Database unavailable"),
            "weekly_radar": _result("SKIPPED", "Database unavailable"),
            "source_health": _result("SKIPPED", "Database unavailable"),
        }
    finally:
        if connection is not None:
            try:
                connection.rollback()
            finally:
                connection.close()


def _overall_status(checks: Mapping[str, dict]) -> str:
    statuses = [check["status"] for check in checks.values()]
    if "CRITICAL" in statuses:
        return "CRITICAL"
    if "WARNING" in statuses:
        return "WARNING"
    if statuses and all(status == "SKIPPED" for status in statuses):
        return "SKIPPED"
    if "SKIPPED" in statuses:
        return "WARNING"
    return "OK"


def collect_health(
    *,
    api_url: str = DEFAULT_API_URL,
    timeout: float = 15.0,
    retries: int = 3,
    environ: Mapping[str, str] | None = None,
    session=requests,
    connector=connect_database,
    table_lister=list_tables,
    now: datetime | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict:
    checked_at = now or datetime.now(timezone.utc)
    checks = {
        "api": check_api(
            api_url=api_url,
            timeout=timeout,
            retries=retries,
            session=session,
            sleep_fn=sleep_fn,
        ),
        **check_database(
            environ=environ,
            connector=connector,
            table_lister=table_lister,
            now=checked_at,
        ),
    }
    overall = _overall_status(checks)
    return {
        "generated_at": checked_at.isoformat(),
        "overall": overall,
        "checks": checks,
    }


def render_human(report: Mapping[str, object]) -> str:
    checks = report["checks"]
    labels = {
        "api": "API",
        "database": "PostgreSQL",
        "papers": "Papers",
        "daily_radar": "Daily Radar",
        "weekly_radar": "Weekly Radar",
        "source_health": "Source health",
    }
    lines = ["ORION SYSTEM HEALTH", ""]
    for key, label in labels.items():
        check = checks[key]
        lines.append(f"{label:.<22} {check['status']}: {check['summary']}")
    lines.extend(("", f"Overall............... {report['overall']}"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("orion-health.json"))
    args = parser.parse_args(argv)
    report = collect_health(
        api_url=args.api_url,
        timeout=max(1.0, args.timeout),
        retries=max(1, min(args.retries, 5)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render_human(report))
    print(f"\nJSON report: {args.output}")
    return 1 if report["overall"] == "CRITICAL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
