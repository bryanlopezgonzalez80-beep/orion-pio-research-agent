from fastapi import APIRouter

from ..schemas import SourceResponse
from ..services import source_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceResponse])
def sources() -> list[dict]:
    return source_service.list_public_sources()
