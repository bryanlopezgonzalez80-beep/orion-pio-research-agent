from fastapi import APIRouter, Depends

from ..dependencies import require_search_quota
from ..schemas import SearchRequest, SearchResponse
from ..services import research_service

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(require_search_quota)],
)


@router.post("", response_model=SearchResponse)
def search(
    request: SearchRequest,
) -> dict:
    return research_service.search(\n        request.query,\n        request.limit,\n        days=request.days,\n        per_source=request.per_source,\n        sources=request.sources,\n        include_pr=request.include_pr,\n    )
