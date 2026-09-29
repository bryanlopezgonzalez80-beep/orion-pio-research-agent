from __future__ import annotations

import html
import json
import math
import os
import re
import time
from collections import Counter
from threading import Lock
from datetime import date, datetime, timedelta
from typing import Iterable
from urllib.parse import quote

import requests
from dotenv import load_dotenv

try:
    import feedparser
except Exception:
    feedparser = None

load_dotenv()

APP_VERSION = "3.0.0"
USER_AGENT = "PIO-Intelligence-Hub/2.0 (research dashboard; personal use)"
TIMEOUT = 25

_SOURCE_PACING_LOCK = Lock()
_SOURCE_NEXT_REQUEST_AT: dict[str, float] = {}


def source_rate_policy(source: str) -> dict:
    """Return conservative provider pacing guidance used by Orion."""
    if source == "OpenAlex":
        return {
            "minimum_interval_seconds": 0.0,
            "guidance": (
                "Daily usage budget; a free API key increases the budget substantially. "
                "Responses expose remaining usage through rate-limit headers."
            ),
        }
    if source == "Crossref":
        polite = bool(os.getenv("CROSSREF_EMAIL"))
        return {
            "minimum_interval_seconds": (1.0 / 3.0) if polite else 1.0,
            "guidance": (
                "Polite pool: up to 3 list requests/second when mailto is configured."
                if polite
                else "Public pool: up to 1 list request/second; configure CROSSREF_EMAIL for the polite pool."
            ),
        }
    if source == "Semantic Scholar":
        return {
            "minimum_interval_seconds": 1.0,
            "guidance": "API-key users start at 1 request/second; unauthenticated access may be throttled.",
        }
    if source == "PubMed":
        keyed = bool(os.getenv("NCBI_API_KEY"))
        return {
            "minimum_interval_seconds": 0.1 if keyed else (1.0 / 3.0),
            "guidance": (
                "NCBI E-utilities: up to 10 requests/second with an API key."
                if keyed
                else "NCBI E-utilities: keep at or below 3 requests/second without an API key."
            ),
        }
    if source == "arXiv":
        return {
            "minimum_interval_seconds": 3.0,
            "guidance": "Legacy API guidance: no more than one request every 3 seconds and one connection at a time.",
        }
    if source == "Europe PMC":
        return {
            "minimum_interval_seconds": 0.25,
            "guidance": "No fixed public numeric quota is documented; Orion uses conservative pacing and backs off on 429 responses.",
        }
    return {
        "minimum_interval_seconds": 0.0,
        "guidance": "No automated provider quota applies.",
    }


def pace_source_request(
    source: str,
    *,
    sleep_fn=time.sleep,
    clock=time.monotonic,
) -> float:
    """Reserve a process-wide request slot for a provider and sleep if needed."""
    interval = float(source_rate_policy(source)["minimum_interval_seconds"])
    if interval <= 0:
        return 0.0
    with _SOURCE_PACING_LOCK:
        now = clock()
        scheduled = max(now, _SOURCE_NEXT_REQUEST_AT.get(source, now))
        wait = max(0.0, scheduled - now)
        _SOURCE_NEXT_REQUEST_AT[source] = scheduled + interval
    if wait > 0:
        sleep_fn(wait)
    return wait


SOURCE_LABELS = {
    "OpenAlex": "OpenAlex",
    "Crossref": "Crossref",
    "Europe PMC": "Europe PMC",
    "PubMed": "PubMed / NCBI",
    "Semantic Scholar": "Semantic Scholar",
    "arXiv": "arXiv",
}

DEFAULT_SOURCES = list(SOURCE_LABELS)
DEFAULT_TOPICS = [
    "industrial organizational psychology",
    "leadership effectiveness",
    "organizational development",
    "employee engagement",
    "training and development workplace",
    "organizational change",
    "workplace wellbeing",
    "team effectiveness",
    "psychological safety workplace",
    "talent management",
    "performance management",
    "employee selection assessment",
    "organizational culture",
    "hybrid work remote work",
    "AI human resources workplace",
]

STOPWORDS = {
    "the","and","for","with","from","that","this","into","among","using","work","study","effects","effect",
    "between","through","based","their","employee","employees","organizational","organization","workplace",
    "research","analysis","role","evidence","toward","towards","across","within","sobre","para","con","del","las","los"
}

PRACTICAL_TERMS = {
    "training": 1.2, "intervention": 1.3, "leadership": 1.1, "coaching": 1.2, "team": 0.8,
    "performance": 0.9, "engagement": 1.0, "change": 0.9, "development": 0.8, "selection": 0.9,
    "assessment": 0.9, "implementation": 1.2, "meta-analysis": 1.3, "systematic review": 1.3,
    "experiment": 0.8, "randomized": 1.0, "longitudinal": 0.8, "validation": 0.8, "wellbeing": 0.8,
    "psychological safety": 1.0, "culture": 0.7, "learning": 0.7, "turnover": 0.8, "retention": 0.8,
}


def _get(url: str, *, params=None, headers=None):
    h = {"User-Agent": USER_AGENT, "Accept": "application/json, text/xml, application/atom+xml;q=0.9, */*;q=0.8"}
    if headers:
        h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(x) for x in value if x)
    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_doi(doi: str) -> str:
    doi = (doi or "").strip().lower()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "")
    return doi.strip()


def stable_id(source: str, native_id: str = "", doi: str = "", title: str = "") -> str:
    d = normalize_doi(doi)
    if d:
        return f"doi:{d}"
    n = (native_id or "").strip()
    if n:
        return f"{source.lower().replace(' ','_')}:{n}"
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:160]
    return f"title:{slug}"


