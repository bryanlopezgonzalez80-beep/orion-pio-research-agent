from fastapi import APIRouter, Depends

from ..dependencies import require_api_key
from ..schemas import SearchRequest, SearchResponse
from ..services import research_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    request: SearchRequest, _: None = Depends(require_api_key)
) -> dict:
    return research_service.search(request.query, request.limit)
