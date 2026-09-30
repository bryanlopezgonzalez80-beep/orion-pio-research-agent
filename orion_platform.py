from __future__ import annotations

import json
import os
import random
import re
import time
from dataclasses import dataclass, asdict
from typing import Callable, Iterable
from urllib.parse import quote_plus

from platform_store import get_cache, log_search, record_source_failure, record_source_metrics, record_source_success, set_cache, source_available

PLATFORM_VERSION = "3.0.0"


def _retry_after_seconds(response, *, cap: float) -> float | None:
    """Parse a numeric Retry-After header without leaking response content."""
    raw = (getattr(response, "headers", None) or {}).get("Retry-After")
    if raw:
        try:
            return min(cap, max(0.0, float(raw)))
        except (TypeError, ValueError):
            pass
    return None


def _rate_limit_delay(exc: Exception, attempt: int) -> float | None:
    """Return a bounded retry delay for HTTP 429, otherwise None."""
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) != 429:
        return None
    retry_after = _retry_after_seconds(response, cap=30.0)
    if retry_after is not None:
        return retry_after
    return min(15.0, 1.0 * (2 ** max(0, attempt)))


def _transient_retry_delay(exc: Exception, attempt: int) -> float | None:
    """Back off for rate limits, provider 5xx errors, timeouts, and connection failures."""
    rate_limit = _rate_limit_delay(exc, attempt)
    if rate_limit is not None:
        return rate_limit

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        retry_after = _retry_after_seconds(response, cap=30.0)
        if retry_after is not None:
            return retry_after
        return min(15.0, 1.0 * (2 ** max(0, attempt)))

    # Requests exceptions are intentionally detected by class name as well as
    # inheritance so test doubles and wrapped transport errors remain retryable.
    if type(exc).__name__ in {"Timeout", "ConnectTimeout", "ReadTimeout", "ConnectionError"}:
        return min(8.0, 1.0 * (2 ** max(0, attempt)))
    return None

@dataclass(frozen=True)
class SourceSpec:
    name: str
    domain: str
    authority: str
    automated: bool
    free_access: bool
    credential_env: str = ""
    official_url: str = ""
    login_url: str = ""
    notes: str = ""

