# Site v21 backend contract

Site v21 is not implemented or published by this change. This document defines additive API fields while preserving Site v20 behavior.

## Authentication and architecture

The Site calls the Orion API server-side using `X-Orion-API-Key`. It never connects to PostgreSQL and never exposes API keys, provider credentials, or `DATABASE_URL` to browser code. Public health endpoints remain unchanged.

## Daily tracking

`GET /api/v1/radar/status` retains all existing fields and adds:

- `corpus.total_papers`, `corpus.total_papers_persisted`, `corpus.new_this_run`;
- `run.new_papers_this_run`, `run.records_received_this_run`, `run.unique_seen_this_run`;
- `geography_summary.puerto_rico`, `united_states`, `latam_caribbean`, `global_or_unknown`;
- `historical.floor_year`, `current_month`, `oldest_completed_month`, `target_months_per_run`, `months_completed_this_run`, `tasks_completed`, `tasks_pending`, `estimated_months_remaining`;
- `evidence.peer_reviewed`, `preprints`, `systematic_reviews`, `meta_analyses`, `retracted`;
- `access.open_access`, `institutional_access`, `provider_login`, `metadata_only`, `requires_login`;
- `enrichment.completed`, `enrichment.pending`, `enrichment.by_status`;
- `citation_graph.papers_discovered`;
- `providers.health` and the existing registry/health arrays.

Corpus totals and current-run metrics are deliberately separate. `estimated_months_remaining` is `null` until a trustworthy estimate exists.

## Paper and radar filters

`GET /api/v1/papers` and `GET /api/v1/radar` use parameterized allowlisted filters:

- `geography=puerto_rico|united_states|latam_caribbean|global`
- `evidence_type=<bounded string>`
- `peer_review_status=CONFIRMED|LIKELY|UNKNOWN|NOT_PEER_REVIEWED`
- `access_status=OPEN_ACCESS|INSTITUTIONAL_ACCESS|PROVIDER_LOGIN|PUBLISHER_ACCESS|DOI_ONLY|METADATA_ONLY|UNKNOWN`
- `retraction_status=RETRACTED|EXPRESSION_OF_CONCERN|CORRECTED|UNKNOWN`
- `open_access=true|false`
- `source=<bounded string>`
- `year=<1800..2200>`

Pagination remains `limit` and `offset`; existing Site v20 parameters and response fields remain valid.

## Paper card

Existing title, authors, year, journal, DOI, URL, and abstract fields remain. Additive evidence fields include:

- `evidence_type`, `peer_review_status`, `publication_type`;
- `geography_primary`, `geography_tags`, `geography_basis`, `study_location`, `affiliation_locations`;
- `metadata_sources_count`, `metadata_provenance`;
- `retraction_status`, `correction_status`, `evidence_flags`;
- `access_status`, `best_access_url`, `access_type`, `access_provider`, `requires_login`;
- `institutional_access_possible`, `open_access`, `pdf_available`, `html_available`, `doi_url`, `alternative_access_options`.

Show a prominent warning when retracted or under expression of concern. Access buttons must use `best_access_url` and status: “Open article” for confirmed OA, “Access with institution” for OpenURL, or “Login with provider” for licensed access. Orion never receives the user’s provider credentials.
