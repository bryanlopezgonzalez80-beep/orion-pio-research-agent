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
| `ORION_ALLOWED_ORIGINS` | Comma-separated browser origins. Defaults to local development origins; wildcard origins are rejected. |
| `ORION_API_KEY` | Optional shared internal key. When configured, every `/api/v1` data endpoint requires `X-Orion-API-Key`; health, docs, and OpenAPI remain public. |

The future GPT Site should be added as an explicit HTTPS origin in `ORION_ALLOWED_ORIGINS`. Phase 4 does not connect or deploy that Site.

## Endpoints

The canonical application routes use `/api/v1`. `/health` is also exposed without a prefix for infrastructure health checks.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Sanitized database reachability. |
| GET | `/api/v1/health` | Versioned health endpoint. |
| GET | `/api/v1/papers` | Paged papers with optional `query`, `source`, and `year` filters. |
| GET | `/api/v1/papers/{paper_id}` | Paper detail; IDs are text and may contain DOI-style punctuation or slashes. |
| GET | `/api/v1/sources` | Public source catalog and sanitized known status. |
| POST | `/api/v1/search` | Search local papers first, then real Orion research when appropriate. |
| GET | `/api/v1/library` | Paged favorite papers. |
| POST | `/api/v1/library` | Mark or unmark an existing paper as favorite. |

Example search:

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"psychological safety", "limit":20}'
```

If `ORION_API_KEY` is configured, add `-H 'X-Orion-API-Key: ...'` to data requests. This protects papers, sources, search, and both library operations. `/health`, `/api/v1/health`, `/docs`, and `/openapi.json` remain public. When the variable is absent, the dependency allows local development without a key. No real key belongs in source control, logs, examples, or OpenAPI.

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
