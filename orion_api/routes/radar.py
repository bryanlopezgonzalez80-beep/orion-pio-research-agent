from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
import time
from uuid import uuid4
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from deep_harvest import BACKFILL_FLOOR_YEAR, harvest_status, run_live_sweep, run_historical_backfill
from platform_store import get_setting, set_setting
from harvest_coordinator import active_harvest, exclusive_job, heartbeat_harvest

from ..dependencies import require_read_quota, require_search_quota
from ..schemas import PaperListResponse
from ..services import paper_service

router = APIRouter(
    prefix="/radar",
    tags=["radar"],
    dependencies=[Depends(require_read_quota)],
)

_REFRESH_LOCK = Lock()
_BACKFILL_LOCK = Lock()
_MANUAL_STATUS_KEY = "deep_harvest.manual_refresh"
_BACKFILL_STATUS_KEY = "deep_harvest.manual_backfill"
_STATUS_CACHE_TTL_SECONDS = 20.0
_STATUS_CACHE: dict | None = None
_STATUS_CACHE_AT = 0.0
_STATUS_CACHE_LOCK = Lock()
_MANUAL_STALE_SECONDS = 90 * 60
_MANUAL_RUNTIME_SECONDS = 40 * 60
_INSTANCE_ID = uuid4().hex


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _manual_refresh_status() -> dict | None:
    """Return persisted progress and recover jobs abandoned by a process restart."""
    value = get_setting(_MANUAL_STATUS_KEY)
    if not isinstance(value, dict):
        return value
    if value.get("state") not in {"queued", "running"}:
        return value
    if value.get("instance_id") != _INSTANCE_ID and not active_harvest(_MANUAL_STATUS_KEY, value.get("instance_id")):
        recovered = {
            **value,
            "state": "interrupted_retryable",
            "interrupted_at": _iso_now(),
            "message": "La instancia cambió durante la ejecución; puede reanudarse de forma segura.",
        }
        set_setting(_MANUAL_STATUS_KEY, recovered)
        return recovered
    raw_heartbeat = (
        value.get("updated_at")
        or value.get("started_at")
        or value.get("requested_at")
    )
    if not raw_heartbeat:
        return value
    try:
        heartbeat = datetime.fromisoformat(str(raw_heartbeat).replace("Z", "+00:00"))
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return value
    age = (datetime.now(timezone.utc) - heartbeat).total_seconds()
    if age <= _MANUAL_STALE_SECONDS:
        return value
    recovered = {
        **value,
        "state": "interrupted_retryable",
        "interrupted_at": _iso_now(),
        "message": "La ejecución anterior se interrumpió; puede reanudarse de forma segura.",
    }
    set_setting(_MANUAL_STATUS_KEY, recovered)
    return recovered


@exclusive_job(_MANUAL_STATUS_KEY, lambda: _INSTANCE_ID, lambda: _REFRESH_LOCK)
def _run_manual_refresh() -> None:
    try:
        started_at = _iso_now()
        set_setting(
            _MANUAL_STATUS_KEY,
            {
                "state": "running",
                "instance_id": _INSTANCE_ID,
                "phase": "taxonomy",
                "started_at": started_at,
                "queries_processed": 0,
                "queries_total": 0,
                "received": 0,
                "unique_seen": 0,
                "journal_watch_processed": 0,
                "journal_watch_total": 0,
                "source_totals": {},
                "geography_phase": "",
                "geo_queries_processed": 0,
                "geo_queries_total": 0,
                "geography_totals": {},
            },
        )

        def report_progress(progress: dict) -> None:
            heartbeat_harvest()
            set_setting(
                _MANUAL_STATUS_KEY,
                {
                    "state": "running",
                    "instance_id": _INSTANCE_ID,
                    "phase": progress.get("phase") or "taxonomy",
                    "started_at": started_at,
                    "updated_at": _iso_now(),
                    "queries_processed": int(progress.get("queries_processed") or 0),
                    "queries_total": int(progress.get("queries_total") or 0),
                    "received": int(progress.get("received") or 0),
                    "unique_seen": int(progress.get("unique_seen") or 0),
                    "journal_watch_processed": int(
                        progress.get("journal_watch_processed") or 0
                    ),
                    "journal_watch_total": int(
                        progress.get("journal_watch_total") or 0
                    ),
                    "source_totals": progress.get("source_totals") or {},
                    "geography_phase": progress.get("geography_phase") or "",
                    "geo_queries_processed": int(
                        progress.get("geo_queries_processed") or 0
                    ),
                    "geo_queries_total": int(
                        progress.get("geo_queries_total") or 0
                    ),
                    "geography_totals": progress.get("geography_totals") or {},
                },
            )

        # The task runs in Starlette's background thread pool, so the HTTP
        # response and status polling remain available while the complete
        # taxonomy is refreshed.
        live = run_live_sweep(
            per_source=10,
            max_runtime_seconds=_MANUAL_RUNTIME_SECONDS,
            progress_callback=report_progress,
        )
        geography = {}
        remaining = int(live.get("queries_remaining") or 0)
        if remaining:
            completed_state = "partial_retryable"
        else:
            completed_state = (
                "completed_with_warnings" if live.get("errors") else "completed"
            )
        set_setting(
            _MANUAL_STATUS_KEY,
            {
                "state": completed_state,
                "completed_at": _iso_now(),
                "queries_processed": live.get("queries_processed", 0),
                "queries_total": live.get("queries_total", 0),
                "received": live.get("received", 0),
                "unique_seen": live.get("unique_seen", 0),
                "queries_remaining": remaining,
                "errors": len(live.get("errors") or []),
                "source_totals": live.get("source_totals") or {},
                "journal_watch_processed": live.get("journal_watch_processed", 0),
                "journal_watch_total": live.get("journal_watch_count", 0),
                "geography_phase": "completed",
                "geo_queries_processed": geography.get("queries_processed", 0),
                "geo_queries_total": geography.get("queries_total", 0),
                "geography_totals": geography.get("geography_totals") or {},
            },
        )
    except Exception as exc:
        set_setting(
            _MANUAL_STATUS_KEY,
            {
                "state": "failed",
                "completed_at": _iso_now(),
                "error": type(exc).__name__,
            },
        )
    finally:
        if _REFRESH_LOCK.locked():
            _REFRESH_LOCK.release()


