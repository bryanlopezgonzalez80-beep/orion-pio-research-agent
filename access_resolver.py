"""Resolve legitimate document access without receiving user credentials."""
from __future__ import annotations

import os
from urllib.parse import quote, urlparse


ACCESS_STATUSES = {
    "OPEN_ACCESS", "INSTITUTIONAL_ACCESS", "PROVIDER_LOGIN",
    "PUBLISHER_ACCESS", "DOI_ONLY", "METADATA_ONLY", "UNKNOWN",
}


def _http_url(value: object) -> str:
    text = str(value or "").strip()
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _doi_url(doi: object) -> str:
    clean = str(doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    return f"https://doi.org/{quote(clean, safe='/();:')}" if clean else ""


def resolve_access(paper: dict, *, institution: dict | None = None) -> dict:
    alternatives: list[dict] = []
    doi_url = _doi_url(paper.get("doi"))
    oa_url = _http_url(paper.get("oa_url"))
    repository_url = _http_url(paper.get("repository_url"))
    publisher_url = _http_url(paper.get("publisher_url") or paper.get("url"))
    pdf_url = _http_url(paper.get("pdf_url")) if paper.get("pdf_confirmed") else ""
    institution = institution or {
        "institution_name": os.getenv("ORION_INSTITUTION_NAME", ""),
        "openurl_base": os.getenv("ORION_OPENURL_BASE", ""),
        "enabled": os.getenv("ORION_OPENURL_ENABLED", "false").lower() == "true",
    }
    openurl = ""
    if institution.get("enabled") and _http_url(institution.get("openurl_base")):
        target = doi_url or publisher_url
        if target:
            separator = "&" if "?" in institution["openurl_base"] else "?"
            openurl = f"{institution['openurl_base']}{separator}url_ver=Z39.88-2004&rft_id={quote(target, safe='')}"

    providers = paper.get("licensed_providers") or []
    if isinstance(providers, str):
        providers = [providers]
    if oa_url or repository_url or pdf_url:
        status, best, access_type, provider = "OPEN_ACCESS", pdf_url or repository_url or oa_url, "open_access", paper.get("oa_provider") or "Open Access"
    elif openurl:
        status, best, access_type, provider = "INSTITUTIONAL_ACCESS", openurl, "institutional_resolver", institution.get("institution_name") or "Institution"
    elif providers:
        status, best, access_type, provider = "PROVIDER_LOGIN", _http_url(paper.get("provider_url")) or publisher_url or doi_url, "licensed_provider", str(providers[0])
    elif publisher_url:
        status, best, access_type, provider = "PUBLISHER_ACCESS", publisher_url, "publisher", str(paper.get("publisher") or "Publisher")
    elif doi_url:
        status, best, access_type, provider = "DOI_ONLY", doi_url, "doi", "DOI"
    elif paper.get("title"):
        status, best, access_type, provider = "METADATA_ONLY", "", "metadata", ""
    else:
        status, best, access_type, provider = "UNKNOWN", "", "unknown", ""
    for label, url in (("repository", repository_url), ("publisher", publisher_url), ("institution", openurl), ("doi", doi_url)):
        if url and url != best:
            alternatives.append({"access_type": label, "url": url})
    return {
        "access_status": status, "best_access_url": best,
        "access_type": access_type, "provider": provider,
        "requires_login": status in {"INSTITUTIONAL_ACCESS", "PROVIDER_LOGIN"},
        "institutional_access_possible": bool(openurl),
        "open_access": status == "OPEN_ACCESS", "pdf_available": bool(pdf_url),
        "html_available": bool(oa_url or repository_url), "doi_url": doi_url,
        "alternative_access_options": alternatives,
    }
