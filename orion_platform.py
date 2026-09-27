from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass, asdict
from typing import Callable, Iterable
from urllib.parse import quote_plus

from platform_store import get_cache, log_search, record_source_failure, record_source_success, set_cache, source_available

PLATFORM_VERSION = "3.0.0"

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
    SourceSpec("OpenAlex","academic","Scholarly index",True,True,official_url="https://openalex.org/",notes="Broad academic discovery."),
    SourceSpec("Crossref","academic","DOI metadata registry",True,True,"CROSSREF_EMAIL","https://www.crossref.org/",notes="Metadata-focused; email enables polite-pool identification."),
    SourceSpec("Semantic Scholar","academic","Scholarly index",True,True,"SEMANTIC_SCHOLAR_API_KEY","https://www.semanticscholar.org/","https://www.semanticscholar.org/me/account"),
    SourceSpec("Europe PMC","academic","Biomedical literature index",True,True,official_url="https://europepmc.org/"),
    SourceSpec("arXiv","academic","Preprint repository",True,True,official_url="https://arxiv.org/",notes="Preprints are not equivalent to peer-reviewed evidence."),
    SourceSpec("Google Scholar","academic","Discovery service",False,True,official_url="https://scholar.google.com/"),
    SourceSpec("APA PsycNet","academic","APA literature platform",False,False,official_url="https://psycnet.apa.org/",login_url="https://my.apa.org/"),
    SourceSpec("SSRN","academic","Working-paper repository",False,True,official_url="https://www.ssrn.com/",login_url="https://hq.ssrn.com/login/pubsigninjoin.cfm"),
    SourceSpec("SIOP","academic","Professional association",False,True,official_url="https://www.siop.org/",login_url="https://my.siop.org/"),
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
    q=normalize_query(query); sources=["OpenAlex","Crossref","Semantic Scholar"]
    if any(t in q for t in ("wellbeing","burnout","stress","health","mental","fatigue","sleep")): sources.append("Europe PMC")
    if any(t in q for t in ("ai ","machine learning","algorithm","automation","computational","large language")): sources.append("arXiv")
    return list(dict.fromkeys(sources))

def route_query(query, domain="auto"):
    resolved=classify_query(query) if domain=="auto" else domain
    if resolved=="academic":
        return {"domain":resolved,"automated_sources":recommended_academic_sources(query),"manual_sources":["Google Scholar","APA PsycNet","SIOP","SSRN"]}
    if resolved=="legal_pr":
        return {"domain":resolved,"automated_sources":[],"manual_sources":["OSL / SUTRA","Departamento de Estado PR","Biblioteca Jurídica Virtual PR","Rama Judicial de Puerto Rico"]}
    if resolved=="legal_us":
        return {"domain":resolved,"automated_sources":[],"manual_sources":["Congress.gov","GovInfo","Federal Register","Supreme Court of the United States","CourtListener"]}
    if resolved=="legal_intl":
        return {"domain":resolved,"automated_sources":[],"manual_sources":["United Nations Digital Library","UN Treaty Collection","International Court of Justice","HUDOC"]}
    return {"domain":resolved,"automated_sources":[],"manual_sources":["OSL / SUTRA","Congress.gov","United Nations Digital Library"]}

def source_search_url(source, query):
    q=quote_plus(query)
    urls={
      "Google Scholar":f"https://scholar.google.com/scholar?q={q}",
      "APA PsycNet":f"https://psycnet.apa.org/search/results?term={q}",
      "SIOP":f"https://www.google.com/search?q=site%3Asiop.org+{q}",
      "SSRN":f"https://papers.ssrn.com/sol3/results.cfm?txtKey_Words={q}",
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
    started=time.perf_counter(); searchers=searchers or _default_searchers()
    selected=list(sources or recommended_academic_sources(query)); gathered=[]; errors=[]; source_meta=[]
    for source in selected:
        fn=searchers.get(source)
        if not fn:
            errors.append(f"{source}: source is not available in this build")
            source_meta.append({"source":source,"status":"unavailable","count":0,"cached":False}); continue
        if not source_available(source):
            errors.append(f"{source}: temporarily paused after repeated failures")
            source_meta.append({"source":source,"status":"circuit_open","count":0,"cached":False}); continue
        cached=None if force_refresh else get_cache(source,query,days,per_source)
        if cached is not None:
            gathered.extend(cached); source_meta.append({"source":source,"status":"ok","count":len(cached),"cached":True}); continue
        result=None; last_error=None
        for attempt in range(retries+1):
            try:
                result=fn(query,days=days,per_page=per_source); record_source_success(source); break
            except Exception as exc:
                last_error=exc
                if attempt<retries: sleep_fn(min(3.0,0.45*(2**attempt)+random.random()*0.2))
        if result is None:
            msg=f"{source}: {type(last_error).__name__}: {last_error}"
            errors.append(msg); record_source_failure(source,msg)
            source_meta.append({"source":source,"status":"error","count":0,"cached":False}); continue
        set_cache(source,query,days,per_source,result,ttl_hours=cache_ttl_hours)
        gathered.extend(result); source_meta.append({"source":source,"status":"ok","count":len(result),"cached":False})
    unique=_deduplicate(gathered)[:int(max_keep)]
    duration_ms=int((time.perf_counter()-started)*1000)
    log_search(query,"academic",selected,len(gathered),len(unique),duration_ms,errors)
    return {"query":query,"domain":"academic","sources":selected,"results":unique,"received":len(gathered),"unique":len(unique),"errors":errors,"source_meta":source_meta,"duration_ms":duration_ms}

def all_topics():
    return [topic for topics in TOPIC_GROUPS.values() for topic in topics]
