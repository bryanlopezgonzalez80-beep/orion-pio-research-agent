"""Central, declarative registry for Orion evidence providers.

The registry describes capability and configuration. It never contains secrets
and does not imply that a provider is licensed, reachable, or peer reviewed.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from enum import Enum


class SourceType(str, Enum):
    DISCOVERY = "DISCOVERY"
    ENRICHMENT = "ENRICHMENT"
    CITATION_GRAPH = "CITATION_GRAPH"
    FULLTEXT = "FULLTEXT"
    VALIDATION = "VALIDATION"
    ACCESS_PROVIDER = "ACCESS_PROVIDER"
    REGIONAL = "REGIONAL"
    DATA_SOURCE = "DATA_SOURCE"


class SourceHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    INACTIVE = "INACTIVE"


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    source_name: str
    source_type: tuple[SourceType, ...]
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
    rate_limit_policy: str = "provider-default"
    last_success: str | None = None
    last_error: str | None = None
    health_status: SourceHealth = SourceHealth.HEALTHY
    registered: bool = True
    implemented: bool = False
    configured: bool = False
    authorized: bool = True
    active: bool = False

    def public_dict(self) -> dict:
        value = asdict(self)
        value["source_type"] = [item.value for item in self.source_type]
        value["health_status"] = self.health_status.value
        return value


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _premium(source_id: str, name: str, env_prefix: str) -> SourceDefinition:
    enabled = _enabled(f"{env_prefix}_API_ENABLED")
    configured = bool(os.getenv(f"{env_prefix}_API_KEY"))
    authorized = _enabled(f"{env_prefix}_API_AUTHORIZED")
    active = False  # Registry/access stub only; no licensed harvesting adapter yet.
    health = (
        SourceHealth.AUTH_REQUIRED if enabled and not configured
        else SourceHealth.LICENSE_REQUIRED if enabled and not authorized
        else SourceHealth.INACTIVE
    )
    return SourceDefinition(
        source_id, name, (SourceType.ACCESS_PROVIDER, SourceType.DISCOVERY),
        discovery_enabled=active, access_mode="licensed-provider",
        authentication_required=True, api_configured=configured,
        license_required=True, peer_review_information_available=True,
        health_status=health, implemented=False, configured=configured,
        authorized=authorized, active=active,
    )


def source_registry() -> dict[str, SourceDefinition]:
    openalex_configured = bool(os.getenv("OPENALEX_API_KEY"))
    semantic_configured = bool(os.getenv("SEMANTIC_SCHOLAR_API_KEY"))
    core_configured = bool(os.getenv("CORE_API_KEY"))
    sources = [
        SourceDefinition("crossref", "Crossref", (SourceType.DISCOVERY, SourceType.ENRICHMENT, SourceType.VALIDATION), True, True, api_configured=True, rate_limit_policy="polite-adaptive", implemented=True, configured=True, active=True),
        SourceDefinition("openalex", "OpenAlex", (SourceType.DISCOVERY, SourceType.ENRICHMENT, SourceType.CITATION_GRAPH, SourceType.FULLTEXT), True, True, True, True, api_configured=True, rate_limit_policy="optional-key-adaptive", implemented=True, configured=openalex_configured, active=True),
        SourceDefinition("semantic_scholar", "Semantic Scholar", (SourceType.ENRICHMENT, SourceType.CITATION_GRAPH), enrichment_enabled=True, citation_graph_enabled=True, authentication_required=False, api_configured=True, rate_limit_policy="optional-key-adaptive", implemented=True, configured=semantic_configured, active=True),
        SourceDefinition("pubmed", "PubMed", (SourceType.DISCOVERY, SourceType.ENRICHMENT, SourceType.VALIDATION), True, True, api_configured=True, peer_review_information_available=True, geographic_strength="occupational-health", implemented=True, configured=True, active=True),
        SourceDefinition("europe_pmc", "Europe PMC", (SourceType.DISCOVERY, SourceType.ENRICHMENT, SourceType.FULLTEXT), True, True, fulltext_enabled=True, access_mode="open-access", api_configured=True, implemented=True, configured=True, active=True),
        SourceDefinition("core", "CORE", (SourceType.ENRICHMENT, SourceType.FULLTEXT), authentication_required=True, api_configured=core_configured, access_mode="open-access-repository", health_status=SourceHealth.INACTIVE, configured=core_configured),
        SourceDefinition("doaj", "DOAJ", (SourceType.VALIDATION, SourceType.FULLTEXT), access_mode="open-access", peer_review_information_available=True),
        SourceDefinition("datacite", "DataCite", (SourceType.DISCOVERY, SourceType.ENRICHMENT, SourceType.DATA_SOURCE)),
        SourceDefinition("eric", "ERIC", (SourceType.DISCOVERY, SourceType.ENRICHMENT), geographic_strength="education-and-training"),
        SourceDefinition("arxiv", "arXiv", (SourceType.DISCOVERY, SourceType.FULLTEXT), True, fulltext_enabled=True, access_mode="preprint-open-access", api_configured=True, peer_review_information_available=False, implemented=True, configured=True, active=True),
        SourceDefinition("scielo", "SciELO", (SourceType.DISCOVERY, SourceType.REGIONAL, SourceType.FULLTEXT), access_mode="directed-open-access", geographic_strength="latam-caribbean"),
        SourceDefinition("redalyc", "Redalyc", (SourceType.REGIONAL, SourceType.ACCESS_PROVIDER), access_mode="authorized-manual", geographic_strength="latam-caribbean"),
        SourceDefinition("latindex", "Latindex", (SourceType.REGIONAL, SourceType.VALIDATION), access_mode="directory", geographic_strength="latam-caribbean"),
        _premium("psycinfo", "APA PsycInfo", "PSYCINFO"),
        _premium("scopus", "Scopus", "SCOPUS"),
        _premium("web_of_science", "Web of Science", "WOS"),
        _premium("proquest", "ProQuest", "PROQUEST"),
    ]
    return {source.source_id: source for source in sources}


def public_source_registry() -> list[dict]:
    return [item.public_dict() for item in source_registry().values()]
