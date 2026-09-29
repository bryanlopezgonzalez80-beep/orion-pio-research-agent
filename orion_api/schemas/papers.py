from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PaperResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    authors: str = ""
    year: int = 0
    published_date: str = ""
    source: str = ""
    journal: str = ""
    work_type: str = ""
    doi: str = ""
    url: str = ""
    oa_url: str = ""
    pdf_url: str = ""
    abstract: str = ""
    topics: str = ""
    cited_by_count: int = 0
    relevance_score: float = 0
    summary: str = ""
    why_it_matters: str = ""
    applications: str = ""
    limitations: str = ""
    evidence_level: str = ""
    evidence_type: str = ""
    peer_review_status: str = "UNKNOWN"
    publication_type: str = ""
    retraction_status: str = "UNKNOWN"
    correction_status: str = "UNKNOWN"
    doi_verified: int = 0
    metadata_sources_count: int = 1
    metadata_provenance: dict[str, Any] = Field(default_factory=dict)
    evidence_flags: list[str] = Field(default_factory=list)
    abstract_available: int = 0
    apa_citation: str = ""
    geography_primary: str = ""
    geography_tags: list[str] = Field(default_factory=list)
    geography_confidence: float = 0
    geography_basis: dict[str, list[str]] = Field(default_factory=dict)
    study_location: str = ""
    author_affiliation_location: str = ""
    affiliation_locations: list[str] = Field(default_factory=list)
    publication_location: str = ""
    geographic_mentions: list[str] = Field(default_factory=list)
    geo_pr: int = 0
    geo_us: int = 0
    geo_latam_caribbean: int = 0
    access_status: str = "UNKNOWN"
    best_access_url: str = ""
    access_provider: str = ""
    access_type: str = ""
    requires_login: int = 0
    institutional_access_possible: int = 0
    open_access: int = 0
    pdf_available: int = 0
    html_available: int = 0
    doi_url: str = ""
    alternative_access_options: list[dict[str, Any]] = Field(default_factory=list)
    fulltext_available: int = 0
    read_full: int = 0
    favorite: int = 0


class PaperListResponse(BaseModel):
    items: list[PaperResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