def _backfill_status() -> dict | None:
    value = get_setting(_BACKFILL_STATUS_KEY)
    if not isinstance(value, dict) or value.get("state") not in {"queued", "running"}:
        return value
    if value.get("instance_id") != _INSTANCE_ID and not active_harvest(_BACKFILL_STATUS_KEY, value.get("instance_id")):
        recovered = {**value, "state": "interrupted_retryable", "interrupted_at": _iso_now(), "message": "La corrida se interrumpió al reiniciar el servicio; puede reanudarse con seguridad."}
        set_setting(_BACKFILL_STATUS_KEY, recovered)
        return recovered
    return value


@exclusive_job(_BACKFILL_STATUS_KEY, lambda: _INSTANCE_ID, lambda: _BACKFILL_LOCK)
def _run_manual_backfill(months_per_run: int | None = None) -> None:
    snapshot: dict = {}
    try:
        started_at = _iso_now()
        months = months_per_run if months_per_run is not None else 24
        snapshot = {
            "state": "running", "instance_id": _INSTANCE_ID, "started_at": started_at,
            "phase": "historical", "months_per_run": months,
            "tasks_completed": 0, "tasks_total": 0, "tasks_scope": "run",
            "months_processed": 0, "records_received": 0,
        }
        set_setting(_BACKFILL_STATUS_KEY, snapshot)
        planned_months: int | None = None
        previous_month: str | None = None
        previous_month_records = 0
        completed_month_records = 0
        completed_months = 0

        def report_progress(progress: dict) -> None:
            heartbeat_harvest()
            nonlocal snapshot, planned_months, previous_month
            nonlocal previous_month_records, completed_month_records, completed_months
            month = progress.get("backfill_month")
            if planned_months is None and month:
                try:
                    first_month = datetime.fromisoformat(str(month))
                    remaining_months = max(0, (first_month.year - BACKFILL_FLOOR_YEAR) * 12 + first_month.month)
                    planned_months = min(months, remaining_months)
                except ValueError:
                    pass
            if previous_month and month != previous_month:
                completed_month_records += previous_month_records
                completed_months += 1
                previous_month_records = 0
            previous_month = month
            previous_month_records = max(previous_month_records, int(progress.get("backfill_records_received") or 0))
            snapshot = {
                "state": "running", "instance_id": _INSTANCE_ID, "started_at": started_at,
                "updated_at": _iso_now(), "phase": progress.get("phase", "historical"),
                "backfill_month": month, "months_per_run": months,
                "tasks_completed": progress.get("backfill_tasks_completed_total", 0),
                "tasks_total": int(progress.get("backfill_tasks_total") or 0) * (planned_months or 0),
                "tasks_scope": "run", "months_processed": completed_months,
                "records_received": completed_month_records + previous_month_records,
            }
            set_setting(_BACKFILL_STATUS_KEY, snapshot)

        result = run_historical_backfill(months_per_run=months, progress_callback=report_progress)
        set_setting(_BACKFILL_STATUS_KEY, {
            **snapshot,
            "state": "partial_retryable" if result.get("partial") else "completed_with_warnings" if result.get("errors") else "completed",
            "completed_at": _iso_now(), "next_cursor": result.get("next_cursor"),
            "months_processed": result.get("months_processed", 0),
            "records_received": result.get("received", 0),
            "errors": len(result.get("errors") or []),
        })
    except Exception as exc:
        set_setting(_BACKFILL_STATUS_KEY, {**snapshot, "state": "failed", "completed_at": _iso_now(), "error": type(exc).__name__})
    finally:
        if _BACKFILL_LOCK.locked():
            _BACKFILL_LOCK.release()


