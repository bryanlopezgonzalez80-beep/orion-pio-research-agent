"""Bounded geographic discovery and transparent evidence classification."""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from data_store import upsert_papers
from orion_platform import execute_academic_search
from platform_store import get_setting, set_setting

STATE_PREFIX = "geographic_intelligence"


@dataclass(frozen=True)
class GeographicProfile:
    key: str
    label: str
    aliases: tuple[str, ...]
    priority: int


PUERTO_RICO = GeographicProfile(
    "puerto_rico",
    "Puerto Rico",
    (
        "puerto rico", "puerto rican", "puertorriqueno", "puertorriquena",
        "puertorriquenos", "puertorriquenas", "san juan puerto rico",
        "ponce puerto rico", "mayaguez puerto rico", "bayamon puerto rico",
        "caguas puerto rico", "carolina puerto rico", "guaynabo puerto rico",
        "arecibo puerto rico", "humacao puerto rico",
    ),
    0,
)
UNITED_STATES = GeographicProfile(
    "united_states",
    "United States",
    (
        "united states", "united states of america", "u.s.", "u.s.a.", "usa",
        "u.s. employees", "u.s. workers", "u.s. workforce",
        "us employees", "us workers", "us workforce", "american employees",
        "american workers", "american workforce", "us organizations",
        "empleados estadounidenses", "trabajadores estadounidenses",
        "organizaciones estadounidenses", "universidad estadounidense",
    ),
    1,
)
LATAM_CARIBBEAN = GeographicProfile(
    "latam_caribbean",
    "Latin America / Caribbean",
    (
        "latin america", "latinoamerica", "america latina", "caribbean",
        "caribe", "mexico", "colombia", "chile", "argentina", "brasil",
        "brazil", "costa rica", "republica dominicana", "dominican republic",
        "panama", "peru", "uruguay", "ecuador", "guatemala", "jamaica",
        "trinidad and tobago", "barbados",
    ),
    2,
)
GLOBAL = GeographicProfile(
    "global", "Global / International", ("global", "international", "multinational"), 3
)
GEOGRAPHIC_PROFILES = (PUERTO_RICO, UNITED_STATES, LATAM_CARIBBEAN, GLOBAL)

