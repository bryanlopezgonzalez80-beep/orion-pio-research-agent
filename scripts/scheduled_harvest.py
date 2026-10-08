"""Cloud entrypoint: shared durable state, one harvest writer, no web lifetime."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from database.config import get_database_config
from database.connection import connect_database, first_value
from deep_harvest import run_deep_harvest
from harvest_coordinator import exclusive_job, harvest_lock, heartbeat_harvest
from platform_store import get_setting, set_setting

BACKFILL_ENABLED_KEY = "deep_harvest.backfill_schedule_enabled"
LIVE_STATUS_KEY = "deep_harvest.manual_refresh"
INSTANCE = uuid4().hex


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_persistent_database():
    config = get_database_config()
    if config.engine != "postgres":
        raise RuntimeError("Cloud harvesting requires the shared PostgreSQL database.")
    connection = connect_database(config)
    try:
        if first_value(connection.execute("SELECT 1").fetchone()) != 1:
            raise RuntimeError("The shared database did not pass its health check.")
        connection.commit()
    finally:
        connection.close()


@exclusive_job(LIVE_STATUS_KEY, lambda: INSTANCE, lambda: None)
def run_cloud_deep():
    snapshot = {"state": "running", "instance_id": INSTANCE,
                "started_at": _now(), "executor": "github_actions", "phase": "taxonomy"}
    set_setting(LIVE_STATUS_KEY, snapshot)

    def report(progress):
        heartbeat_harvest()
        snapshot.update(progress)
        snapshot.update(state="running", updated_at=_now())
        set_setting(LIVE_STATUS_KEY, dict(snapshot))

    try:
        result = run_deep_harvest(include_backfill=False, progress_callback=report)
        live = result.get("live") or {}
        partial = result.get("status") == "PARTIAL_RETRYABLE" or int(live.get("queries_processed") or 0) < int(live.get("queries_total") or 0)
        warnings = bool(live.get("errors") or (result.get("geography") or {}).get("errors"))
        snapshot.update(state="partial_retryable" if partial else "completed_with_warnings" if warnings else "completed",
                        completed_at=_now(), received=result.get("records_received_this_run", 0))
        set_setting(LIVE_STATUS_KEY, dict(snapshot))
        return result
    except Exception as exc:
        snapshot.update(state="failed", completed_at=_now(), error=type(exc).__name__)
        set_setting(LIVE_STATUS_KEY, dict(snapshot))
        raise


def execute(job: str, *, scheduled=False, historical_action="preserve"):
    if job not in {"daily", "deep", "backfill", "verify"}:
        raise ValueError("Unknown harvest job.")
    if historical_action not in {"preserve", "pause", "resume"}:
        raise ValueError("Unknown historical action.")
    if scheduled and historical_action != "preserve":
        raise ValueError("A schedule cannot change the historical pause setting.")
    require_persistent_database()
    if historical_action != "preserve":
        set_setting(BACKFILL_ENABLED_KEY, historical_action == "resume")
    if job == "verify":
        return {"state": "healthy", "database": "postgres"}
    if job == "backfill":
        if historical_action == "pause" or (scheduled and get_setting(BACKFILL_ENABLED_KEY, False) is not True):
            return {"state": "paused", "months_per_run": 24}
        from orion_api.routes.radar import _run_manual_backfill, _BACKFILL_STATUS_KEY
        os.environ.setdefault("ORION_BACKFILL_RUNTIME_SECONDS", "3000")
        outcome = _run_manual_backfill(24)
        if isinstance(outcome, dict) and outcome.get("state") == "blocked_retryable":
            return outcome
        value = get_setting(_BACKFILL_STATUS_KEY) or {}
        return {key: value.get(key) for key in ("state", "months_per_run", "months_processed", "records_received", "tasks_completed", "tasks_total", "tasks_scope")}
    if job == "deep":
        result = run_cloud_deep()
        if result and result.get("state") == "blocked_retryable":
            return result
        value = get_setting(LIVE_STATUS_KEY) or {}
        return {"state": value.get("state"), "queries_processed": (result or {}).get("live", {}).get("queries_processed", 0),
                "queries_total": (result or {}).get("live", {}).get("queries_total", 0),
                "records_received": (result or {}).get("records_received_this_run", 0)}
    with harvest_lock("deep_harvest.daily_radar", INSTANCE) as owned:
        if not owned:
            return {"state": "blocked_retryable"}
        import daily_agent
        payload = daily_agent.main(core_only=True, include_backfill=False)
        return {"state": "completed_with_warnings" if payload.get("errors") else "completed",
                "core_topics": len(daily_agent.CORE_TOPICS),
                "records_received": payload.get("results_seen", 0),
                "warnings": len(payload.get("errors") or [])}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", choices=["daily", "deep", "backfill", "verify"], default=os.getenv("ORION_JOB_KIND", "verify"))
    parser.add_argument("--historical-action", choices=["preserve", "pause", "resume"], default=os.getenv("ORION_HISTORICAL_ACTION", "preserve"))
    parser.add_argument("--scheduled", action="store_true", default=os.getenv("ORION_JOB_SCHEDULED") == "true")
    parser.add_argument("--output", default="reports/cloud_harvest.json")
    args = parser.parse_args(argv)
    try:
        result = execute(args.job, scheduled=args.scheduled, historical_action=args.historical_action)
        code = 1 if result.get("state") == "failed" else 0
    except Exception as exc:
        result = {"state": "failed", "error_type": type(exc).__name__}
        code = 1
    payload = {"job": args.job, "completed_at": _now(), **result}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