def parse_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        m = re.search(r"\d{4}-\d{2}-\d{2}", value)
        if m:
            return m.group(0)
        m = re.search(r"\d{4}", value)
        if m:
            return f"{m.group(0)}-01-01"
    if isinstance(value, (list, tuple)) and value:
        vals = list(value) + [1, 1]
        try:
            return f"{int(vals[0]):04d}-{int(vals[1]):02d}-{int(vals[2]):02d}"
        except Exception:
            return ""
    return ""


def apa_fallback(p: dict) -> str:
    authors = p.get("authors") or "Autor no disponible"
    year = p.get("year") or (p.get("published_date") or "")[:4] or "s. f."
    title = p.get("title") or "Sin título"
    journal = p.get("journal") or p.get("source") or "Fuente no disponible"
    doi = normalize_doi(p.get("doi") or "")
    tail = f" https://doi.org/{doi}" if doi else (f" {p.get('url')}" if p.get("url") else "")
    return f"{authors} ({year}). {title}. {journal}.{tail}".strip()


QUERY_STOPWORDS = {
    "the","and","for","with","from","into","among","using","study","research","analysis",
    "about","sobre","para","con","una","uno","del","las","los","and","of","in","on","to"
}

QUERY_ALIASES = {
    "organizational justice": ["organizational justice", "workplace fairness", "procedural justice", "distributive justice", "interactional justice"],
    "employee burnout": ["employee burnout", "occupational burnout", "job burnout", "emotional exhaustion"],
    "succession planning": ["succession planning", "succession management", "leadership succession"],
    "psychological safety": ["psychological safety", "team psychological safety", "interpersonal risk"],
    "training transfer": ["training transfer", "transfer of training", "learning transfer", "transfer of learning"],
}

# Deterministic Spanish -> English expansion for common PIO / HR concepts.
# Orion always keeps the original Spanish query and adds at most one English
# variant so Spanish-language results remain discoverable while English-heavy
# scholarly indexes return stronger coverage.
SPANISH_ACADEMIC_PHRASES = (
    ("psicología industrial organizacional", "industrial organizational psychology"),
    ("psicologia industrial organizacional", "industrial organizational psychology"),
    ("desarrollo organizacional", "organizational development"),
    ("cambio organizacional", "organizational change"),
    ("cultura organizacional", "organizational culture"),
    ("clima organizacional", "organizational climate"),
    ("clima laboral", "organizational climate"),
    ("seguridad psicológica", "psychological safety"),
    ("seguridad psicologica", "psychological safety"),
    ("compromiso de los empleados", "employee engagement"),
    ("compromiso laboral", "employee engagement"),
    ("bienestar laboral", "workplace wellbeing"),
    ("agotamiento laboral", "employee burnout"),
    ("estrés laboral", "occupational stress"),
    ("estres laboral", "occupational stress"),
    ("satisfacción laboral", "job satisfaction"),
    ("satisfaccion laboral", "job satisfaction"),
    ("desempeño laboral", "job performance"),
    ("desempeno laboral", "job performance"),
    ("evaluación del desempeño", "performance management"),
    ("evaluacion del desempeño", "performance management"),
    ("evaluacion del desempeno", "performance management"),
    ("gestión del talento", "talent management"),
    ("gestion del talento", "talent management"),
    ("manejo del talento", "talent management"),
    ("selección de personal", "employee selection"),
    ("seleccion de personal", "employee selection"),
    ("retención de empleados", "employee retention"),
    ("retencion de empleados", "employee retention"),
    ("rotación de personal", "employee turnover"),
    ("rotacion de personal", "employee turnover"),
    ("transferencia de capacitación", "training transfer"),
    ("transferencia de capacitacion", "training transfer"),
    ("transferencia del aprendizaje", "learning transfer"),
    ("trabajo híbrido", "hybrid work"),
    ("trabajo hibrido", "hybrid work"),
    ("trabajo remoto", "remote work"),
    ("trabajo en equipo", "team effectiveness"),
    ("efectividad de equipos", "team effectiveness"),
    ("eficacia de equipos", "team effectiveness"),
    ("justicia organizacional", "organizational justice"),
    ("aprendizaje organizacional", "organizational learning"),
    ("innovación organizacional", "organizational innovation"),
    ("innovacion organizacional", "organizational innovation"),
    ("motivación laboral", "work motivation"),
    ("motivacion laboral", "work motivation"),
    ("coaching ejecutivo", "executive coaching"),
    ("planificación de sucesión", "succession planning"),
    ("planificacion de sucesion", "succession planning"),
    ("inteligencia artificial en recursos humanos", "artificial intelligence human resources workplace"),
    ("recursos humanos", "human resources"),
    ("liderazgo transformacional", "transformational leadership"),
    ("liderazgo ético", "ethical leadership"),
    ("liderazgo etico", "ethical leadership"),
    ("liderazgo auténtico", "authentic leadership"),
    ("liderazgo autentico", "authentic leadership"),
    ("liderazgo", "leadership"),
    ("capacitación", "training"),
    ("capacitacion", "training"),
    ("adiestramiento", "training"),
    ("reclutamiento", "recruitment"),
)

SPANISH_QUERY_WORDS = {
    "y": "and",
    "empleado": "employee",
    "empleados": "employees",
    "equipo": "team",
    "equipos": "teams",
    "trabajo": "work",
    "laboral": "workplace",
    "organizacional": "organizational",
    "organizaciones": "organizations",
}


