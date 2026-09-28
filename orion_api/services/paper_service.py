from __future__ import annotations

import data_store


TEXT_FIELDS = {
    "authors", "published_date", "source", "journal", "work_type", "doi", "url",
    "oa_url", "pdf_url", "abstract", "topics", "summary", "why_it_matters",
    "applications", "limitations", "evidence_level", "apa_citation",
}
INTEGER_FIELDS = {"year", "cited_by_count", "read_full", "favorite"}
FLOAT_FIELDS = {"relevance_score"}


def _normalize_paper(paper: dict) -> dict:
    normalized = dict(paper)
    normalized["id"] = str(normalized.get("id") or "")
    normalized["title"] = normalized.get("title") or "Sin título"
    for field in TEXT_FIELDS:
        normalized[field] = normalized.get(field) or ""
    for field in INTEGER_FIELDS:
        normalized[field] = int(normalized.get(field) or 0)
    for field in FLOAT_FIELDS:
        normalized[field] = float(normalized.get(field) or 0)
    return normalized


def list_papers(
    *,
    limit: int,
    offset: int,
    query: str | None = None,
    source: str | None = None,
    year: int | None = None,
    favorites_only: bool = False,
) -> list[dict]:
    papers = data_store.list_papers(
        limit=limit,
        offset=offset,
        query=query,
        source=source,
        year=year,
        favorites_only=favorites_only,
    )
    return [_normalize_paper(paper) for paper in papers]


def get_paper(paper_id: str) -> dict | None:
    paper = data_store.get_paper(paper_id)
    return _normalize_paper(paper) if paper else None


def update_favorite(paper_id: str, favorite: bool) -> dict | None:
    if data_store.get_paper(paper_id) is None:
        return None
    data_store.set_favorite(paper_id, favorite)
    return get_paper(paper_id)
