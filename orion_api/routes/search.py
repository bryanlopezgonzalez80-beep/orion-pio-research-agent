from fastapi import APIRouter

from ..schemas import SearchRequest, SearchResponse
from ..services import research_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    request: SearchRequest,
) -> dict:
    return research_service.search(request.query, request.limit)