def _normalized(value: str) -> str:
    value = (value or "").casefold()
    value = re.sub(r"[^a-záéíóúñ0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def academic_query_variants(query: str) -> list[str]:
    """Return the original query plus at most one deterministic English expansion."""
    original = re.sub(r"\s+", " ", (query or "").strip())
    if not original:
        return []

    normalized = _normalized(original)
    translated = normalized
    changed = False
    # Longest phrases first prevents a generic token from replacing part of a
    # more specific PIO concept.
    for spanish, english in sorted(
        SPANISH_ACADEMIC_PHRASES, key=lambda item: len(item[0]), reverse=True
    ):
        pattern = rf"(?<!\w){re.escape(spanish)}(?!\w)"
        translated_next, replacements = re.subn(pattern, english, translated)
        if replacements:
            translated = translated_next
            changed = True

    translated_tokens = []
    for token in translated.split():
        replacement = SPANISH_QUERY_WORDS.get(token, token)
        translated_tokens.append(replacement)
        if replacement != token:
            changed = True
    translated = " ".join(translated_tokens).strip()

    variants = [original]
    if changed and translated and _normalized(translated) != normalized:
        variants.append(translated)
    return variants[:2]


def topic_relevance_percent(p: dict, query: str) -> float:
    """Estimate topical match across the original query and bilingual expansion."""
    variants = academic_query_variants(query) or [query]
    normalized_variants = [_normalized(v) for v in variants if _normalized(v)]

    title = _normalized(p.get("title") or "")
    topics = _normalized(p.get("topics") or "")
    abstract = _normalized(p.get("abstract") or "")
    journal = _normalized(p.get("journal") or "")

    def variant_score(text: str, query_n: str) -> float:
        if not text:
            return 0.0
        terms = [
            t for t in re.findall(r"[a-záéíóúñ0-9]+", query_n)
            if len(t) >= 3 and t not in QUERY_STOPWORDS
        ]
        if not terms:
            return 0.0
        aliases = [_normalized(x) for x in QUERY_ALIASES.get(query_n, [query_n]) if x]
        coverage = sum(1 for t in terms if t in text) / max(len(terms), 1)
        phrase = 1.0 if any(a and a in text for a in aliases) else 0.0
        return min(1.0, coverage * 0.75 + phrase * 0.45)

    def field_score(text: str) -> float:
        return max(
            (variant_score(text, query_n) for query_n in normalized_variants),
            default=0.0,
        )

    score = (
        0.42 * field_score(title)
        + 0.30 * field_score(topics)
        + 0.25 * field_score(abstract)
        + 0.03 * field_score(journal)
    )
    return round(min(100.0, score * 100.0), 1)


def score_record(p: dict, query: str, days: int) -> dict:
    title = (p.get("title") or "").lower()
    abstract = (p.get("abstract") or "").lower()
    blob = f"{title} {abstract} {(p.get('topics') or '').lower()}"
    practical = sum(weight for term, weight in PRACTICAL_TERMS.items() if term in blob)
    citations = min(math.log1p(int(p.get("cited_by_count") or 0)) / 2.5, 1.8)
    oa_bonus = 0.6 if p.get("oa_url") or p.get("pdf_url") else 0
    pub = p.get("published_date") or ""
    recency = 0.0
    try:
        d = date.fromisoformat(pub[:10])
        age = max(0, (date.today() - d).days)
        recency = max(0.0, 2.2 * (1 - age / max(days, 1)))
    except Exception:
        pass

    evidence = 0.0
    kind = f"{title} {p.get('work_type','')}".lower()
    if "meta-analysis" in kind or "meta analysis" in kind:
        evidence += 2.2
    if "systematic review" in kind:
        evidence += 2.0
    if "randomized" in blob or "experiment" in blob:
        evidence += 1.0
    if "longitudinal" in blob:
        evidence += 0.7
    if "validation" in blob:
        evidence += 0.6

    topical = topic_relevance_percent(p, query)
    p["matched_query"] = query
    p["topic_relevance_percent"] = topical
    # Backward-compatible 0–20 field, now based ONLY on topical match.
    p["relevance_score"] = round(topical / 5.0, 2)
    p["practical_score"] = min(10.0, round(practical + oa_bonus, 2))
    p["evidence_score"] = min(10.0, round(evidence + citations, 2))
    p["recency_score"] = round(recency, 2)
    p["apa_citation"] = p.get("apa_citation") or apa_fallback(p)
    return p


def search_openalex(query: str, days: int = 45, per_page: int = 15) -> list[dict]:
    start = date.today() - timedelta(days=days)
    params = {
        "search": query,
        "filter": f"from_publication_date:{start.isoformat()},to_publication_date:{date.today().isoformat()}",
        "per-page": min(per_page, 50),
        "sort": "publication_date:desc",
        "api_key": os.getenv("OPENALEX_API_KEY", "") or None,
    }
    params = {key: value for key, value in params.items() if value is not None}
    data = _get("https://api.openalex.org/works", params=params).json()
    out = []
    for w in data.get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        pairs = sorted((pos, word) for word, positions in inv.items() for pos in positions)
        abstract = " ".join(word for _, word in pairs)
        authors = ", ".join((((a or {}).get("author") or {}).get("display_name") or "") for a in w.get("authorships", [])[:8]).strip(", ")
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        oa = w.get("open_access") or {}
        best_oa = w.get("best_oa_location") or {}
        topics = ", ".join(t.get("display_name", "") for t in (w.get("topics") or [])[:6] if t.get("display_name"))
        doi = normalize_doi(w.get("doi") or "")
        p = {
            "id": stable_id("OpenAlex", w.get("id", ""), doi, w.get("title", "")),
            "title": clean_text(w.get("title")), "authors": clean_text(authors), "year": int(w.get("publication_year") or 0),
            "published_date": parse_date(w.get("publication_date")), "source": "OpenAlex", "journal": clean_text(src.get("display_name")),
            "work_type": clean_text(w.get("type")), "doi": doi,
            "url": loc.get("landing_page_url") or w.get("doi") or w.get("id") or "",
            "oa_url": best_oa.get("landing_page_url") or (w.get("doi") if oa.get("is_oa") else "") or "",
            "pdf_url": best_oa.get("pdf_url") or "", "abstract": clean_text(abstract), "topics": topics,
            "discovered_via": "OpenAlex", "cited_by_count": int(w.get("cited_by_count") or 0),
        }
        out.append(score_record(p, query, days))
    return out


def _crossref_date(item: dict) -> str:
    for key in ("published-online", "published-print", "published", "issued", "created"):
        obj = item.get(key) or {}
        if key == "created" and obj.get("date-time"):
            d = parse_date(obj.get("date-time"))
            if d: return d
        parts = obj.get("date-parts") or []
        if parts and parts[0]:
            return parse_date(parts[0])
    return ""


def search_crossref(query: str, days: int = 45, per_page: int = 15) -> list[dict]:
    start = date.today() - timedelta(days=days)
    params = {
        "query.bibliographic": query,
        "filter": f"from-pub-date:{start.isoformat()},until-pub-date:{date.today().isoformat()}",
        "rows": min(per_page, 50), "sort": "published", "order": "desc",
        "mailto": os.getenv("CROSSREF_EMAIL", "") or None,
    }
    params = {k:v for k,v in params.items() if v is not None}
    data = _get("https://api.crossref.org/works", params=params).json().get("message", {})
    out = []
    for it in data.get("items", []):
        authors = []
        for a in it.get("author", [])[:8]:
            name = " ".join(x for x in [a.get("given", ""), a.get("family", "")] if x).strip()
            if name: authors.append(name)
        title = clean_text((it.get("title") or [""])[0])
        doi = normalize_doi(it.get("DOI") or "")
        url = it.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        published = _crossref_date(it)
        journal = clean_text((it.get("container-title") or [""])[0])
        year = int((published or "0")[:4] or 0)
        abstract = clean_text(it.get("abstract"))
        p = {
            "id": stable_id("Crossref", doi, doi, title), "title": title, "authors": ", ".join(authors), "year": year,
            "published_date": published, "source": "Crossref", "journal": journal, "work_type": clean_text(it.get("type")),
            "doi": doi, "url": url, "oa_url": "", "pdf_url": "", "abstract": abstract,
            "topics": ", ".join(clean_text(s) for s in (it.get("subject") or [])[:6]), "discovered_via": "Crossref",
            "cited_by_count": int(it.get("is-referenced-by-count") or 0),
        }
        out.append(score_record(p, query, days))
    return out


def search_crossref_window(
    query: str,
    start_date: date,
    end_date: date,
    *,
    max_records: int = 500,
    page_size: int = 200,
) -> list[dict]:
    """Retrieve a bounded historical Crossref window using cursor pagination."""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    rows = max(1, min(int(page_size), 1000))
    cap = max(1, int(max_records))
    cursor = "*"
    out: list[dict] = []
    scoring_days = max(1, (date.today() - start_date).days + 1)

    while len(out) < cap:
        pace_source_request("Crossref")
        params = {
            "query.bibliographic": query,
            "filter": (
                f"from-pub-date:{start_date.isoformat()},"
                f"until-pub-date:{end_date.isoformat()}"
            ),
            "rows": min(rows, cap - len(out)),
            "cursor": cursor,
            "mailto": os.getenv("CROSSREF_EMAIL", "") or None,
        }
        params = {k: v for k, v in params.items() if v is not None}
        message = _get("https://api.crossref.org/works", params=params).json().get("message", {})
        items = message.get("items") or []
        for it in items:
            authors = []
            for a in it.get("author", [])[:8]:
                name = " ".join(
                    x for x in [a.get("given", ""), a.get("family", "")] if x
                ).strip()
                if name:
                    authors.append(name)
            title = clean_text((it.get("title") or [""])[0])
            if not title:
                continue
            doi = normalize_doi(it.get("DOI") or "")
            published = _crossref_date(it)
            p = {
                "id": stable_id("Crossref", doi, doi, title),
                "title": title,
                "authors": ", ".join(authors),
                "year": int((published or "0")[:4] or 0),
                "published_date": published,
                "source": "Crossref",
                "journal": clean_text((it.get("container-title") or [""])[0]),
                "work_type": clean_text(it.get("type")),
                "doi": doi,
                "url": it.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
                "oa_url": "",
                "pdf_url": "",
                "abstract": clean_text(it.get("abstract")),
                "topics": ", ".join(
                    clean_text(s) for s in (it.get("subject") or [])[:6]
                ),
                "discovered_via": "Crossref historical backfill",
                "cited_by_count": int(it.get("is-referenced-by-count") or 0),
            }
            out.append(score_record(p, query, scoring_days))
            if len(out) >= cap:
                break

        next_cursor = message.get("next-cursor")
        if not items or len(items) < params["rows"] or not next_cursor:
            break
        cursor = next_cursor

    return deduplicate(out)[:cap]


def search_crossref_journal_window(
    journal: str,
    start_date: date,
    end_date: date,
    *,
    max_records: int = 250,
    page_size: int = 200,
) -> list[dict]:
    """Retrieve all bounded Crossref records for an exact journal title window."""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    rows = max(1, min(int(page_size), 1000))
    cap = max(1, int(max_records))
    cursor = "*"
    out: list[dict] = []
    scoring_days = max(1, (date.today() - start_date).days + 1)

    while len(out) < cap:
        pace_source_request("Crossref")
        params = {
            "filter": (
                f"container-title:{journal},"
                f"from-pub-date:{start_date.isoformat()},"
                f"until-pub-date:{end_date.isoformat()}"
            ),
            "rows": min(rows, cap - len(out)),
            "cursor": cursor,
            "mailto": os.getenv("CROSSREF_EMAIL", "") or None,
        }
        params = {k: v for k, v in params.items() if v is not None}
        message = _get("https://api.crossref.org/works", params=params).json().get(
            "message", {}
        )
        items = message.get("items") or []
        for it in items:
            authors = []
            for a in it.get("author", [])[:8]:
                name = " ".join(
                    x for x in [a.get("given", ""), a.get("family", "")] if x
                ).strip()
                if name:
                    authors.append(name)
            title = clean_text((it.get("title") or [""])[0])
            if not title:
                continue
            container = clean_text((it.get("container-title") or [""])[0])
            # Crossref documents container-title as an exact-value filter, but
            # keep this defensive check so a provider anomaly cannot pollute
            # the curated journal stream.
            if container and container.casefold() != journal.casefold():
                continue
            doi = normalize_doi(it.get("DOI") or "")
            published = _crossref_date(it)
            p = {
                "id": stable_id("Crossref", doi, doi, title),
                "title": title,
                "authors": ", ".join(authors),
                "year": int((published or "0")[:4] or 0),
                "published_date": published,
                "source": "Crossref",
                "journal": container or journal,
                "work_type": clean_text(it.get("type")),
                "doi": doi,
                "url": it.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
                "oa_url": "",
                "pdf_url": "",
                "abstract": clean_text(it.get("abstract")),
                "topics": ", ".join(
                    clean_text(s) for s in (it.get("subject") or [])[:6]
                ),
                "discovered_via": "Crossref PIO journal watch",
                "cited_by_count": int(it.get("is-referenced-by-count") or 0),
            }
            out.append(score_record(p, journal, scoring_days))
            if len(out) >= cap:
                break

        next_cursor = message.get("next-cursor")
        if not items or len(items) < params["rows"] or not next_cursor:
            break
        cursor = next_cursor

    return deduplicate(out)[:cap]


def search_europe_pmc(query: str, days: int = 45, per_page: int = 15) -> list[dict]:
    start = date.today() - timedelta(days=days)
    q = f'({query}) AND FIRST_PDATE:[{start.isoformat()} TO {date.today().isoformat()}]'
    params = {"query": q, "format": "json", "pageSize": min(per_page, 50), "resultType": "core", "sort": "FIRST_PDATE_D desc"}
    data = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params=params).json()
    out = []
    for it in ((data.get("resultList") or {}).get("result") or []):
        title = clean_text(it.get("title"))
        doi = normalize_doi(it.get("doi") or "")
        pmid = it.get("pmid") or it.get("pmcid") or it.get("id") or ""
        url = f"https://europepmc.org/article/{it.get('source','MED')}/{pmid}" if pmid else (f"https://doi.org/{doi}" if doi else "")
        published = parse_date(it.get("firstPublicationDate") or it.get("firstIndexDate") or it.get("journalInfo", {}).get("printPublicationDate"))
        year = int((published or str(it.get("pubYear") or 0))[:4] or 0)
        journal = clean_text(((it.get("journalInfo") or {}).get("journal") or {}).get("title") or it.get("journalTitle"))
        authors = clean_text(it.get("authorString"))
        abstract = clean_text(it.get("abstractText"))
        is_oa = str(it.get("isOpenAccess", "")).upper() == "Y"
        pmcid = it.get("pmcid") or ""
        pdf = f"https://europepmc.org/articles/{pmcid}?pdf=render" if is_oa and pmcid else ""
        p = {
            "id": stable_id("Europe PMC", str(pmid), doi, title), "title": title, "authors": authors, "year": year,
            "published_date": published, "source": "Europe PMC", "journal": journal, "work_type": clean_text(it.get("pubType")),
            "doi": doi, "url": url, "oa_url": url if is_oa else "", "pdf_url": pdf, "abstract": abstract,
            "topics": "", "discovered_via": "Europe PMC / PubMed", "cited_by_count": int(it.get("citedByCount") or 0),
        }
        out.append(score_record(p, query, days))
    return out