HIGH_VALUE_CONCEPTS = (
    "leadership", "organizational leadership", "employee engagement", "burnout",
    "occupational stress", "job satisfaction", "organizational commitment",
    "organizational climate", "organizational culture", "psychological safety",
    "employee wellbeing", "turnover", "retention", "recruitment",
    "employee selection", "performance management", "training",
    "training transfer", "organizational development", "organizational change",
    "team effectiveness", "work motivation", "work-family conflict", "remote work",
    "hybrid work", "diversity equity inclusion", "workplace discrimination",
    "occupational safety", "human factors", "HR analytics", "people analytics",
    "AI in HR", "automation", "future of work",
    "mental health", "anxiety", "depression", "suicide prevention",
    "psychological trauma", "disaster resilience", "community psychology",
    "clinical psychology", "counseling psychology", "school psychology",
    "health psychology", "neuropsychology", "psychological assessment",
    "psychometrics", "substance use", "gender violence", "family wellbeing",
    "child and adolescent psychology", "older adults caregivers",
    "LGBTQ mental health", "disability neurodiversity", "autism ADHD",
)
SPANISH_CONCEPTS = {
    "leadership": "liderazgo",
    "employee engagement": "compromiso laboral",
    "burnout": "agotamiento laboral",
    "occupational stress": "estrés ocupacional",
    "job satisfaction": "satisfacción laboral",
    "psychological safety": "seguridad psicológica",
    "employee wellbeing": "bienestar laboral",
    "turnover": "rotación de empleados",
    "training": "capacitación laboral",
    "organizational development": "desarrollo organizacional",
    "organizational change": "cambio organizacional",
    "work motivation": "motivación laboral",
    "workplace discrimination": "discriminación laboral",
    "mental health": "salud mental",
    "anxiety": "ansiedad",
    "depression": "depresión",
    "suicide prevention": "prevención del suicidio",
    "psychological trauma": "trauma psicológico",
    "disaster resilience": "resiliencia ante desastres",
    "community psychology": "psicología social comunitaria",
    "clinical psychology": "psicología clínica",
    "counseling psychology": "psicología de consejería",
    "school psychology": "psicología escolar",
    "health psychology": "psicología de la salud",
    "psychological assessment": "evaluación psicológica",
    "psychometrics": "psicometría",
    "substance use": "uso de sustancias",
}
PUERTO_RICO_JOURNALS = (
    "Revista Puertorriqueña de Psicología",
    "Revista Caribeña de Psicología",
    "Fórum Empresarial",
)
USA_STATE_GROUPS = (
    ("California", "Texas", "Florida", "New York", "Pennsylvania"),
    ("Illinois", "Ohio", "Georgia", "North Carolina", "Michigan"),
    ("New Jersey", "Virginia", "Washington", "Arizona", "Massachusetts"),
    ("Tennessee", "Indiana", "Maryland", "Missouri", "Wisconsin"),
    ("Colorado", "Minnesota", "South Carolina", "Alabama", "Louisiana"),
    ("Kentucky", "Oregon", "Oklahoma", "Connecticut", "Utah"),
    ("Iowa", "Nevada", "Arkansas", "Mississippi", "Kansas"),
    ("New Mexico", "Nebraska", "Idaho", "West Virginia", "Hawaii"),
    ("New Hampshire", "Maine", "Montana", "Rhode Island", "Delaware"),
    ("South Dakota", "North Dakota", "Alaska", "Vermont", "Wyoming"),
)
LATAM_GROUPS = (
    ("México", "Colombia", "Costa Rica", "Guatemala"),
    ("Chile", "Argentina", "Uruguay", "Perú"),
    ("Brasil", "Ecuador", "Panamá", "República Dominicana"),
    ("Jamaica", "Trinidad and Tobago", "Barbados", "Caribbean"),
)
DIRECTED_SOURCES = (
    {
        "name": "CONUCO",
        "mode": "directed_manual",
        "peer_reviewed_default": False,
        "url": "https://conuco.uprm.edu/",
    },
    {
        "name": "Repositorio Institucional UPR",
        "mode": "directed_manual",
        "peer_reviewed_default": False,
        "url": "https://repositorio.upr.edu/",
    },
    {"name": "Portal de Revistas Académicas UPR", "mode": "directed_manual", "peer_reviewed_default": False, "url": "https://revistas.upr.edu/"},
    {"name": "Psicología(s) UPR", "mode": "directed_manual", "peer_reviewed_default": True, "url": "https://revistas.upr.edu/index.php/psicologias"},
    {"name": "Revista Puertorriqueña de Psicología", "mode": "directed_manual", "peer_reviewed_default": True, "url": "https://www.repsasppr.net/"},
    {"name": "Revista Caribeña de Psicología", "mode": "directed_manual", "peer_reviewed_default": True, "url": "https://revistacaribenadepsicologia.com/"},
    {"name": "Tesis y Disertaciones Universidad Albizu", "mode": "directed_manual", "peer_reviewed_default": False, "url": "https://albizu411.com/au-ada/es/centro-institucional-de-investigacion-cientifica/tesis-y-disertaciones/"},
    {"name": "Tesis y Disertaciones PHSU", "mode": "directed_manual", "peer_reviewed_default": False, "url": "https://phsu.edu/library/thesis-and-dissertation.php"},
    {"name": "Observatorio de Salud Mental y Adicción PR", "mode": "directed_manual", "peer_reviewed_default": False, "url": "https://observatorio.assmca.pr.gov/"},
    {"name": "Biblioteca Virtual ASSMCA", "mode": "directed_manual", "peer_reviewed_default": False, "url": "https://www.assmca.pr.gov/originales/biblioteca-virtual"},
    {"name": "Comisión para la Prevención del Suicidio PR", "mode": "directed_manual", "peer_reviewed_default": False, "url": "https://prevencionsuicidio.salud.pr.gov/"},
)
DATA_INTELLIGENCE_SOURCES = (
    {"name": "O*NET", "kind": "workforce_taxonomy"},
    {"name": "Bureau of Labor Statistics", "kind": "labor_statistics"},
    {"name": "OPM FedScope / FEVS", "kind": "federal_workforce_data"},
    {"name": "NIOSH", "kind": "occupational_safety_data"},
)


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).casefold().split())


def _text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)
    return str(value or "")


def _matches(profile: GeographicProfile, value: object) -> bool:
    text = _fold(_text(value))
    if not text:
        return False
    return any(
        re.search(rf"(?<!\w){re.escape(_fold(alias))}(?!\w)", text)
        for alias in profile.aliases
    )


def _locations(value: object) -> list[str]:
    return [profile.label for profile in GEOGRAPHIC_PROFILES if _matches(profile, value)]