@router.get("", response_model=PaperListResponse)
def radar(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    geography: Annotated[
        Literal["puerto_rico", "united_states", "latam_caribbean", "global", "unknown"] | None,
        Query(),
    ] = None,
    geography_relation: Literal["any", "study", "affiliation_or_mention"] | None = None,
    source: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    year: Annotated[int | None, Query(ge=1800, le=2200)] = None,
    evidence_type: Annotated[str | None, Query(min_length=2, max_length=50)] = None,
    peer_review_status: Literal["CONFIRMED", "LIKELY", "UNKNOWN", "NOT_PEER_REVIEWED"] | None = None,
    access_status: Literal["OPEN_ACCESS", "INSTITUTIONAL_ACCESS", "PROVIDER_LOGIN", "PUBLISHER_ACCESS", "DOI_ONLY", "METADATA_ONLY", "UNKNOWN"] | None = None,
    retraction_status: Literal["RETRACTED", "EXPRESSION_OF_CONCERN", "CORRECTED", "UNKNOWN"] | None = None,
    open_access: bool | None = None,
) -> PaperListResponse:
    """Return the accumulated research radar instead of only the latest search."""
    items = paper_service.list_papers(
        limit=limit, offset=offset, geography=geography,
        geography_relation=geography_relation, source=source, year=year,
        evidence_type=evidence_type, peer_review_status=peer_review_status,
        access_status=access_status, retraction_status=retraction_status,
        open_access=open_access,
    )
    return PaperListResponse(
        items=items,
        limit=limit,
        offset=offset,
        count=len(items),
        metadata={"geography": paper_service.geography_facets()},
    )


@router.get("/status")
def radar_status() -> dict:
    """Return coverage with a short-lived cache so polling never overloads the database."""
    global _STATUS_CACHE, _STATUS_CACHE_AT
    now = time.monotonic()
    cached = _STATUS_CACHE
    if cached is not None and now - _STATUS_CACHE_AT < _STATUS_CACHE_TTL_SECONDS:
        return {**cached, "manual_refresh": _manual_refresh_status(), "manual_backfill": _backfill_status()}

    if not _STATUS_CACHE_LOCK.acquire(blocking=False):
        if cached is not None:
            return {**cached, "manual_refresh": _manual_refresh_status(), "manual_backfill": _backfill_status()}
        _STATUS_CACHE_LOCK.acquire()
    try:
        now = time.monotonic()
        if _STATUS_CACHE is None or now - _STATUS_CACHE_AT >= _STATUS_CACHE_TTL_SECONDS:
            fresh = harvest_status()
            fresh.pop("manual_refresh", None)
            _STATUS_CACHE = fresh
            _STATUS_CACHE_AT = now
        return {**(_STATUS_CACHE or {}), "manual_refresh": _manual_refresh_status(), "manual_backfill": _backfill_status()}
    finally:
        _STATUS_CACHE_LOCK.release()


@router.post(
    "/refresh",
    status_code=202,
    dependencies=[Depends(require_search_quota)],
)
def refresh_radar(background_tasks: BackgroundTasks) -> dict:
    """Start a full live PIO taxonomy sweep without blocking the HTTP request."""
    if active_harvest():
        return {"status": "already_running", "manual_refresh": _manual_refresh_status(), "manual_backfill": _backfill_status()}
    if not _REFRESH_LOCK.acquire(blocking=False):
        return {
            "status": "already_running",
            "manual_refresh": _manual_refresh_status(),
        }
    set_setting(
        _MANUAL_STATUS_KEY,
        {"state": "queued", "instance_id": _INSTANCE_ID, "requested_at": _iso_now()},
    )
    background_tasks.add_task(_run_manual_refresh)
    return {
        "status": "queued",
        "message": "Full PIO live sweep queued",
    }


@router.post("/backfill", status_code=202, dependencies=[Depends(require_search_quota)])
def refresh_backfill(background_tasks: BackgroundTasks, payload: dict | None = None) -> dict:
    """Start the resumable historical backfill without rerunning the live Radar."""
    months = (payload or {}).get("months_per_run", 24)
    # Validate before acquiring the lock: malformed input must never leave it held.
    if type(months) is not int or months not in {24, 48, 96, 120}:
        raise HTTPException(status_code=422, detail="Selecciona un plazo de 2, 4, 8 o 10 años.")
    if active_harvest():
        return {"status": "already_running", "manual_refresh": _manual_refresh_status(), "manual_backfill": _backfill_status()}
    if not _BACKFILL_LOCK.acquire(blocking=False):
        return {"status": "already_running", "manual_backfill": _backfill_status()}
    set_setting(_BACKFILL_STATUS_KEY, {"state": "queued", "instance_id": _INSTANCE_ID, "requested_at": _iso_now(), "months_per_run": months})
    background_tasks.add_task(_run_manual_backfill, months)
    return {"status": "queued", "message": "Historical backfill queued", "months_per_run": months}
