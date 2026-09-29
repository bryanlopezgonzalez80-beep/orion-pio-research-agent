"""Transparent evidence-integrity indicators; intentionally no opaque score."""
from __future__ import annotations

import re

PEER_REVIEW_STATES = {"CONFIRMED", "LIKELY", "UNKNOWN", "NOT_PEER_REVIEWED"}
EVIDENCE_TYPES = {
    "META_ANALYSIS", "SYSTEMATIC_REVIEW", "RANDOMIZED_TRIAL", "LONGITUDINAL",
    "QUASI_EXPERIMENTAL", "CROSS_SECTIONAL", "QUALITATIVE", "CASE_STUDY",
    "REVIEW", "THEORETICAL", "PREPRINT", "THESIS", "UNKNOWN",
}


def classify_evidence_type(paper: dict) -> str:
    text = " ".join(str(paper.get(k) or "") for k in ("title", "abstract", "work_type")).casefold()
    patterns = (
        ("META_ANALYSIS", r"meta[- ]analys"), ("SYSTEMATIC_REVIEW", r"systematic review"),
        ("RANDOMIZED_TRIAL", r"randomi[sz]ed(?: controlled)? trial"),
        ("LONGITUDINAL", r"longitudinal|prospective cohort"),
        ("QUASI_EXPERIMENTAL", r"quasi[- ]experiment"),
        ("CROSS_SECTIONAL", r"cross[- ]sectional"), ("QUALITATIVE", r"qualitative"),
        ("CASE_STUDY", r"case stud"), ("PREPRINT", r"preprint|arxiv"),
        ("THESIS", r"thesis|dissertation"), ("REVIEW", r"\breview\b"),
        ("THEORETICAL", r"theoretical|conceptual paper"),
    )
    return next((label for label, pattern in patterns if re.search(pattern, text)), "UNKNOWN")


def assess_integrity(paper: dict) -> dict:
    source = str(paper.get("source") or "").casefold()
    work_type = str(paper.get("work_type") or "").casefold()
    explicit = str(paper.get("peer_review_status") or "").upper()
    if explicit in PEER_REVIEW_STATES:
        peer_review = explicit
    elif "arxiv" in source or "preprint" in work_type:
        peer_review = "NOT_PEER_REVIEWED"
    elif paper.get("peer_review_confirmed") is True:
        peer_review = "CONFIRMED"
    else:
        peer_review = "UNKNOWN"  # A DOI or index membership is not proof.
    retraction = str(paper.get("retraction_status") or "UNKNOWN").upper()
    correction = str(paper.get("correction_status") or "UNKNOWN").upper()
    flags = list(paper.get("evidence_flags") or [])
    if retraction in {"RETRACTED", "EXPRESSION_OF_CONCERN"}:
        flags.append(retraction)
    return {
        "peer_review_status": peer_review,
        "publication_type": str(paper.get("publication_type") or paper.get("work_type") or ""),
        "retraction_status": retraction,
        "correction_status": correction,
        "doi_verified": bool(paper.get("doi_verified")),
        "metadata_sources_count": max(1, int(paper.get("metadata_sources_count") or 1)),
        "abstract_available": bool(paper.get("abstract")),
        "fulltext_available": bool(paper.get("fulltext_available") or paper.get("pdf_url")),
        "journal_validation_sources": list(paper.get("journal_validation_sources") or []),
        "study_design": classify_evidence_type(paper),
        "evidence_flags": sorted(set(flags)),
    }
