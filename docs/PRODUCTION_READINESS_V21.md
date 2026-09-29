# Orion production readiness for Site v21

This checklist describes the backend state after merged PRs #31 and #32 and this readiness pass. It does not authorize deployment or Site publication.

## Post-merge inventory

### IMPLEMENTED

- Exactly 188 global PIO queries, journal watch, rotating live coverage, and provider-local failure isolation.
- Geographic Evidence Intelligence for Puerto Rico, United States, Latin America/Caribbean, and global/unknown; affiliation remains separate from study location.
- Twelve-month adaptive historical target, granular month/provider/query-or-journal checkpoints, cursor protection, provider pacing, bounded retry/backoff, and circuit breaker infrastructure.
- Central source registry, canonical identifiers, field provenance, integrity indicators, bounded citation graph, legitimate access resolver, OpenURL configuration, provider metrics, and additive SQLite/PostgreSQL schema.
- API authentication, security headers, allowlisted filters, paginated radar, system monitoring, and read-only production health checks.

### PARTIALLY_IMPLEMENTED

- Citation graph: bounded graph engine exists; production OpenAlex/Semantic Scholar reference/citation fetchers and scheduled worker orchestration remain separate work.
- Metadata enrichment: queue and canonical merge contracts exist; provider-specific asynchronous workers still need incremental implementation.
- Open-source expansion: Crossref, OpenAlex, Semantic Scholar, PubMed, Europe PMC, and arXiv have real adapters. CORE, DOAJ, DataCite, ERIC, and SciELO are registered but do not claim active adapters.
- Evidence validation: transparent fields and retraction flags exist; provider-specific retraction/correction feeds still determine how much can be confirmed.

### MISSING

- Authorized production adapters for CORE, DOAJ, DataCite, ERIC, and SciELO.
- Licensed harvesting adapters for PsycInfo, Scopus, Web of Science, and ProQuest. These intentionally remain inactive.
- A scheduled enrichment/citation worker. No heavy work runs inside GET requests.

### NOT_REQUIRED

- Direct browser/Site database access, credential collection, paywall bypass, scraping, destructive migrations, or a single opaque evidence-quality score.
- Site v21 publication in this change.

## Deployment checklist

- [ ] Review and merge through protected `main`; do not deploy this PR branch directly.
- [ ] Confirm CI, CodeQL, and dependency audit pass.
- [ ] Take the normal managed PostgreSQL backup/snapshot before rollout.
- [ ] Confirm `DATABASE_URL`, `ORION_ENV=production`, `ORION_API_KEY`, and explicit HTTPS `ORION_ALLOWED_ORIGINS` remain configured in Render. Do not print their values.
- [ ] Deploy the normal API image. On the first database connection, `ensure_postgres_schema()` applies `database/schema_postgres.sql` transactionally. Statements are additive (`CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`); there is no DROP, TRUNCATE, or data reset.
- [ ] Verify `/health` and `/api/v1/health`, then authenticate and verify `/api/v1/radar/status`, `/api/v1/papers`, and `/api/v1/sources`.
- [ ] Run the Daily workflow once manually only if normal operational policy permits it. It resumes the current incomplete historical month, skips completed task checkpoints, queues newly persisted papers for enrichment, and continues other providers if one fails.
- [ ] Confirm Site v20 still loads and ignores additive response fields.
- [ ] Do not publish Site v21 until its separate review is complete.

## Environment variables

Optional tuning/configuration introduced by the evidence engine:

- `ORION_BACKFILL_TARGET_MONTHS_PER_RUN`
- `ORION_CITATION_MAX_DEPTH`
- `ORION_CITATION_MAX_NODES`
- `ORION_CITATION_MIN_RELEVANCE`
- `ORION_INSTITUTION_NAME`
- `ORION_OPENURL_BASE`
- `ORION_OPENURL_ENABLED`
- `CORE_API_KEY`

Registered licensed-provider controls (none activates harvesting because adapters are not implemented):

- `PSYCINFO_API_ENABLED`, `PSYCINFO_API_KEY`, `PSYCINFO_API_AUTHORIZED`
- `SCOPUS_API_ENABLED`, `SCOPUS_API_KEY`, `SCOPUS_API_AUTHORIZED`
- `WOS_API_ENABLED`, `WOS_API_KEY`, `WOS_API_AUTHORIZED`
- `PROQUEST_API_ENABLED`, `PROQUEST_API_KEY`, `PROQUEST_API_AUTHORIZED`

Existing provider identity/key variables remain optional: `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `CROSSREF_EMAIL`, `NCBI_EMAIL`, and `NCBI_API_KEY`.

## Provider lifecycle

The source API reports five separate booleans: `registered`, `implemented`, `configured`, `authorized`, and `active`.

- Implemented and active: Crossref, OpenAlex, Semantic Scholar, PubMed, Europe PMC, arXiv.
- Registered, not implemented/active: CORE, DOAJ, DataCite, ERIC, SciELO, Redalyc, Latindex.
- Registered licensed access stubs, not implemented/active: APA PsycInfo, Scopus, Web of Science, ProQuest.
- Redalyc, Latindex, CONUCO/UPR and other regional sources remain directed/manual unless an authorized automation method is reviewed.

## First Daily run

The run performs the 188-query rotating live sweep, bounded geographic booster, and adaptive backfill. The target is 12 completed historical months, but a provider 429 pauses that provider, preserves successful records, leaves unstarted tasks `PENDING`, and does not advance the month cursor. The final state is `COMPLETED_WITH_WARNINGS` when provider incidents occur.

## Rollback

Revert the application commits and redeploy the previous image. Additive columns/tables can remain unused and must not be dropped during emergency rollback. Do not delete new checkpoints or external identifiers. If an application regression affects scheduled harvesting, disable the workflow run operationally or roll back the image; do not remove `DATABASE_URL` as a routine rollback because that would switch persistence to ephemeral/local SQLite. Site v20 requires no rollback because it is not modified here.
