"""Canonical identity and provenance helpers for multi-source evidence."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable

from access_resolver import resolve_access
from evidence_integrity import assess_integrity
from geographic_intelligence import enrich_paper


def normalize_doi(value: object) -> str:
    doi = str(value or "").strip().casefold()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.rstrip(". ,")


def external_ids(paper: dict) -> dict[str, str]:
    aliases = {
        "doi": normalize_doi(paper.get("doi")),
        "pmid": str(paper.get("pmid") or "").strip(),
        "pmcid": str(paper.get("pmcid") or "").strip(),
        "openalex": str(paper.get("openalex_id") or "").strip(),
        "semantic_scholar": str(paper.get("semantic_scholar_id") or "").strip(),
        "publisher": str(paper.get("publisher_id") or "").strip(),
    }
    return {key: value for key, value in aliases.items() if value}


def canonical_key(paper: dict) -> str:
    ids = external_ids(paper)
    for kind in ("doi", "pmid", "pmcid", "openalex", "semantic_scholar", "publisher"):
        if ids.get(kind):
            return f"{kind}:{ids[kind].casefold()}"
    title = unicodedata.normalize("NFKD", str(paper.get("title") or "")).encode("ascii", "ignore").decode().casefold()
    title = " ".join(re.findall(r"[a-z0-9]+", title))
    authors = str(paper.get("authors") or "").casefold().split(",")[0].strip()
    year = str(paper.get("year") or "").strip()
    digest = hashlib.sha256(f"{title}|{authors}|{year}".encode()).hexdigest()[:24]
    return f"metadata:{digest}"


def merge_records(records: Iterable[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[canonical_key(record)].append(dict(record))
    merged: list[dict] = []
    for key, candidates in grouped.items():
        candidates.sort(key=lambda item: len(str(item.get("abstract") or "")), reverse=True)
        paper = dict(candidates[0])
        provenance: dict[str, list[str]] = defaultdict(list)
        combined_ids: dict[str, str] = {}
        for candidate in candidates:
            source = str(candidate.get("source") or candidate.get("discovered_via") or "unknown")
            combined_ids.update(external_ids(candidate))
            for field, value in candidate.items():
                if value not in (None, "", [], {}):
                    provenance[field].append(source)
                    current = paper.get(field)
                    if current in (None, "", [], {}) or len(str(value)) > len(str(current)):
                        paper[field] = value
        paper["id"] = paper.get("id") or key
        paper["paper_external_ids"] = combined_ids
        paper["metadata_sources_count"] = len({s for values in provenance.values() for s in values})
        paper["metadata_provenance"] = {field: sorted(set(sources)) for field, sources in provenance.items()}
        merged.append(paper)
    return merged


def enrich_record(paper: dict, *, institution: dict | None = None) -> dict:
    enriched = enrich_paper(dict(paper))
    enriched.update(assess_integrity(enriched))
    access = resolve_access(enriched, institution=institution)
    enriched.update(access)
    enriched["access_provider"] = access.get("provider") or ""
    enriched["metadata_provenance"] = enriched.get("metadata_provenance") or {}
    enriched["paper_external_ids"] = enriched.get("paper_external_ids") or external_ids(enriched)
    for field in ("metadata_provenance", "paper_external_ids", "evidence_flags", "journal_validation_sources", "alternative_access_options"):
        if isinstance(enriched.get(field), (dict, list)):
            enriched[field] = json.loads(json.dumps(enriched[field], ensure_ascii=False))
    return enriched
