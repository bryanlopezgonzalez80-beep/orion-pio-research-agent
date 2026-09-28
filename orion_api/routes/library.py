from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import require_api_key
from ..schemas import LibraryUpdate, PaperListResponse, PaperResponse
from ..services import paper_service

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=PaperListResponse)
def library(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> PaperListResponse:
    items = paper_service.list_papers(
        limit=limit, offset=offset, favorites_only=True
    )
    return PaperListResponse(items=items, limit=limit, offset=offset, count=len(items))


@router.post("", response_model=PaperResponse)
def update_library(
    request: LibraryUpdate, _: None = Depends(require_api_key)
) -> dict:
    paper = paper_service.update_favorite(request.paper_id, request.favorite)
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    return paper
