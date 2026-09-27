# Orion Research Platform — ChatGPT Sites migration package

## Objective
Preserve the published Orion URL while migrating the application toward durable storage, authentication, source resilience and daily refresh.

## Target architecture
- UI: ChatGPT Site
- Structured persistence: D1
- Files/PDFs/objects: R2
- Secrets: Site environment/secrets only
- Scheduled refresh: supported Site scheduler when available, otherwise the GitHub Actions daily workflow
- Identity: Site audience controls plus Sign in with ChatGPT when enabled

## Migration order
1. Create D1 and apply `schema.sql`.
2. Import the existing library from SQLite/JSON.
3. Replace local/in-memory library writes with D1 upserts.
4. Bind R2 only for files the owner has rights to retain; keep metadata and source URLs in D1.
5. Scope collections, favorites, alerts and history to authenticated user id.
6. Move every credential to Site secrets.
7. Port `orion_platform.py` routing, cache policy and source registry.
8. Keep legal search primary-source-first; never fabricate results when no stable official API exists.
9. QA public visitor, authenticated visitor, mobile view, empty results, duplicate DOI, malformed metadata, timeout, 429, 5xx, revoked key, cache hit/expiry and partial outage.
10. Republish in place without changing the existing public URL.

## Failure policy
A single provider failure must not fail the whole search. Retry transient failures, cache repeat requests, open a temporary circuit after repeated failures, report skipped/failed sources, deduplicate before persistence, and never store third-party passwords or expose API keys to browser code.
