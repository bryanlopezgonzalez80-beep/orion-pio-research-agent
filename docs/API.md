# Orion PIO Intelligence API

Phase 4 adds a FastAPI boundary over Orion's existing research, source catalog, favorites, and dual SQLite/PostgreSQL persistence layers. The API does not duplicate research providers or create a second database model.

## Run locally

Use Python 3.12 and install the normal requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn orion_api.main:app --host 0.0.0.0 --port 8000
```

Without `DATABASE_URL`, Orion uses its local SQLite fallback. To avoid modifying the repository database during development, set `PIO_DB_PATH` and `ORION_DB_PATH` to disposable files.

Interactive documentation is available at `/docs`; the OpenAPI document is `/openapi.json`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Optional PostgreSQL connection. Never expose it to clients or logs. |
| `OPENALEX_API_KEY` | Optional OpenAlex key. Orion works without it and rotates OpenAlex queries when anonymous. |
| `NCBI_EMAIL` | Optional contact identity for NCBI E-utilities; `CROSSREF_EMAIL` is used as a fallback. |
| `NCBI_API_KEY` | Optional PubMed/NCBI key. Not required; raises the supported E-utilities request rate. |
| `ORION_OPENALEX_QUERIES_PER_RUN` | Anonymous OpenAlex query budget per deep sweep; defaults to 12. |
| `ORION_BACKFILL_MONTHS_PER_RUN` | Historical Crossref month windows processed per daily run; defaults to 4. |
| `ORION_BACKFILL_FLOOR_YEAR` | Oldest year targeted by automatic historical backfill; defaults to 1950. |
| `ORION_GEO_PR_QUERIES_PER_RUN` | Puerto Rico geographic query budget; defaults to 6. |
| `ORION_GEO_US_QUERIES_PER_RUN` | United States geographic query budget; defaults to 4. |
| `ORION_GEO_LATAM_QUERIES_PER_RUN` | Latin America/Caribbean geographic query budget; defaults to 3. |
| `ORION_GEO_RUNTIME_SECONDS` | Separate Geographic Intelligence runtime budget; defaults to 180 seconds. |
| `ORION_ENV` | `development` by default; set explicitly to `production` only after production requirements are configured. |
| `ORION_ALLOWED_ORIGINS` | Comma-separated browser origins. Development defaults locally; production requires explicit HTTPS, non-local origins. Wildcards are rejected. |
| `ORION_API_KEY` | Optional only in development. Production requires at least 32 characters. Protected endpoints use `X-Orion-API-Key`; health, docs, and OpenAPI remain public. |
| `ORION_API_KEY_SECONDARY` | Optional overlap credential for zero-downtime rotation. |

The future GPT Site should be added as an explicit HTTPS origin in `ORION_ALLOWED_ORIGINS`. Phase 4 does not connect or deploy that Site.

## Endpoints

The canonical application routes use `/api/v1`. `/health` is also exposed without a prefix for infrastructure health checks.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Sanitized database reachability. |
| GET | `/api/v1/health` | Versioned health endpoint. |
| GET | `/api/v1/papers` | Paged papers with optional `query`, `source`, `year`, and allowlisted `geography` filters. |
| GET | `/api/v1/papers/{paper_id}` | Paper detail; IDs are text and may contain DOI-style punctuation or slashes. |
| GET | `/api/v1/radar` | Accumulated persisted research radar with optional `geography=puerto_rico|united_states|latam_caribbean`. |
| GET | `/api/v1/radar/status` | Deep-harvest coverage, historical cursor, source configuration flags, secondary-source links, and last manual refresh state. |
| POST | `/api/v1/radar/refresh` | Queue a non-blocking full live PIO taxonomy sweep. Returns `202`; clients poll `/radar/status` for completion. |
| GET | `/api/v1/sources` | Public source catalog and sanitized known status. |
| POST | `/api/v1/search` | Search local papers first, then real Orion research when appropriate. Academic queries may be entered in Spanish or English; supported Spanish PIO/RR. HH. concepts are expanded to an English scholarly variant and deduplicated. |
| GET | `/api/v1/library` | Paged favorite papers. |
| POST | `/api/v1/library` | Mark or unmark an existing paper as favorite. |

Example search:

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"psychological safety", "limit":20}'
```

