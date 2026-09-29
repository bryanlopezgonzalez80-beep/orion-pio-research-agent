from __future__ import annotations

from orion_platform import source_configuration
from platform_store import get_source_health
from research_agent import source_rate_policy
from source_registry import source_registry


def list_public_sources() -> list[dict]:
    health = {row["source"]: row for row in get_source_health()}
    registry = {item.source_name: item for item in source_registry().values()}
    public = []
    for source in source_configuration():
        known = health.get(source["name"], {})
        definition = registry.get(source["name"])
        policy = source_rate_policy(source["name"])
        public.append(
            {
                "name": source["name"],
                "domain": source["domain"],
                "authority": source["authority"],
                "automated": source["automated"],
                "free_access": source["free_access"],
                "official_url": source["official_url"],
                "status": known.get("last_status", "unknown"),
                "last_checked": known.get("last_checked"),
                "minimum_interval_seconds": policy["minimum_interval_seconds"],
                "rate_guidance": policy["guidance"],
                "source_id": definition.source_id if definition else source["name"].casefold().replace(" ", "_"),
                "source_type": [value.value for value in definition.source_type] if definition else [],
                "discovery_enabled": bool(definition and definition.discovery_enabled),
                "enrichment_enabled": bool(definition and definition.enrichment_enabled),
                "citation_graph_enabled": bool(definition and definition.citation_graph_enabled),
                "fulltext_enabled": bool(definition and definition.fulltext_enabled),
                "access_mode": definition.access_mode if definition else "metadata",
                "authentication_required": bool(definition and definition.authentication_required),
                "api_configured": bool(definition and definition.api_configured),
                "license_required": bool(definition and definition.license_required),
                "peer_review_information_available": bool(definition and definition.peer_review_information_available),
                "geographic_strength": definition.geographic_strength if definition else "global",
                "health_status": definition.health_status.value if definition else "INACTIVE",
            }
        )
    known_names = {item["name"] for item in public}
    for definition in registry.values():
        if definition.source_name in known_names:
            continue
        item = definition.public_dict()
        public.append({
            "name": definition.source_name, "domain": "academic",
            "authority": "provider", "automated": definition.discovery_enabled,
            "free_access": not definition.license_required,
            "official_url": "", "status": definition.health_status.value.casefold(),
            "last_checked": None, "minimum_interval_seconds": 0.0,
            "rate_guidance": definition.rate_limit_policy, **item,
        })
    return public
