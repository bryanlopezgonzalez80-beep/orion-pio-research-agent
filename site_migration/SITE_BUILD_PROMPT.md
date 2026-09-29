# Orion Research Platform — Site build brief

Upgrade the existing published Orion Site in place and preserve its current public URL.

Build these primary areas: Search, Library, AI Analyzer, Topic Explorer, Evidence Dashboard, Legal Research (Puerto Rico / Federal U.S. / International), Teaching, Consulting, Workshop Builder, Favorites, Collections, Alerts, History, Sources, and Account.

Use D1 for durable structured records and R2 for user-owned/authorized files. Every academic search must normalize, deduplicate, classify, persist and then display results. The search box must accept Spanish and English; Spanish PIO/RR. HH. topics should use the API bilingual expansion rather than requiring the user to translate them. The Radar must be cumulative: after each successful search, refresh it from `GET /api/v1/radar` so earlier results remain visible instead of being replaced by the latest search. Add source health, cache status and transparent per-source errors. Manual refresh must not have an artificial UI limit; protect providers with caching, backoff, quotas and circuit breakers. Add daily refresh at 07:00 Puerto Rico using the supported scheduler or the repository GitHub Actions workflow.

Use the repository's `orion_platform.py` source registry and query routing logic. For legal research, prioritize official primary sources and do not claim non-official results establish current law. Source login controls must open official account pages; do not collect or store third-party passwords. API keys must come only from Site secrets/environment variables.

When Sign in with ChatGPT is available, make collections, favorites, alerts and history user-scoped. Keep Site audience access separate from in-app identity.

Before publish, test anonymous/public visitor, authenticated visitor, empty result, duplicated DOI, malformed date, source timeout, HTTP 429, HTTP 5xx, revoked API key, partial provider outage, cache hit, cache expiry, Spanish/accented queries, Puerto Rico legal query, federal query, international query, mobile layout and persistence after refresh.


## Mandatory Radar reliability behavior

After every academic search:
1. Render direct results when present.
2. Always refresh the accumulated Radar from `GET /api/v1/radar`; a new search must never clear previously persisted articles.
3. If the search response has `origin=radar_fallback` or `metadata.fallback_used=true`, show those cards under a clear label such as "Radar acumulado — no son coincidencias directas de la consulta".
4. Render `metadata.source_meta` as a compact source-usage table showing source, status, results, network requests, cache hits, retries, 429 status, and pacing interval.
5. Always show `metadata.manual_links` under "Fuentes complementarias" so the user can open Google Scholar, APA PsycNet, SIOP, and SSRN for the same query.
6. Never show an empty Radar while persisted Radar articles exist.
7. If both live search and persisted Radar are empty, show the manual links and an explicit source-status explanation instead of a blank state.


## Comprehensive PIO coverage interface

Add a compact control to the Radar/Explore area labeled:

**Actualizar seguimiento diario**

Behavior:
1. On click, call `POST /api/v1/radar/refresh` through the existing server-side proxy and existing `ORION_API_KEY`.
2. Treat HTTP 202 as queued successfully. Show: "Actualización integral iniciada. Orión está recorriendo el catálogo PIO y las fuentes automáticas."
3. Treat HTTP 409 as already running. Show: "Ya hay una actualización integral en progreso."
4. While queued/running, poll `GET /api/v1/radar/coverage` every 8-12 seconds. Do not poll more aggressively.
5. Display:
   - persisted papers;
   - catalog topics;
   - catalog domains;
   - latest run status;
   - topics completed / total;
   - provider records seen;
   - unique papers processed;
   - source counts when present.
6. When the latest run finishes, refresh `GET /api/v1/radar?limit=100` and keep the Radar cumulative.
7. A manual refresh must never clear existing Radar cards while it runs.
8. If the refresh fails, keep existing Radar content and show a recoverable warning.
9. Do not expose stack traces, provider credentials, API keys, DATABASE_URL, or secrets.

Copy note shown near the control:
"Orión maximiza cobertura dentro de índices académicos confiables y sus límites de acceso. Ningún motor puede garantizar literalmente todo lo publicado en Internet. Las fuentes complementarias siguen disponibles para ampliar la búsqueda."

Keep the complementary links (Google Scholar, APA PsycNet, SIOP, SSRN) visible for user queries. Do not scrape those platforms from the browser or server unless an official supported API is added later.
