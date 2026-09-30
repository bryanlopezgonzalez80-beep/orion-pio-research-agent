from __future__ import annotations

import json

import data_store


TEXT_FIELDS = {
    "authors", "published_date", "source", "journal", "work_type", "doi", "url",
    "oa_url", "pdf_url", "abstract", "topics", "summary", "why_it_matters",
    "applications", "limitations", "evidence_level", "apa_citation",
    "evidence_type", "geography_primary", "study_location",
    "author_affiliation_location", "publication_location",
    "peer_review_status", "publication_type", "retraction_status",
    "correction_status", "access_status", "best_access_url", "access_provider",
    "access_type", "doi_url", "language",
}
LIST_FIELDS = {"geography_tags", "affiliation_locations", "geographic_mentions", "evidence_flags", "alternative_access_options"}
INTEGER_FIELDS = {"year", "cited_by_count", "read_full", "favorite", "geo_pr", "geo_us", "geo_latam_caribbean", "doi_verified", "metadata_sources_count", "abstract_available", "requires_login", "institutional_access_possible", "open_access", "pdf_available", "html_available", "fulltext_available"}
FLOAT_FIELDS = {"relevance_score", "topic_relevance_percent", "geography_confidence"}


def _normalize_paper(paper: dict) -> dict:
    normalized = dict(paper)
    normalized["id"] = str(normalized.get("id") or "")
    normalized["title"] = normalized.get("title") or "Sin título"
    for field in TEXT_FIELDS:
        normalized[field] = normalized.get(field) or ""
    for field in ("evidence_type", "peer_review_status", "retraction_status", "correction_status", "access_status"):
        normalized[field] = normalized.get(field) or "UNKNOWN"
    for field in INTEGER_FIELDS:
        normalized[field] = int(normalized.get(field) or 0)
    for field in FLOAT_FIELDS:
        normalized[field] = float(normalized.get(field) or 0)
    for field in LIST_FIELDS:
        value = normalized.get(field)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                value = []
        normalized[field] = value if isinstance(value, list) else []
    basis = normalized.get("geography_basis")
    if isinstance(basis, str):
        try:
            basis = json.loads(basis)
        except (TypeError, ValueError):
            basis = {}
    normalized["geography_basis"] = basis if isinstance(basis, dict) else {}
    provenance = normalized.get("metadata_provenance")
    if isinstance(provenance, str):
        try:
            provenance = json.loads(provenance)
        except (TypeError, ValueError):
            provenance = {}
    normalized["metadata_provenance"] = provenance if isinstance(provenance, dict) else {}
    return normalized


def list_papers(
    *,
    limit: int,
    offset: int,
    query: str | None = None,
    source: str | None = None,
    year: int | None = None,
    favorites_only: bool = False,
    geography: str | None = None,
    peer_reviewed: bool | None = None,
    open_access: bool | None = None,
    full_text: bool | None = None,
    evidence_type: str | None = None,
    retracted: bool | None = None,
    peer_review_status: str | None = None,
    access_status: str | None = None,
    retraction_status: str | None = None,
) -> list[dict]:
    papers = data_store.list_papers(
        limit=limit,
        offset=offset,
        query=query,
        source=source,
        year=year,
        favorites_only=favorites_only,
        geography=geography,
        peer_reviewed=peer_reviewed,
        open_access=open_access,
        full_text=full_text,
        evidence_type=evidence_type,
        retracted=retracted,
        peer_review_status=peer_review_status,
        access_status=access_status,
        retraction_status=retraction_status,
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