def search_pubmed(query: str, days: int = 45, per_page: int = 15) -> list[dict]:
    """Search PubMed through NCBI E-utilities using only public metadata."""
    start = date.today() - timedelta(days=days)
    today = date.today()
    term = (
        f'({query}) AND ("{start.strftime("%Y/%m/%d")}"[Date - Publication] : '
        f'"{today.strftime("%Y/%m/%d")}"[Date - Publication])'
    )
    common = {
        "tool": "orion_pio_research",
        "email": os.getenv("NCBI_EMAIL", "") or os.getenv("CROSSREF_EMAIL", "") or None,
        "api_key": os.getenv("NCBI_API_KEY", "") or None,
    }
    common = {k: v for k, v in common.items() if v}
    search_params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": min(int(per_page), 50),
        "sort": "pub date",
        **common,
    }
    search_data = _get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params=search_params,
    ).json()
    ids = ((search_data.get("esearchresult") or {}).get("idlist") or [])
    if not ids:
        return []

    # NCBI counts each E-utility call separately. Reserve the second request
    # here because one logical PubMed search uses ESearch + ESummary.
    pace_source_request("PubMed")
    summary_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "json",
        **common,
    }
    summary = _get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        params=summary_params,
    ).json().get("result") or {}

    out = []
    for pmid in summary.get("uids") or ids:
        it = summary.get(str(pmid)) or {}
        title = clean_text(it.get("title"))
        if not title:
            continue
        article_ids = it.get("articleids") or []
        doi = normalize_doi(
            next(
                (
                    item.get("value")
                    for item in article_ids
                    if str(item.get("idtype", "")).casefold() == "doi"
                ),
                "",
            )
        )
        authors = ", ".join(
            clean_text(author.get("name"))
            for author in (it.get("authors") or [])[:8]
            if author.get("name")
        )
        published = parse_date(it.get("pubdate") or it.get("epubdate"))
        year = int((published or "0")[:4] or 0)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        p = {
            "id": stable_id("PubMed", str(pmid), doi, title),
            "title": title,
            "authors": authors,
            "year": year,
            "published_date": published,
            "source": "PubMed",
            "journal": clean_text(it.get("fulljournalname") or it.get("source")),
            "work_type": ", ".join(clean_text(x) for x in (it.get("pubtype") or [])[:6]),
            "doi": doi,
            "url": url,
            "oa_url": "",
            "pdf_url": "",
            "abstract": "",
            "topics": "",
            "discovered_via": "PubMed / NCBI",
            "cited_by_count": 0,
        }
        out.append(score_record(p, query, days))
    return out