SOURCE_SPECS = (
    SourceSpec("OpenAlex","academic","Scholarly index",True,True,"OPENALEX_API_KEY","https://openalex.org/","https://openalex.org/settings/api",notes="Broad academic discovery; a free API key increases the daily search budget."),
    SourceSpec("Crossref","academic","DOI metadata registry",True,True,"CROSSREF_EMAIL","https://www.crossref.org/",notes="Metadata-focused; email enables polite-pool identification."),
    SourceSpec("Semantic Scholar","academic","Scholarly index",True,True,"SEMANTIC_SCHOLAR_API_KEY","https://www.semanticscholar.org/","https://www.semanticscholar.org/me/account"),
    SourceSpec("Europe PMC","academic","Biomedical literature index",True,True,official_url="https://europepmc.org/"),
    SourceSpec("PubMed","academic","U.S. National Library of Medicine literature index",True,True,"NCBI_API_KEY","https://pubmed.ncbi.nlm.nih.gov/","https://www.ncbi.nlm.nih.gov/account/",notes="NCBI E-utilities; an API key is optional and only raises supported request rate."),
    SourceSpec("arXiv","academic","Preprint repository",True,True,official_url="https://arxiv.org/",notes="Preprints are not equivalent to peer-reviewed evidence."),
    SourceSpec("Google Scholar","academic","Discovery service",False,True,official_url="https://scholar.google.com/"),
    SourceSpec("APA PsycNet","academic","APA literature platform",False,False,official_url="https://psycnet.apa.org/",login_url="https://my.apa.org/"),
    SourceSpec("SSRN","academic","Working-paper repository",False,True,official_url="https://www.ssrn.com/",login_url="https://hq.ssrn.com/login/pubsigninjoin.cfm"),
    SourceSpec("SIOP","academic","Professional association",False,True,official_url="https://www.siop.org/",login_url="https://my.siop.org/"),
    SourceSpec("Academy of Management","academic","Scholarly management journals",False,False,official_url="https://journals.aom.org/"),
    SourceSpec("DOAJ","academic","Curated open-access journal directory",False,True,official_url="https://doaj.org/"),
    SourceSpec("Revista Puertorriqueña de Psicología","academic","Puerto Rico journal",False,True,official_url="https://www.repsasppr.net/"),
    SourceSpec("Revista Caribeña de Psicología","academic","Caribbean psychology journal",False,True,official_url="https://revistacaribenadepsicologia.com/"),
    SourceSpec("Fórum Empresarial","academic","Puerto Rico business journal",False,True,official_url="https://revistas.upr.edu/index.php/forumempresarial"),
    SourceSpec("CONUCO","academic","Directed Puerto Rico repository",False,True,official_url="https://conuco.uprm.edu/",notes="Mixed academic and informational material; never assume peer review."),
    SourceSpec("Repositorio Institucional UPR","academic","Directed Puerto Rico institutional repository",False,True,official_url="https://www.upr.edu/repositorio/",notes="Open repository metadata and content; item type and peer-review status must be verified per record."),
    SourceSpec("OSL / SUTRA","legal_pr","Official Puerto Rico legislative source",False,True,official_url="https://sutra.oslpr.org/"),
    SourceSpec("Departamento de Estado PR","legal_pr","Official Puerto Rico laws source",False,True,official_url="https://www.estado.pr.gov/leyes-de-puerto-rico"),
    SourceSpec("Biblioteca Jurídica Virtual PR","legal_pr","Official Puerto Rico government legal library",False,True,official_url="https://bibliotecavirtual.estado.pr.gov/"),
    SourceSpec("Rama Judicial de Puerto Rico","legal_pr","Official Puerto Rico judiciary",False,True,official_url="https://poderjudicial.pr/"),
    SourceSpec("Congress.gov","legal_us","Official U.S. legislative source",False,True,official_url="https://www.congress.gov/"),
    SourceSpec("GovInfo","legal_us","Official U.S. Government Publishing Office",False,True,official_url="https://www.govinfo.gov/"),
    SourceSpec("Federal Register","legal_us","Official U.S. rulemaking/publication source",False,True,official_url="https://www.federalregister.gov/"),
    SourceSpec("Supreme Court of the United States","legal_us","Official U.S. Supreme Court",False,True,official_url="https://www.supremecourt.gov/"),
    SourceSpec("CourtListener","legal_us","Nonprofit case-law search",False,True,"COURTLISTENER_API_TOKEN","https://www.courtlistener.com/","https://www.courtlistener.com/sign-in/"),
    SourceSpec("United Nations Digital Library","legal_intl","Official UN source",False,True,official_url="https://digitallibrary.un.org/"),
    SourceSpec("UN Treaty Collection","legal_intl","Official UN treaty source",False,True,official_url="https://treaties.un.org/"),
    SourceSpec("International Court of Justice","legal_intl","Official ICJ source",False,True,official_url="https://www.icj-cij.org/"),
    SourceSpec("HUDOC","legal_intl","European Court of Human Rights database",False,True,official_url="https://hudoc.echr.coe.int/"),
)
SOURCE_BY_NAME={s.name:s for s in SOURCE_SPECS}
ACADEMIC_AUTOMATED=[s.name for s in SOURCE_SPECS if s.domain=="academic" and s.automated]

TOPIC_GROUPS={
"Leadership":["leadership effectiveness","transformational leadership","servant leadership","ethical leadership","authentic leadership","shared leadership","leader member exchange","leadership development","team leadership","leadership identity","manager coaching","leadership derailment"],
"People & Talent":["employee engagement","talent management","succession planning","employee retention","turnover intention","performance management","employee selection assessment","structured interviews","assessment centers","onboarding","career development","competency modeling"],
"Teams & Culture":["team effectiveness","psychological safety workplace","organizational culture","organizational climate","team conflict","team cohesion","virtual teams","hybrid work remote work","collaboration","knowledge sharing","organizational trust","organizational justice"],
"Learning & Change":["training and development workplace","training transfer","learning transfer","organizational development","organizational change","change readiness","change resistance","employee voice","job crafting","continuous learning","learning organization","innovation climate"],
"Wellbeing & Work Design":["workplace wellbeing","employee burnout","occupational stress","work engagement","job demands resources","work life balance","work design","meaningful work","employee resilience","fatigue at work","workplace incivility","workplace bullying"],
"Technology & Analytics":["AI human resources workplace","people analytics","algorithmic management","AI hiring","HR analytics","future of work","digital transformation workplace","automation and jobs","human AI collaboration","employee monitoring","HR information systems","skills based organization"],
}

