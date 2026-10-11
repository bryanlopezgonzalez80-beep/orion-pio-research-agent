from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import require_read_quota, require_write_quota
from ..schemas import LibraryUpdate, PaperListResponse, PaperResponse
from ..services import paper_service
from ..library_cursor import decode_cursor, encode_cursor
import data_store

router = APIRouter(prefix="/library", tags=["library"])


@router.get(
    "", response_model=PaperListResponse, dependencies=[Depends(require_read_quota)]
)
def library(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    cursor: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
) -> PaperListResponse:
    # Deep Harvest already persists every deduplicated Radar discovery. The
    # Library is the durable view of that archive; favorites remain a separate
    # user flag instead of deciding whether a paper is visible here.
    if cursor is not None:
        if offset:
            raise HTTPException(status_code=400, detail="Cursor cannot be combined with offset")
        rows = data_store.list_library_cursor(limit + 1, decode_cursor(cursor))
        more = len(rows) > limit
        items = [paper_service._normalize_paper(p) for p in rows[:limit]]
        return PaperListResponse(items=items, limit=limit, offset=0, count=len(items), metadata={
            "next_cursor": encode_cursor(items[-1]["id"]) if more and items else None,
            "order": "id_desc", "statistics_max_age_seconds": 120,
        })
    items = paper_service.list_papers(limit=limit, offset=offset)
    return PaperListResponse(items=items, limit=limit, offset=offset, count=len(items))


@router.post(
    "", response_model=PaperResponse, dependencies=[Depends(require_write_quota)]
)
def update_library(
    request: LibraryUpdate,
) -> dict:
    paper = paper_service.update_favorite(request.paper_id, request.favorite)
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    return paper
