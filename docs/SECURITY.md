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
- `ORION_API_KEY_SECONDARY`, when present for rotation, contains at least 32 characters and differs from the primary;
- `ORION_ALLOWED_ORIGINS` is explicitly configured;
- every origin uses HTTPS;
- no origin is `localhost`, a `.localhost` hostname, `127.0.0.1`, or `::1`;
- wildcard origins are not allowed.

Configuration errors describe the missing or invalid setting but never echo its value. Do not add the future Site URL to source code; configure it through `ORION_ALLOWED_ORIGINS`.

## Authentication model

Clients send the shared internal credential through `X-Orion-API-Key`. Orion compares it using `hmac.compare_digest`. `ORION_API_KEY` is the primary credential. An optional `ORION_API_KEY_SECONDARY` enables a temporary overlap during rotation; it must contain at least 32 characters and differ from the primary. The application never returns which credential matched. Credential values must never appear in URLs, query parameters, application logs, screenshots, issue reports, examples, OpenAPI content, fingerprints, or database records.

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

Store `ORION_API_KEY`, `ORION_API_KEY_SECONDARY`, `DATABASE_URL`, and provider credentials only in Render or GitHub Secrets. Never commit them to `.env`, configuration files, Docker images, artifacts, test fixtures, or documentation.

### Zero-downtime key rotation

Use placeholder names `OLD` and `NEW`; never place real values in source code, tickets, documentation, or chat.

Initial state:

- `ORION_API_KEY=OLD`
- `ORION_API_KEY_SECONDARY` unset

Rotation procedure:

1. Generate `NEW` outside the codebase using an approved secret manager.
2. In Render, keep `ORION_API_KEY=OLD`, set `ORION_API_KEY_SECONDARY=NEW`, and deploy. Both credentials are then accepted.
3. Change the GPT Site secret from `OLD` to `NEW`. Validate authenticated Site and API operations.
4. In Render, set `ORION_API_KEY=NEW`, remove `ORION_API_KEY_SECONDARY`, and deploy. `OLD` is then revoked.

If validation fails during step 3, restore the GPT Site secret to `OLD`; the overlap configuration still accepts it. If the final deployment fails, restore the overlap configuration (`OLD` primary and `NEW` secondary), deploy, and investigate before attempting the cutover again. Never swap or remove the old credential until the Site has been validated with the new one.

### API rate limits

Authenticated traffic uses separate sliding-window quotas per credential slot and operation category:

- search: `ORION_RATE_LIMIT_SEARCH_PER_MINUTE`, default 20;
- library writes: `ORION_RATE_LIMIT_WRITE_PER_MINUTE`, default 60;
- reads: `ORION_RATE_LIMIT_READ_PER_MINUTE`, default 120.

Values must be positive integers no greater than 10,000. Authentication occurs before quota consumption, so missing or invalid credentials return `401` without creating state. Exceeded quotas return `429` with a `Retry-After` header and no credential, IP, or internal identifier.

The limiter is thread-safe and stores at most six in-memory buckets: primary and secondary credentials across read, write, and search. It uses monotonic time and removes expired timestamps. Public health and documentation endpoints are not limited.

This limiter is intentionally per process. If Orion later runs multiple API instances, Phase 9 must evaluate a distributed limiter so the quota is consistent across instances.

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

### Supply-chain security

- Every GitHub Action is pinned to a full, immutable commit SHA. A trailing comment records the corresponding release tag so updates remain reviewable.
- Dependabot checks pip, GitHub Actions, and Docker weekly. It may open update pull requests, but automatic merging is not enabled.
- CodeQL analyzes Python on pull requests, pushes to `main`, and a weekly schedule. Only that job receives `security-events: write`, which is required to publish analysis results.
- `pip-audit` checks `requirements.txt` on pull requests, manual dispatch, and a weekly schedule. It receives no secrets and does not suppress advisories.
- Dependency and workflow updates require human review, successful CI, and evaluation of upstream release notes before merge.

When an audit reports a CVE, record the affected package and advisory without copying secrets or production data. Confirm whether Orion uses the vulnerable code path, identify the smallest compatible fixed version, test the upgrade in a dedicated pull request, and obtain manual approval before merge. Do not hide the finding with an ignore flag merely to make CI pass. If no fix exists, document the exposure and compensating controls, then track the advisory until remediation is available.

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