def search_semantic_scholar(query: str, days: int = 45, per_page: int = 15) -> list[dict]:
    start = date.today() - timedelta(days=days)
    fields = "title,abstract,authors,year,venue,url,externalIds,citationCount,publicationDate,openAccessPdf,publicationTypes,fieldsOfStudy"
    params = {
        "query": query.replace("-", " "), "limit": min(per_page, 50), "fields": fields,
        "publicationDateOrYear": f"{start.isoformat()}:{date.today().isoformat()}",
    }
    headers = {}
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
        headers["x-api-key"] = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    data = _get("https://api.semanticscholar.org/graph/v1/paper/search", params=params, headers=headers).json()
    out = []
    for it in data.get("data", []) or []:
        title = clean_text(it.get("title"))
        ext = it.get("externalIds") or {}
        doi = normalize_doi(ext.get("DOI") or "")
        oa = it.get("openAccessPdf") or {}
        pubtypes = it.get("publicationTypes") or []
        authors = ", ".join(a.get("name", "") for a in (it.get("authors") or [])[:8] if a.get("name"))
        published = parse_date(it.get("publicationDate")) or (f"{int(it.get('year')):04d}-01-01" if it.get("year") else "")
        p = {
            "id": stable_id("Semantic Scholar", it.get("paperId", ""), doi, title), "title": title, "authors": authors,
            "year": int(it.get("year") or 0), "published_date": published, "source": "Semantic Scholar",
            "journal": clean_text(it.get("venue")), "work_type": ", ".join(pubtypes), "doi": doi,
            "url": it.get("url") or (f"https://doi.org/{doi}" if doi else ""), "oa_url": oa.get("url") or "",
            "pdf_url": oa.get("url") or "", "abstract": clean_text(it.get("abstract")),
            "topics": ", ".join(it.get("fieldsOfStudy") or []), "discovered_via": "Semantic Scholar",
            "cited_by_count": int(it.get("citationCount") or 0),
        }
        out.append(score_record(p, query, days))
    return out


