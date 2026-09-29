from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Annotated

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
        set_setting(
            _MANUAL_STATUS_KEY,
            {"state": "running", "started_at": _iso_now()},
        )
        result = run_deep_harvest(include_backfill=False)
        live = result.get("live") or {}
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
) -> PaperListResponse:
    """Return the accumulated research radar instead of only the latest search."""
    items = paper_service.list_papers(limit=limit, offset=offset)
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
