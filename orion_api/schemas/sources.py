from pydantic import BaseModel


class SourceResponse(BaseModel):
    name: str
    domain: str
    authority: str
    automated: bool
    free_access: bool
    official_url: str = ""
    status: str = "unknown"
    last_checked: str | None = None
    minimum_interval_seconds: float = 0.0
    rate_guidance: str = ""
    source_id: str = ""
    source_type: list[str] = []
    discovery_enabled: bool = False
    enrichment_enabled: bool = False
    citation_graph_enabled: bool = False
    fulltext_enabled: bool = False
    access_mode: str = "metadata"
    authentication_required: bool = False
    api_configured: bool = False
    license_required: bool = False
    peer_review_information_available: bool = False
    geographic_strength: str = "global"
    health_status: str = "INACTIVE"