LEGAL_PR_TERMS={"puerto rico","pr law","ley ","reglamento","jurisprudencia","tribunal supremo de puerto rico","rama judicial","código civil","codigo civil","ley 80","ley 100","ley 180","despido injustificado","asamblea legislativa","senado de puerto rico","cámara de representantes","camara de representantes"}
LEGAL_US_TERMS={"u.s. law","federal law","congress","supreme court","usc ","u.s.c","cfr ","federal register","title vii","ada ","nlra","flsa","eeoc","osha","federal court","constitution"}
LEGAL_INTL_TERMS={"international law","treaty","united nations","icj","echr","hudoc","human rights law","international court","public international law","derecho internacional","tratado"}
LEGAL_GENERIC={"law","legal","statute","regulation","case law","derecho","ley","jurisprudencia","reglamento"}

def normalize_query(q):
    return re.sub(r"\s+"," ",(q or "").strip()).casefold()

def classify_query(query):
    q=normalize_query(query)
    if any(t in q for t in LEGAL_PR_TERMS): return "legal_pr"
    if any(t in q for t in LEGAL_US_TERMS): return "legal_us"
    if any(t in q for t in LEGAL_INTL_TERMS): return "legal_intl"
    if any(t in q for t in LEGAL_GENERIC): return "legal_general"
    return "academic"

def recommended_academic_sources(query):
    from research_agent import academic_query_variants

    variants=academic_query_variants(query) or [query]
    q=" ".join(normalize_query(v) for v in variants); sources=["OpenAlex","Crossref"]
    # Semantic Scholar is excellent, but unauthenticated requests have tight rate limits.
    # Promote it to the default route only when a key is configured; it remains user-selectable.
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"): sources.append("Semantic Scholar")
    if any(t in q for t in ("wellbeing","burnout","stress","health","mental","fatigue","sleep","occupational")):
        sources.extend(["Europe PMC","PubMed"])
    if any(t in q for t in ("ai ","artificial intelligence","machine learning","algorithm","automation","computational","large language")): sources.append("arXiv")
    return list(dict.fromkeys(sources))

def route_query(query, domain="auto"):
    resolved=classify_query(query) if domain=="auto" else domain
    if resolved=="academic":
        return {"domain":resolved,"automated_sources":recommended_academic_sources(query),"manual_sources":["Google Scholar","APA PsycNet","SIOP","SSRN","Academy of Management","DOAJ"]}
    if resolved=="legal_pr":
        return {"domain":resolved,"automated_sources":[],"manual_sources":["OSL / SUTRA","Departamento de Estado PR","Biblioteca Jurídica Virtual PR","Rama Judicial de Puerto Rico"]}
    if resolved=="legal_us":
        return {"domain":resolved,"automated_sources":[],"manual_sources":["Congress.gov","GovInfo","Federal Register","Supreme Court of the United States","CourtListener"]}
    if resolved=="legal_intl":
        return {"domain":resolved,"automated_sources":[],"manual_sources":["United Nations Digital Library","UN Treaty Collection","International Court of Justice","HUDOC"]}
    return {"domain":resolved,"automated_sources":[],"manual_sources":["OSL / SUTRA","Congress.gov","United Nations Digital Library"]}

