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
    return research_service.search(request.query, request.limit)