def _json_list(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except (TypeError, ValueError):
            return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return []


def _json_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def classify_geography(paper: dict) -> dict:
    """Classify geographic evidence without inferring study sample from affiliation."""
    evidence: dict[str, set[str]] = {}

    def add(value: object, basis: str) -> list[str]:
        found = _locations(value)
        for label in found:
            evidence.setdefault(label, set()).add(basis)
        return found

    sample_value = paper.get("sample_location") or paper.get("sample_locations")
    explicit_study_value = paper.get("study_location")
    provider = paper.get("provider_metadata") or {}
    if not sample_value and isinstance(provider, dict):
        sample_value = provider.get("sample_location")
    if not explicit_study_value and isinstance(provider, dict):
        explicit_study_value = provider.get("study_location")

    sample_locations = add(sample_value, "sample_explicit")
    study_locations = add(explicit_study_value, "study_location_explicit")
    affiliation_value = (
        paper.get("affiliations")
        or paper.get("author_affiliations")
        or paper.get("authorship_metadata")
        or paper.get("author_affiliation_location")
    )
    affiliation_locations = add(affiliation_value, "affiliation")
    publication_value = paper.get("publication_location") or " ".join(
        (_text(paper.get("journal")), _text(paper.get("source")))
    )
    publication_locations = add(publication_value, "publication_venue")
    mention_value = " ".join(
        _text(paper.get(field))
        for field in ("title", "abstract", "topics", "keywords")
    )
    mention_locations = add(mention_value, "title_or_abstract_mention")
    add(paper.get("matched_query"), "query_context")

    existing_basis = _json_dict(paper.get("geography_basis"))
    existing_tags = _json_list(paper.get("geography_tags"))
    for flag, label in (
        (paper.get("geo_pr"), PUERTO_RICO.label),
        (paper.get("geo_us"), UNITED_STATES.label),
        (paper.get("geo_latam_caribbean"), LATAM_CARIBBEAN.label),
    ):
        if flag and label not in existing_tags:
            existing_tags.append(label)
    for label in existing_tags:
        bases = existing_basis.get(label) or ["persisted_flag"]
        if not isinstance(bases, list):
            bases = [bases]
        evidence.setdefault(label, set()).update(str(value) for value in bases if value)

    basis_rank = {
        "sample_explicit": 0,
        "study_location_explicit": 1,
        "title_or_abstract_mention": 2,
        "query_context": 3,
        "affiliation": 4,
        "publication_venue": 5,
        "unknown": 6,
        "persisted_flag": 7,
    }
    profile_rank = {profile.label: profile.priority for profile in GEOGRAPHIC_PROFILES}
    tags = sorted(
        evidence,
        key=lambda label: (
            min(basis_rank.get(basis, 99) for basis in evidence[label]),
            profile_rank.get(label, 99),
        ),
    )
    primary = tags[0] if tags else ""
    primary_basis = (
        min(evidence[primary], key=lambda basis: basis_rank.get(basis, 99))
        if primary
        else "unknown"
    )
    confidence_by_basis = {
        "sample_explicit": 1.0,
        "study_location_explicit": 0.95,
        "title_or_abstract_mention": 0.7,
        "query_context": 0.5,
        "affiliation": 0.4,
        "publication_venue": 0.3,
        "unknown": 0.0,
        "persisted_flag": 0.0,
    }
    study_location = (sample_locations or study_locations)
    basis_payload = {
        label: sorted(bases, key=lambda basis: basis_rank.get(basis, 99))
        for label, bases in evidence.items()
    }
    return {
        "study_location": study_location[0] if study_location else "",
        "author_affiliation_location": (
            affiliation_locations[0] if affiliation_locations else ""
        ),
        "affiliation_locations": affiliation_locations,
        "publication_location": (
            publication_locations[0] if publication_locations else ""
        ),
        "geographic_mentions": mention_locations,
        "geography_primary": primary,
        "geography_tags": tags,
        "geography_confidence": confidence_by_basis[primary_basis],
        "geography_basis": basis_payload,
        "geo_pr": int(PUERTO_RICO.label in tags),
        "geo_us": int(UNITED_STATES.label in tags),
        "geo_latam_caribbean": int(LATAM_CARIBBEAN.label in tags),
    }


def classify_evidence_type(paper: dict) -> str:
    source = _fold(paper.get("source"))
    work_type = _fold(paper.get("work_type"))
    journal = _fold(paper.get("journal"))
    combined = f"{source} {work_type} {journal}"
    if "arxiv" in combined or "preprint" in combined:
        return "preprint"
    if any(term in combined for term in ("thesis", "dissertation")):
        return "thesis_dissertation"
    if any(term in combined for term in ("proceedings", "conference")):
        return "conference"
    if any(term in combined for term in ("government report", "technical report")):
        return "government_report"
    if "dataset" in combined:
        return "government_dataset" if "government" in combined else "unknown"
    if any(term in combined for term in ("siop", "tip", "white paper", "conuco")):
        return "professional_publication"
    if work_type in {"journal-article", "journal article", "article"}:
        return "journal_article"
    return "unknown"


def enrich_paper(paper: dict, *, matched_query: str | None = None) -> dict:
    enriched = dict(paper)
    if matched_query:
        enriched["matched_query"] = matched_query
    enriched.update(classify_geography(enriched))
    existing_type = str(enriched.get("evidence_type") or "").strip()
    enriched["evidence_type"] = (
        existing_type if existing_type and existing_type.casefold() != "unknown"
        else classify_evidence_type(enriched)
    )
    return enriched


def puerto_rico_queries() -> list[str]:
    queries = [f"{concept} Puerto Rico" for concept in HIGH_VALUE_CONCEPTS]
    queries.extend(f"{concept} Puerto Rican employees" for concept in HIGH_VALUE_CONCEPTS[::3])
    queries.extend(f"{spanish} Puerto Rico" for spanish in SPANISH_CONCEPTS.values())
    queries.extend(PUERTO_RICO_JOURNALS)
    return list(dict.fromkeys(queries))


def usa_queries(state_group_index: int = 0) -> list[str]:
    group = USA_STATE_GROUPS[state_group_index % len(USA_STATE_GROUPS)]
    queries = [f"{concept} United States employees" for concept in HIGH_VALUE_CONCEPTS]
    for state in group:
        queries.extend(f"{concept} employees {state}" for concept in HIGH_VALUE_CONCEPTS[::7])
    return list(dict.fromkeys(queries))


def latam_caribbean_queries(group_index: int = 0) -> list[str]:
    group = LATAM_GROUPS[group_index % len(LATAM_GROUPS)]
    concepts = HIGH_VALUE_CONCEPTS[::4]
    queries = [f"{concept} Latin America Caribbean" for concept in concepts]
    for location in group:
        queries.extend(f"{concept} {location}" for concept in concepts[:4])
    queries.extend(f"{spanish} América Latina" for spanish in tuple(SPANISH_CONCEPTS.values())[:5])
    queries.extend(("psicologia organizacional Brasil", "psicologia do trabalho Brasil"))
    return list(dict.fromkeys(queries))


def _subset(items: list[str], cursor: int, count: int) -> tuple[list[str], int]:
    if not items or count <= 0:
        return [], 0
    cursor %= len(items)
    count = min(count, len(items))
    return [items[(cursor + i) % len(items)] for i in range(count)], (cursor + count) % len(items)


def _budget(name: str, default: int, maximum: int = 100) -> int:
    try:
        return max(0, min(maximum, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def _sources() -> list[str]:
    sources = ["Crossref", "PubMed", "Europe PMC"]
    if os.getenv("OPENALEX_API_KEY"):
        sources.append("OpenAlex")
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
        sources.append("Semantic Scholar")
    return sources


def _source_metrics(total: dict[str, Counter], source_meta: Iterable[dict]) -> None:
    for meta in source_meta:
        bucket = total.setdefault(str(meta.get("source") or "unknown"), Counter())
        bucket["queries"] += 1
        bucket["results"] += int(meta.get("count") or 0)
        bucket["network_requests"] += int(meta.get("network_requests") or 0)
        bucket["retries"] += int(meta.get("retries") or 0)
        bucket["rate_limited_queries"] += int(bool(meta.get("rate_limited")))
        bucket["errors"] += int(meta.get("status") == "error")
        bucket["circuits_open"] += int(meta.get("status") == "circuit_open")


def run_geographic_booster(
    *,
    progress_callback: Callable[[dict], None] | None = None,
    max_runtime_seconds: int | None = None,
) -> dict:
    """Run bounded rotating geographic discovery; failures remain query-local."""
    started = time.monotonic()
    runtime = max_runtime_seconds if max_runtime_seconds is not None else _budget(
        "ORION_GEO_RUNTIME_SECONDS", 180, 1800
    )
    state_groups = {
        "united_states": int(get_setting(f"{STATE_PREFIX}.us_state_group", 0) or 0),
        "latam_caribbean": int(get_setting(f"{STATE_PREFIX}.latam_group", 0) or 0),
    }
    layers = (
        (PUERTO_RICO, puerto_rico_queries(), _budget("ORION_GEO_PR_QUERIES_PER_RUN", 6)),
        (UNITED_STATES, usa_queries(state_groups["united_states"]), _budget("ORION_GEO_US_QUERIES_PER_RUN", 4)),
        (LATAM_CARIBBEAN, latam_caribbean_queries(state_groups["latam_caribbean"]), _budget("ORION_GEO_LATAM_QUERIES_PER_RUN", 3)),
    )
    totals: dict[str, dict] = {}
    errors: list[str] = []
    source_totals: dict[str, Counter] = {}
    all_unique: set[str] = set()
    total_planned = sum(min(budget, len(queries)) for _, queries, budget in layers)
    overall_processed = 0

    def emit(profile: GeographicProfile) -> None:
        if progress_callback is None:
            return
        payload = {
            "geography_phase": profile.label,
            "geo_queries_processed": overall_processed,
            "geo_queries_total": total_planned,
            "geography_totals": totals,
        }
        try:
            progress_callback(payload)
        except Exception:
            pass

    for profile, queries, budget in layers:
        cursor_key = f"{STATE_PREFIX}.{profile.key}_cursor"
        cursor = int(get_setting(cursor_key, 0) or 0)
        selected, next_cursor = _subset(queries, cursor, budget)
        layer = {"queries_processed": 0, "received": 0, "unique_seen": 0, "errors": 0}
        layer_unique: set[str] = set()
        totals[profile.label] = layer
        for query in selected:
            if time.monotonic() - started >= runtime:
                break
            try:
                outcome = execute_academic_search(
                    query,
                    days=365,
                    per_source=15,
                    sources=_sources(),
                    max_keep=100,
                    retries=2,
                    cache_ttl_hours=12,
                    force_refresh=False,
                )
                papers = [enrich_paper(paper, matched_query=query) for paper in outcome.get("results") or []]
                if papers:
                    upsert_papers(papers)
                layer["received"] += int(outcome.get("received") or 0)
                for paper in papers:
                    if paper.get("id"):
                        layer_unique.add(str(paper["id"]))
                        all_unique.add(str(paper["id"]))
                _source_metrics(source_totals, outcome.get("source_meta") or [])
                for error in outcome.get("errors") or []:
                    errors.append(f"{profile.key}: provider incident")
                    layer["errors"] += 1
            except Exception as exc:
                errors.append(f"{profile.key}: {type(exc).__name__}")
                layer["errors"] += 1
            finally:
                layer["queries_processed"] += 1
                overall_processed += 1
                layer["unique_seen"] = len(layer_unique)
                emit(profile)
        advanced = layer["queries_processed"]
        persisted_cursor = (cursor + advanced) % len(queries) if queries else next_cursor
        set_setting(cursor_key, persisted_cursor)

    if totals.get(UNITED_STATES.label, {}).get("queries_processed"):
        set_setting(
            f"{STATE_PREFIX}.us_state_group",
            (state_groups["united_states"] + 1) % len(USA_STATE_GROUPS),
        )
    if totals.get(LATAM_CARIBBEAN.label, {}).get("queries_processed"):
        set_setting(
            f"{STATE_PREFIX}.latam_group",
            (state_groups["latam_caribbean"] + 1) % len(LATAM_GROUPS),
        )
    result = {
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "queries_processed": overall_processed,
        "queries_total": total_planned,
        "received": sum(item["received"] for item in totals.values()),
        "unique_seen": len(all_unique),
        "geography_totals": totals,
        "source_totals": {name: dict(values) for name, values in source_totals.items()},
        "partial_source_incidents": len(errors),
        "errors": errors,
        "directed_sources": list(DIRECTED_SOURCES),
    }
    set_setting(f"{STATE_PREFIX}.last_refresh", result)
    return result


def geography_status() -> dict:
    last = get_setting(f"{STATE_PREFIX}.last_refresh") or {}
    return {
        "coverage": {
            "Puerto Rico": len(puerto_rico_queries()),
            "United States": len(usa_queries()),
            "Latin America / Caribbean": len(latam_caribbean_queries()),
        },
        "last_geographic_refresh": last.get("completed_at"),
        "rotation_cursors": {
            profile.key: int(get_setting(f"{STATE_PREFIX}.{profile.key}_cursor", 0) or 0)
            for profile in (PUERTO_RICO, UNITED_STATES, LATAM_CARIBBEAN)
        }
        | {
            "us_state_group": int(get_setting(f"{STATE_PREFIX}.us_state_group", 0) or 0),
            "latam_group": int(get_setting(f"{STATE_PREFIX}.latam_group", 0) or 0),
        },
        "results_discovered": int(last.get("received") or 0),
        "unique_results_seen": int(last.get("unique_seen") or 0),
        "partial_source_incidents": int(last.get("partial_source_incidents") or 0),
        "totals": last.get("geography_totals") or {},
        "directed_sources": list(DIRECTED_SOURCES),
    }
