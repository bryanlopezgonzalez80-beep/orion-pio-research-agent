# Orion Production Security

This document describes the Phase 8A security baseline. It contains no production values. Secrets belong only in the deployment platform or GitHub secret store.

## Runtime environments

`ORION_ENV` accepts exactly `development` or `production` and defaults to `development` for backward-compatible local use.

### Development

- `ORION_API_KEY` is optional. When absent, protected routes remain accessible for local development.
- `ORION_ALLOWED_ORIGINS` is optional and defaults to `http://localhost:3000,http://localhost:8501`.
- Explicit origins must still be valid HTTP(S) origins and wildcard CORS is rejected.

### Production

The application fails during startup unless all of these conditions hold:

- `ORION_ENV=production`;
- `ORION_API_KEY` exists and contains at least 32 characters;
- `ORION_ALLOWED_ORIGINS` is explicitly configured;
- every origin uses HTTPS;
- no origin is `localhost`, a `.localhost` hostname, `127.0.0.1`, or `::1`;
- wildcard origins are not allowed.

Configuration errors describe the missing or invalid setting but never echo its value. Do not add the future Site URL to source code; configure it through `ORION_ALLOWED_ORIGINS`.

## Authentication model

Clients send the shared internal credential through `X-Orion-API-Key`. Orion compares it using `hmac.compare_digest`. The value must never appear in URLs, query parameters, application logs, screenshots, issue reports, examples, or OpenAPI content.

Public endpoints:

- `GET /health`
- `GET /api/v1/health`
- `GET /docs`
- `GET /openapi.json`

Protected endpoints:

- `GET /api/v1/papers`
- `GET /api/v1/papers/{paper_id}`
- `GET /api/v1/sources`
- `POST /api/v1/search`
- `GET /api/v1/library`
- `POST /api/v1/library`

The shared key is an integration credential, not user identity or fine-grained authorization. A future phase should add scoped identities, audit trails, revocation, and per-client rate limits.

## Secret management and rotation

Store `ORION_API_KEY`, `DATABASE_URL`, and provider credentials only in Render or GitHub Secrets. Never commit them to `.env`, configuration files, Docker images, artifacts, test fixtures, or documentation.

To rotate `ORION_API_KEY`:

1. Generate a new high-entropy value of at least 32 characters in an approved secret manager.
2. Coordinate the change window with every authorized client.
3. Replace the value in Render without exposing it in logs or chat.
4. Update the authorized client through its secret-management interface.
5. Verify public health and an authenticated request.
6. Revoke the previous value and review access logs for unexpected failures.

Phase 8A supports one active shared key, so rotation requires coordination rather than an overlap period.

## CORS and response headers

CORS is an explicit browser-origin allowlist; it is not authentication. Production origins must be HTTPS and non-local. Responses include:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`
- `Cache-Control: no-store`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` in production only

No Content Security Policy is added in Phase 8A because an incorrect policy could break FastAPI Swagger documentation. Add CSP only after testing `/docs` and its required assets.

## Least privilege and supply chain

GitHub workflows use `contents: read`; checkout does not persist Git credentials. Automated radar and monitoring jobs never commit or push. Dependabot checks Python, GitHub Actions, and Docker dependencies weekly with bounded concurrent PRs. Dependency updates still require normal review and CI.

The Docker image runs as the non-root `orion` user. `.dockerignore` excludes `.env` files, Streamlit secrets, databases, reports, backups, tests, Git metadata, caches, and coverage output.

## Accidental exposure response

If a credential may have been exposed:

1. Treat it as compromised; do not paste it into an issue or log.
2. Revoke or rotate it immediately in the owning provider.
3. Remove it from Render/GitHub and authorized clients as applicable.
4. Review Git history, Actions artifacts, deployment logs, and access logs.
5. If committed, coordinate history remediation rather than merely deleting the latest file.
6. Document the incident without reproducing the secret and add a regression control.

Database and internal error responses are intentionally generic. Application code must not log authentication headers, complete exceptions containing connection strings, request bodies containing credentials, or environment mappings.
