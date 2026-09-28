from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..dependencies import require_read_quota
from ..schemas import PaperListResponse
from ..services import paper_service

router = APIRouter(
    prefix="/radar",
    tags=["radar"],
    dependencies=[Depends(require_read_quota)],
)


@router.get("", response_model=PaperListResponse)
def radar(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> PaperListResponse:
    """Return the accumulated research radar instead of only the latest search."""
    items = paper_service.list_papers(limit=limit, offset=offset)
    return PaperListResponse(items=items, limit=limit, offset=offset, count=len(items))