def source_search_url(source, query):
    q=quote_plus(query)
    doaj_source=quote_plus(json.dumps({
        "query":{"query_string":{"query":query,"default_operator":"AND"}}
    }, separators=(",",":")))
    urls={
      "Google Scholar":f"https://scholar.google.com/scholar?q={q}",
      "APA PsycNet":f"https://psycnet.apa.org/search/results?term={q}",
      "SIOP":f"https://www.google.com/search?q=site%3Asiop.org+{q}",
      "SSRN":f"https://papers.ssrn.com/sol3/results.cfm?txtKey_Words={q}",
      "Academy of Management":f"https://journals.aom.org/action/doSearch?AllField={q}",
      "DOAJ":f"https://doaj.org/search?source={doaj_source}&ref=homepage-box",
      "Revista Puertorriqueña de Psicología":f"https://www.google.com/search?q=site%3Arepsasppr.net+{q}",
      "Revista Caribeña de Psicología":f"https://www.google.com/search?q=site%3Arevistacaribenadepsicologia.com+{q}",
      "Fórum Empresarial":f"https://www.google.com/search?q=site%3Arevistas.upr.edu+forumempresarial+{q}",
      "CONUCO":f"https://www.google.com/search?q=site%3Aconuco.uprm.edu+{q}",
      "Repositorio Institucional UPR":f"https://www.google.com/search?q=site%3Aupr.edu%2Frepositorio+{q}",
      "OSL / SUTRA":f"https://www.google.com/search?q=site%3Asutra.oslpr.org+{q}",
      "Departamento de Estado PR":f"https://www.google.com/search?q=site%3Aestado.pr.gov+{q}",
      "Biblioteca Jurídica Virtual PR":f"https://www.google.com/search?q=site%3Abibliotecavirtual.estado.pr.gov+{q}",
      "Rama Judicial de Puerto Rico":f"https://www.google.com/search?q=site%3Apoderjudicial.pr+{q}",
      "Congress.gov":f"https://www.congress.gov/quick-search/legislation?wordsPhrases={q}",
      "GovInfo":f"https://www.govinfo.gov/app/search/%7B%22query%22%3A%22{q}%22%7D",
      "Federal Register":f"https://www.federalregister.gov/documents/search?conditions%5Bterm%5D={q}",
      "Supreme Court of the United States":f"https://www.google.com/search?q=site%3Asupremecourt.gov+{q}",
      "CourtListener":f"https://www.courtlistener.com/?q={q}",
      "United Nations Digital Library":f"https://digitallibrary.un.org/search?ln=en&p={q}",
      "UN Treaty Collection":f"https://www.google.com/search?q=site%3Atreaties.un.org+{q}",
      "International Court of Justice":f"https://www.google.com/search?q=site%3Aicj-cij.org+{q}",
      "HUDOC":f"https://hudoc.echr.coe.int/eng#%7B%22fulltext%22%3A%5B%22{q}%22%5D%7D",
    }
    return urls.get(source,SOURCE_BY_NAME.get(source,SourceSpec(source,"","",False,True)).official_url)

def source_configuration():
    rows=[]
    for spec in SOURCE_SPECS:
        row=asdict(spec)
        row["credential_configured"]=bool(spec.credential_env and os.getenv(spec.credential_env))
        row["credential_required_for_orion"]=bool(spec.credential_env)
        rows.append(row)
    return rows

def _default_searchers():
    from research_agent import SEARCHERS
    return SEARCHERS

def _deduplicate(papers):
    from research_agent import deduplicate
    return deduplicate(papers)