If `ORION_API_KEY` is configured, add `-H 'X-Orion-API-Key: ...'` to data requests. This protects papers, radar, sources, search, and both library operations. `/health`, `/api/v1/health`, `/docs`, and `/openapi.json` remain public. When the variable is absent, the dependency allows local development without a key. No real key belongs in source control, logs, examples, or OpenAPI.

Production fails closed during startup if the API key or explicit CORS origins are missing or unsafe. See `docs/SECURITY.md` before setting `ORION_ENV=production` in Render.

## Validation and errors

Limits are bounded: paper pages allow 1–100 records, search allows 1–50, offsets are non-negative and bounded, and search queries contain 2–300 characters. FastAPI returns `422` for invalid input and `404` for an unknown paper. Sanitized service responses include `503` for database unavailability, `502` for external search failure, `504` for timeout, and `429` for upstream rate limiting. Stack traces and credentials are never response fields.

External APIs are mocked in unit tests. Run the normal suite with:

```bash
PYTHONPATH=. python -m pytest -m "not network and not postgres" -q
```

## Container readiness

The included Dockerfile uses Python 3.12, installs only repository requirements, runs as a non-root user, and exposes port 8000. Build and local run are intentionally separate from deployment:

```bash
docker build -t orion-api .
docker run --rm -p 8000:8000 orion-api
```

Supply configuration through the deployment platform's secret system. Do not bake secrets into the image.

## Production next steps

Phase 5 should replace or complement the optional shared key with identity, authorization, key rotation, per-client rate limiting, audit logging, observability, and deployment controls. A reverse proxy or managed API gateway should enforce request-size and traffic limits before production exposure.


## Radar reliability and source telemetry

Academic search responses include `metadata.source_meta` with per-source request count, cache hits, retries, rate-limit observations, pacing guidance, and result count. They also include directed links for Google Scholar, APA PsycNet, SIOP, and SSRN.

If an academic live search returns no direct result but the persisted research library is non-empty, the API returns accumulated Radar items with `origin="radar_fallback"` and `metadata.fallback_used=true`. Clients must label these as accumulated Radar content rather than direct matches to the current query.

See `docs/SOURCE_LIMITS.md` for current provider pacing guidance.


## Deep harvest API behavior

The daily cloud job and manual refresh endpoint share the same high-recall engine.

- The live sweep covers Orion's full PIO taxonomy plus umbrella and geographic queries. Crossref, PubMed, and Europe PMC are queried across the taxonomy. arXiv is added to technology/AI topics. Semantic Scholar is included when its key is configured.
- OpenAlex is deliberately rotated when no OpenAlex key exists so anonymous provider budget is not exhausted. Orion does not require an OpenAlex key.
- Daily automation also advances a resumable historical Crossref backfill in month-sized windows.
- After the global live sweep, Orion runs a separately budgeted geographic booster before historical backfill. It rotates Puerto Rico, U.S. state, and Latin America/Caribbean queries without multiplying the 188-query global taxonomy.
- `POST /api/v1/radar/refresh` starts the live sweep only; it does not run historical backfill in the request-triggered job. The route returns quickly and the worker persists articles query-by-query.
- `GET /api/v1/radar/status` is the polling/status surface. A client should show queued/running/completed/failed state and then refresh `GET /api/v1/radar` after completion.
- The manual refresh worker is best-effort within the current single API process. The scheduled GitHub Actions daily harvest remains the durable source of continuity; distributed job locking/queues belong to the scalability phase.

Search itself also widens to a historical provider pass when neither the local library nor the recent live search finds a match. This reduces the chance that a valid older PIO topic appears empty.

The system aims for maximum practical and lawful coverage. It does not scrape licensed databases or services that do not expose an authorized API, and it never claims that every indexed record is peer reviewed merely because its metadata came from a trusted index.


## Deep Harvest live progress

While a manual `POST /api/v1/radar/refresh` is running, `GET /api/v1/radar/status`
updates `manual_refresh` incrementally. The safe progress payload includes the
current phase, processed/total taxonomy queries, records received, unique papers
seen, journal-watch progress, and aggregate per-source counters. It does not
expose provider credentials, database URLs, or raw exception text.

Optional additive fields include `geography_phase`, `geo_queries_processed`,
`geo_queries_total`, and `geography_totals`. Existing Site clients may ignore
them. `/radar/status` also adds a `geography` block with coverage, persistent
rotation cursors, last refresh, discoveries, unique results, and partial source
incidents without renaming existing fields.

The Site may poll this status every 8–10 seconds and stop when
`manual_refresh.state` becomes `completed` or `failed`.
