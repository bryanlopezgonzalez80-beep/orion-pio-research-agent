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
    try:
        return research_service.search(
            request.query,
            request.limit,
            days=request.days,
            per_source=request.per_source,
            sources=request.sources,
            include_pr=request.include_pr,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return research_service.search(request.query, request.limit)