def search_arxiv(query: str, days: int = 45, per_page: int = 15) -> list[dict]:
    if feedparser is None:
        raise RuntimeError("Falta la dependencia feedparser")
    params = {
        "search_query": f'all:"{query}"', "start": 0, "max_results": min(per_page * 2, 60),
        "sortBy": "submittedDate", "sortOrder": "descending",
    }
    r = requests.get("https://export.arxiv.org/api/query", params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    cutoff = date.today() - timedelta(days=days)
    out = []
    for e in feed.entries:
        published = parse_date(getattr(e, "published", ""))
        try:
            if published and date.fromisoformat(published) < cutoff:
                continue
        except Exception:
            pass
        title = clean_text(getattr(e, "title", ""))
        native = getattr(e, "id", "").split("/abs/")[-1]
        authors = ", ".join(getattr(a, "name", "") for a in getattr(e, "authors", [])[:8])
        pdf = ""
        for link in getattr(e, "links", []):
            if getattr(link, "type", "") == "application/pdf":
                pdf = getattr(link, "href", "")
        p = {
            "id": stable_id("arXiv", native, "", title), "title": title, "authors": authors,
            "year": int((published or "0")[:4] or 0), "published_date": published, "source": "arXiv",
            "journal": "arXiv preprint", "work_type": "preprint", "doi": "", "url": getattr(e, "id", ""),
            "oa_url": getattr(e, "id", ""), "pdf_url": pdf, "abstract": clean_text(getattr(e, "summary", "")),
            "topics": ", ".join(t.get("term", "") for t in getattr(e, "tags", [])[:6]), "discovered_via": "arXiv",
            "cited_by_count": 0,
        }
        out.append(score_record(p, query, days))
        if len(out) >= per_page:
            break
    return out


SEARCHERS = {
    "OpenAlex": search_openalex,
    "Crossref": search_crossref,
    "Europe PMC": search_europe_pmc,
    "PubMed": search_pubmed,
    "Semantic Scholar": search_semantic_scholar,
    "arXiv": search_arxiv,
}


def merge_record(a: dict, b: dict) -> dict:
    # Prefer the most informative values and preserve discovery provenance.
    out = dict(a)
    for field in ("title","authors","journal","work_type","doi","url","oa_url","pdf_url","topics","apa_citation"):
        if not out.get(field) and b.get(field):
            out[field] = b[field]
    if len(b.get("abstract") or "") > len(out.get("abstract") or ""):
        out["abstract"] = b.get("abstract") or ""
    for field in ("cited_by_count","relevance_score","practical_score","evidence_score","recency_score"):
        out[field] = max(float(out.get(field) or 0), float(b.get(field) or 0))
    via = []
    for chunk in [out.get("discovered_via", ""), b.get("discovered_via", "")]:
        for x in re.split(r"\s*\|\s*|,\s*", chunk):
            if x and x not in via: via.append(x)
    out["discovered_via"] = " | ".join(via)
    if (b.get("published_date") or "") > (out.get("published_date") or ""):
        out["published_date"] = b["published_date"]
        out["year"] = b.get("year") or out.get("year")
    return out


def deduplicate(papers: Iterable[dict]) -> list[dict]:
    best = []
    def title_key(p):
        return re.sub(r"[^\w]+", " ", (p.get("title") or "").casefold()).strip()
    for p in papers:
        doi = normalize_doi(p.get("doi") or "")
        title = title_key(p)
        match = next((i for i, old in enumerate(best)
            if (doi and doi == normalize_doi(old.get("doi") or ""))
            or (p.get("id") and p.get("id") == old.get("id"))
            or (title and title == title_key(old))), None)
        if match is None:
            best.append(dict(p))
        else:
            best[match] = merge_record(best[match], p)
    return sorted(best, key=lambda x: (float(x.get("relevance_score") or 0), x.get("published_date") or ""), reverse=True)


def search_all_sources(query: str, days: int, per_source: int, sources: list[str]) -> tuple[list[dict], list[str]]:
    gathered, errors = [], []
    variants = academic_query_variants(query) or [query]
    for source in sources:
        fn = SEARCHERS.get(source)
        if not fn:
            continue
        for index, variant in enumerate(variants, 1):
            try:
                pace_source_request(source)
                gathered.extend(fn(variant, days=days, per_page=per_source))
            except Exception as exc:
                suffix = f" (variant {index}/{len(variants)})" if len(variants) > 1 else ""
                errors.append(f"{source}{suffix}: {type(exc).__name__}: {exc}")
    # Re-score against the user's original query so Spanish searches retain
    # meaningful topical relevance even when a result came from the English expansion.
    return deduplicate(
        score_record(dict(p), query, days) for p in gathered
    ), errors


def get_client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key)


