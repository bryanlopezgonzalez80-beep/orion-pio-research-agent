from __future__ import annotations

from threading import Lock
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from coverage_catalog import COVERAGE_TOPICS, coverage_domains
from coverage_engine import run_comprehensive_refresh
from data_store import db_stats
from platform_store import latest_coverage_run

from ..dependencies import require_read_quota, require_write_quota
from ..schemas import PaperListResponse
from ..services import paper_service

router = APIRouter(prefix="/radar", tags=["radar"])
_refresh_lock = Lock()


@router.get(
    "",
    response_model=PaperListResponse,
    dependencies=[Depends(require_read_quota)],
)
def radar(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> PaperListResponse:
    """Return the accumulated research radar instead of only the latest search."""
    items = paper_service.list_papers(limit=limit, offset=offset)
    return PaperListResponse(items=items, limit=limit, offset=offset, count=len(items))


@router.get("/coverage", dependencies=[Depends(require_read_quota)])
def coverage_status() -> dict:
    """Expose safe coverage progress without provider credentials or internals."""
    stats = db_stats()
    latest = latest_coverage_run()
    if latest:
        errors = latest.pop("errors", []) or []
        latest["error_count"] = len(errors)
    return {
        "catalog_topics": len(COVERAGE_TOPICS),
        "catalog_domains": len(coverage_domains()),
        "papers_persisted": int(stats.get("papers") or 0),
        "last_run": latest,
        "manual_refresh_running": _refresh_lock.locked(),
    }


def _run_refresh_and_release():
    try:
        run_comprehensive_refresh(trigger="manual")
    finally:
        if _refresh_lock.locked():
            _refresh_lock.release()


@router.post(
    "/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_write_quota)],
)
def refresh_radar(background_tasks: BackgroundTasks) -> dict:
    """Queue one comprehensive refresh in the API worker without blocking the client."""
    if not _refresh_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A comprehensive radar refresh is already running",
        )
    background_tasks.add_task(_run_refresh_and_release)
    return {
        "accepted": True,
        "status": "queued",
        "message": "Comprehensive PIO refresh queued",
    }
