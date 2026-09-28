from __future__ import annotations

from orion_platform import source_configuration
from platform_store import get_source_health
from research_agent import source_rate_policy


def list_public_sources() -> list[dict]:
    health = {row["source"]: row for row in get_source_health()}
    public = []
    for source in source_configuration():
        known = health.get(source["name"], {})
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
            }
        )
    return public
