from fastapi import APIRouter, Depends

from ..dependencies import require_read_quota
from ..schemas import SourceResponse
from ..services import source_service

router = APIRouter(
    prefix="/sources",
    tags=["sources"],
    dependencies=[Depends(require_read_quota)],
)


@router.get("", response_model=list[SourceResponse])
def sources() -> list[dict]:
    return source_service.list_public_sources()
