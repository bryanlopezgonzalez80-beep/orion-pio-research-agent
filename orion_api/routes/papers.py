from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import require_read_quota
from ..schemas import PaperListResponse, PaperResponse
from ..services import paper_service

router = APIRouter(
    prefix="/papers",
    tags=["papers"],
    dependencies=[Depends(require_read_quota)],
)


@router.get("", response_model=PaperListResponse)
def papers(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    query: Annotated[str | None, Query(min_length=2, max_length=300)] = None,
    source: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    year: Annotated[int | None, Query(ge=1800, le=2200)] = None,
    geography: Annotated[
        Literal["puerto_rico", "united_states", "latam_caribbean", "global"] | None,
        Query(),
    ] = None,
    peer_reviewed: bool | None = None,
    open_access: bool | None = None,
    full_text: bool | None = None,
    evidence_type: Annotated[str | None, Query(min_length=2, max_length=50)] = None,
    retracted: bool | None = None,
    peer_review_status: Literal["CONFIRMED", "LIKELY", "UNKNOWN", "NOT_PEER_REVIEWED"] | None = None,
    access_status: Literal["OPEN_ACCESS", "INSTITUTIONAL_ACCESS", "PROVIDER_LOGIN", "PUBLISHER_ACCESS", "DOI_ONLY", "METADATA_ONLY", "UNKNOWN"] | None = None,
    retraction_status: Literal["RETRACTED", "EXPRESSION_OF_CONCERN", "CORRECTED", "UNKNOWN"] | None = None,
) -> PaperListResponse:
    items = paper_service.list_papers(
        limit=limit, offset=offset, query=query, source=source, year=year,
        geography=geography,
        peer_reviewed=peer_reviewed, open_access=open_access,
        full_text=full_text, evidence_type=evidence_type, retracted=retracted,
        peer_review_status=peer_review_status, access_status=access_status,
        retraction_status=retraction_status,
    )
    return PaperListResponse(items=items, limit=limit, offset=offset, count=len(items))


@router.get("/{paper_id:path}", response_model=PaperResponse)
def paper_detail(paper_id: str) -> dict:
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    return paper