def execute_academic_search(query, *, days=60, per_source=8, sources=None, max_keep=150, retries=2, cache_ttl_hours=8, force_refresh=False, searchers=None, sleep_fn=time.sleep):
    from research_agent import academic_query_variants, is_spanish_query, pace_source_request, record_language, score_record, source_rate_policy

    started=time.perf_counter()
    using_default_searchers=searchers is None
    searchers=searchers or _default_searchers()
    query_variants=academic_query_variants(query) or [query]
    selected=list(sources or recommended_academic_sources(query)); gathered=[]; errors=[]; source_meta=[]
    for source in selected:
        source_started=time.perf_counter()
        fn=searchers.get(source)
        policy=source_rate_policy(source)
        empty_meta={
            "source":source,"status":"unavailable","count":0,"cached":False,
            "network_requests":0,"cache_hits":0,"retries":0,"rate_limited":False,
            "minimum_interval_seconds":policy["minimum_interval_seconds"],
            "rate_guidance":policy["guidance"],
        }
        if not fn:
            errors.append(f"{source}: source is not available in this build")
            source_meta.append(empty_meta); continue
        if not source_available(source):
            errors.append(f"{source}: temporarily paused after repeated failures")
            source_meta.append({**empty_meta,"status":"circuit_open"}); continue

        source_results=[]; cached_flags=[]; any_success=False
        network_attempted=False; network_success=False; source_errors=[]
        network_requests=0; cache_hits=0; retry_count=0; rate_limited=False
        for variant_index, variant in enumerate(query_variants, 1):
            cached=None if force_refresh else get_cache(source,variant,days,per_source)
            if cached is not None:
                source_results.extend(cached); cached_flags.append(True); any_success=True; cache_hits+=1
                continue

            cached_flags.append(False); network_attempted=True
            result=None; last_error=None
            for attempt in range(retries+1):
                if using_default_searchers:
                    pace_source_request(source, sleep_fn=sleep_fn)
                network_requests+=1
                if attempt: retry_count+=1
                try:
                    result=fn(variant,days=days,per_page=per_source); network_success=True; break
                except Exception as exc:
                    last_error=exc
                    if getattr(getattr(exc, "response", None), "status_code", None)==429:
                        rate_limited=True
                    if attempt<retries:
                        retry_delay = _transient_retry_delay(exc, attempt)
                        # Preserve one short retry for opaque provider/runtime
                        # errors, while giving documented HTTP/transient failures
                        # enough time to recover.
                        sleep_fn(
                            retry_delay
                            if retry_delay is not None
                            else min(3.0, 0.45 * (2 ** attempt) + random.random() * 0.2)
                        )
            if result is None:
                suffix=f" (variant {variant_index}/{len(query_variants)})" if len(query_variants)>1 else ""
                source_errors.append(f"{source}{suffix}: {type(last_error).__name__}: {last_error}")
                continue

            any_success=True
            set_cache(source,variant,days,per_source,result,ttl_hours=cache_ttl_hours)
            source_results.extend(result)

        if network_success:
            record_source_success(source)
        elif network_attempted and source_errors:
            record_source_failure(source,source_errors[-1])

        errors.extend(source_errors); gathered.extend(source_results)
        source_meta.append({
            "source":source,
            "status":"ok" if any_success else "error",
            "count":len(source_results),
            "cached":bool(cached_flags) and all(cached_flags),
            "network_requests":network_requests,
            "cache_hits":cache_hits,
            "retries":retry_count,
            "rate_limited":rate_limited,
            "minimum_interval_seconds":policy["minimum_interval_seconds"],
            "rate_guidance":policy["guidance"],
        })
        record_source_metrics(
            source, requests=network_requests, successes=1 if any_success else 0,
            failures=1 if source_errors else 0, rate_limits=1 if rate_limited else 0,
            latency_ms=int((time.perf_counter()-source_started)*1000),
            records_received=len(source_results), unique_records=len(_deduplicate(source_results)),
            health_status=("RATE_LIMITED" if rate_limited else "HEALTHY" if any_success else "DEGRADED"),
        )

    unique=[score_record(dict(p),query,days) for p in _deduplicate(gathered)]
    for paper in unique:
        paper["language"] = record_language(paper)
    if is_spanish_query(query):
        unique.sort(key=lambda p: (record_language(p) == "es", float(p.get("relevance_score") or 0), p.get("published_date") or ""), reverse=True)
    unique=_deduplicate(unique)[:int(max_keep)]
    duration_ms=int((time.perf_counter()-started)*1000)
    log_search(query,"academic",selected,len(gathered),len(unique),duration_ms,errors)
    return {
        "query":query,"query_variants":query_variants,"query_expanded":len(query_variants)>1,
        "domain":"academic","sources":selected,"results":unique,"received":len(gathered),
        "unique":len(unique),"errors":errors,"source_meta":source_meta,"duration_ms":duration_ms,
    }

def all_topics():
    return [topic for topics in TOPIC_GROUPS.values() for topic in topics]