def ai_text(prompt: str, *, max_output: int = 3500) -> str:
    client = get_client()
    if client is None:
        return "Configura OPENAI_API_KEY en el archivo .env para activar esta función de IA."
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    try:
        response = client.responses.create(model=model, input=prompt, max_output_tokens=max_output)
        return response.output_text.strip()
    except Exception:
        return "No se pudo completar la consulta de IA. Verifica la conexión, la clave, el saldo y el modelo configurado."


def _json_from_ai(prompt: str) -> dict:
    raw = ai_text(prompt, max_output=2500)
    if raw.startswith("Configura OPENAI_API_KEY"):
        return {}
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I | re.S)
    try:
        return json.loads(cleaned)
    except Exception:
        return {"summary": raw}


def analyze_paper(paper: dict, audience: str = "consultoría, capacitación y docencia") -> dict:
    if get_client() is None:
        abstract = paper.get("abstract") or "No se encontró abstract."
        return {
            "summary": abstract[:1000] + ("…" if len(abstract) > 1000 else ""),
            "why_it_matters": "Análisis automático pendiente: activa la IA para evaluar la contribución con más detalle.",
            "applications": "• Revisar el método y la muestra.\n• Identificar hallazgos transferibles al contexto real.\n• Verificar limitaciones antes de usarlo en consultoría o docencia.",
            "limitations": "Sin IA activa no se infieren limitaciones que no estén explícitas en el abstract.",
            "evidence_level": "Pendiente de evaluación",
            "apa_citation": paper.get("apa_citation") or apa_fallback(paper),
            "read_full": bool(paper.get("abstract") and float(paper.get("relevance_score") or 0) >= 8),
            "practical_score": min(10.0, float(paper.get("practical_score") or 0)),
            "evidence_score": min(10.0, float(paper.get("evidence_score") or 0)),
        }
    prompt = f"""
Eres analista senior de Psicología Industrial-Organizacional y Desarrollo Organizacional. Evalúa el trabajo SOLO con la información suministrada. No inventes resultados, tamaños de efecto, muestra ni método ausentes.
Audiencia prioritaria: {audience}.

TÍTULO: {paper.get('title')}
AUTORES: {paper.get('authors')}
FUENTE/JOURNAL: {paper.get('journal') or paper.get('source')}
FECHA: {paper.get('published_date')}
TIPO: {paper.get('work_type')}
ABSTRACT: {paper.get('abstract') or 'No disponible'}
CITAS: {paper.get('cited_by_count',0)}

Devuelve SOLO JSON válido con:
summary: 100-160 palabras en español
why_it_matters: 60-110 palabras
applications: exactamente 3 aplicaciones concretas, cada una empezando por "• " y separadas por salto de línea
limitations: limitaciones observables o, si no están disponibles, qué falta verificar
 evidence_level: frase breve (ej. "meta-análisis", "estudio longitudinal", "preprint", "no determinable desde el abstract")
apa_citation: referencia APA 7 aproximada usando los metadatos disponibles
read_full: booleano
practical_score: número 0-10
evidence_score: número 0-10
"""
    data = _json_from_ai(prompt)
    data.setdefault("apa_citation", paper.get("apa_citation") or apa_fallback(paper))
    return data


