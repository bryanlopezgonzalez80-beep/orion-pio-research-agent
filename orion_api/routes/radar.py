from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from deep_harvest import harvest_status, run_deep_harvest
from platform_store import get_setting, set_setting

from ..dependencies import require_read_quota, require_search_quota
from ..schemas import PaperListResponse
from ..services import paper_service

router = APIRouter(
    prefix="/radar",
    tags=["radar"],
    dependencies=[Depends(require_read_quota)],
)

_REFRESH_LOCK = Lock()
_MANUAL_STATUS_KEY = "deep_harvest.manual_refresh"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_manual_refresh() -> None:
    try:
        started_at = _iso_now()
        set_setting(
            _MANUAL_STATUS_KEY,
            {
                "state": "running",
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
            set_setting(
                _MANUAL_STATUS_KEY,
                {
                    "state": "running",
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

        result = run_deep_harvest(
            include_backfill=False,
            progress_callback=report_progress,
        )
        live = result.get("live") or {}
        geography = result.get("geography") or {}
        set_setting(
            _MANUAL_STATUS_KEY,
            {
                "state": "completed",
                "completed_at": _iso_now(),
                "queries_processed": live.get("queries_processed", 0),
                "queries_total": live.get("queries_total", 0),
                "received": live.get("received", 0),
                "unique_seen": live.get("unique_seen", 0),
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


@router.get("", response_model=PaperListResponse)
def radar(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    geography: Annotated[
        Literal["puerto_rico", "united_states", "latam_caribbean"] | None,
        Query(),
    ] = None,
) -> PaperListResponse:
    """Return the accumulated research radar instead of only the latest search."""
    items = paper_service.list_papers(
        limit=limit, offset=offset, geography=geography
    )
    return PaperListResponse(items=items, limit=limit, offset=offset, count=len(items))


@router.get("/status")
def radar_status() -> dict:
    """Return persisted deep-harvest coverage and the last manual refresh state."""
    status = harvest_status()
    status["manual_refresh"] = get_setting(_MANUAL_STATUS_KEY)
    return status


@router.post(
    "/refresh",
    status_code=202,
    dependencies=[Depends(require_search_quota)],
)
def refresh_radar(background_tasks: BackgroundTasks) -> dict:
    """Start a full live PIO taxonomy sweep without blocking the HTTP request."""
    if not _REFRESH_LOCK.acquire(blocking=False):
        return {
            "status": "already_running",
            "manual_refresh": get_setting(_MANUAL_STATUS_KEY),
        }
    set_setting(
        _MANUAL_STATUS_KEY,
        {"state": "queued", "requested_at": _iso_now()},
    )
    background_tasks.add_task(_run_manual_refresh)
    return {
        "status": "queued",
        "message": "Full PIO live sweep queued",
    }