def build_library_context(papers: list[dict], limit: int = 24) -> str:
    blocks = []
    for p in papers[:limit]:
        blocks.append(
            f"TÍTULO: {p.get('title')}\nFECHA: {p.get('published_date')}\nFUENTE: {p.get('journal') or p.get('source')}\n"
            f"RESUMEN: {p.get('summary') or (p.get('abstract') or '')[:1300]}\nAPLICACIONES: {p.get('applications','')}\n"
            f"LIMITACIONES: {p.get('limitations','')}\nURL: {p.get('url','')}"
        )
    return "\n\n---\n\n".join(blocks)


def answer_from_library(question: str, papers: list[dict]) -> str:
    if get_client() is None:
        return "Configura OPENAI_API_KEY para activar el agente conversacional."
    prompt = f"""
Eres Orión PIO, un agente de evidencia para Psicología Industrial-Organizacional, liderazgo y desarrollo organizacional.
Responde en español usando la biblioteca incluida. Distingue: (1) evidencia descrita, (2) interpretación práctica, (3) límites/incertidumbre.
No inventes detalles ausentes. Cuando recomiendes una lectura, menciona el título. Incluye URLs solo cuando estén disponibles.

PREGUNTA:
{question}

BIBLIOTECA:
{build_library_context(papers)}
"""
    return ai_text(prompt, max_output=4000)


def generate_workshop(paper: dict, duration: str = "90 minutos", audience: str = "líderes y supervisores") -> str:
    prompt = f"""
Diseña un taller práctico de {duration} para {audience}, basado principalmente en el estudio siguiente. No inventes hallazgos que no aparezcan en el material.
Incluye: objetivos de aprendizaje; agenda minuto a minuto; conceptos clave; dinámica inicial; 2 ejercicios aplicados; preguntas de reflexión; materiales; evaluación breve; transferencia al puesto; y una nota explícita de qué afirmaciones dependen de leer el artículo completo.
ESTUDIO: {paper.get('title')}
RESUMEN/ABSTRACT: {paper.get('summary') or paper.get('abstract')}
APLICACIONES: {paper.get('applications')}
LIMITACIONES: {paper.get('limitations')}
"""
    return ai_text(prompt, max_output=4500)


def generate_class_activity(paper: dict, level: str = "universidad/posgrado") -> str:
    prompt = f"""
Crea una actividad docente de 45-60 minutos para nivel {level} basada en este estudio de PIO/DO. Incluye objetivos, preparación, instrucciones, preguntas, rúbrica simple de 10 puntos, cierre y conexión con práctica profesional. Separa claramente lo que afirma el estudio de las preguntas de discusión.
ESTUDIO: {paper.get('title')}
CONTENIDO: {paper.get('summary') or paper.get('abstract')}
"""
    return ai_text(prompt, max_output=3500)


def generate_case(paper: dict, sector: str = "empresa de servicios") -> str:
    prompt = f"""
Crea un caso empresarial ficticio y realista en una {sector} para aplicar los conceptos de este estudio. No copies organizaciones reales. Incluye contexto, problema, datos ficticios claramente marcados como ficticios, 5 preguntas de análisis y una guía del facilitador que conecte con la evidencia disponible.
ESTUDIO: {paper.get('title')}
EVIDENCIA DISPONIBLE: {paper.get('summary') or paper.get('abstract')}
APLICACIONES: {paper.get('applications')}
"""
    return ai_text(prompt, max_output=3500)


def compare_papers(papers: list[dict]) -> str:
    prompt = f"""
Compara los siguientes trabajos de PIO/DO. Crea una síntesis con: pregunta/tema, tipo de evidencia si es identificable, hallazgos disponibles, coincidencias, diferencias, aplicaciones, limitaciones y qué conviene verificar leyendo completos. No declares un estudio 'mejor' solo por citas o actualidad.

{build_library_context(papers, limit=8)}
"""
    return ai_text(prompt, max_output=4500)


def generate_consulting_diagnostic(topic: str, context: str = "") -> str:
    prompt = f"""
Diseña un diagnóstico organizacional práctico sobre: {topic}.
Contexto: {context or 'No provisto'}.
Incluye propósito, hipótesis de trabajo (no conclusiones), stakeholders, 10 preguntas de entrevista, 12 ítems de encuesta Likert, indicadores, plan de análisis, riesgos éticos/confidencialidad, y cómo convertir resultados en recomendaciones. Señala qué partes deben adaptarse al cliente.
"""
    return ai_text(prompt, max_output=4000)


def extract_trends(papers: list[dict], top_n: int = 20) -> list[tuple[str, int]]:
    counts = Counter()
    for p in papers:
        text = f"{p.get('title','')} {p.get('topics','')}".lower()
        tokens = re.findall(r"[a-záéíóúñ][a-záéíóúñ-]{3,}", text)
        for t in tokens:
            if t not in STOPWORDS and not t.isdigit():
                counts[t] += 1
    return counts.most_common(top_n)


def source_search_links(query: str) -> list[tuple[str, str]]:
    q = quote(query)
    return [
        ("Google Scholar", f"https://scholar.google.com/scholar?q={q}"),
        ("APA PsycNet", f"https://psycnet.apa.org/search/results?term={q}"),
        ("SIOP", f"https://www.google.com/search?q=site%3Asiop.org+{q}"),
        ("SSRN", f"https://papers.ssrn.com/sol3/results.cfm?txtKey_Words={q}"),
        ("Academy of Management", f"https://journals.aom.org/action/doSearch?AllField={q}"),
        ("Harvard Business Review", f"https://hbr.org/search?term={q}"),
    ]