# Orion Site v21 implementation specification

This is a build specification, not a publication instruction. Site v20 remains
unchanged and available. Site v21 must be reviewed separately and, when approved,
published in place at the existing public URL.

## Architecture and security boundary

The browser talks only to the Site server. The Site server calls the Orion API
through the existing server-side proxy and adds `X-Orion-API-Key` there. The
header, `DATABASE_URL`, provider credentials, stack traces, and raw upstream
errors must never enter client bundles, browser storage, URLs, analytics, or
rendered error messages. The Site never connects to PostgreSQL/Supabase.

Use `GET /api/v1/radar/status` as the single aggregate status request. Keep
paper/radar pagination and do not download the corpus to calculate metrics.
Protected API errors map to safe UI states: `401` configuration/authentication,
`429` temporarily rate limited, `503` temporarily unavailable, and `504`
timeout. Preserve already loaded Radar cards for every transient error.

## Explore / Radar composition

Use progressive disclosure in this order:

1. Search and existing filters/actions.
2. Compact **Seguimiento diario** summary.
3. Accumulated Radar cards.
4. Expandable evidence, provider, and historical details.

Keep Search, Library/favorites, analysis, existing filters, complementary links,
error behavior, accumulated results, and **Actualizar Radar ahora**. A search
never clears the accumulated Radar.

### Corpus and run metrics

Never combine these groups:

- **Corpus total:** `corpus.total_papers_persisted` (fall back to
  `corpus.total_papers` only when the former is absent).
- **Current run:** `run.new_papers_this_run`,
  `run.records_received_this_run`, and `run.unique_seen_this_run`.

Missing groups render as unavailable, not zero, unless the API explicitly sends
zero. Partial responses must not prevent the rest of the page from rendering.

### Geographic intelligence

Offer only the backend filter values `puerto_rico`, `united_states`,
`latam_caribbean`, and `global`. Cards may display `geography_primary`,
`geography_tags`, and an expandable `geography_basis`.

`study_location` describes study population/sample location.
`affiliation_locations` describes institutional affiliation. Never copy or label
an affiliation as a study location. When `geography_basis` contains only
`affiliation`, label it **Institutional affiliation**, not study geography.

### Evidence and integrity

Display `evidence_type`, `peer_review_status`, and `publication_type`
independently. `UNKNOWN` is a first-class peer-review state. Index presence alone
does not prove peer review. Label `PREPRINT` as not peer reviewed unless the API
explicitly says otherwise.

Show prominent, non-dismissible card warnings for `RETRACTED` and
`EXPRESSION_OF_CONCERN`; show `CORRECTED` as a visible informational notice.
Advanced details may expose `metadata_sources_count`, sanitized
`metadata_provenance`, `correction_status`, and `evidence_flags`. Do not derive an
opaque quality score.

### Access action mapping

Use only URLs returned by the API and retain `alternative_access_options` in an
expandable secondary menu.

| `access_status` | Primary action |
| --- | --- |
| `OPEN_ACCESS` | Open article |
| `INSTITUTIONAL_ACCESS` | Access with institution |
| `PROVIDER_LOGIN` | Access with provider |
| `PUBLISHER_ACCESS` | Open publisher page |
| `DOI_ONLY` | Open DOI |
| `METADATA_ONLY`, `UNKNOWN`, null | No full-access claim; show metadata only |

The action uses `best_access_url`, with `doi_url` only for DOI fallback. Respect
`requires_login`, `institutional_access_possible`, `open_access`,
`pdf_available`, and `html_available`. Orion never asks for third-party provider
credentials and never bypasses a paywall.

### Filters

Send only documented query parameters: `geography`, `evidence_type`,
`peer_review_status`, `access_status`, `retraction_status`, `open_access`,
`source`, and `year`. Enum controls must use the values in
`docs/SITE_V21_CONTRACT.md`; source/evidence options come from API data or the
documented contract, never free-form SQL-like expressions. Keep `limit` and
`offset` pagination.

## Daily tracking and Backfill Turbo

The compact summary uses `corpus`, `run`, `geography_summary`, `evidence`,
`access`, `enrichment`, `citation_graph`, and `providers`. Provider UI must show
`registered`, `implemented`, `configured`, `authorized`, and `active`
independently; registration alone never produces an Active badge.

Historical details use `historical.floor_year`, `current_month`,
`oldest_completed_month`, `target_months_per_run`,
`months_completed_this_run`, `tasks_completed`, `tasks_pending`, and
`estimated_months_remaining`. Null remaining time renders **Estimate not
available**.

During a running backfill, current-month progress is
`backfill_month_tasks_completed / backfill_month_tasks_total`; it may reset when
the month changes. `backfill_tasks_completed_total` is the monotonic run total.
Never chart the current-month counter as a cumulative total.

## Manual refresh state machine

1. `POST /api/v1/radar/refresh` once.
2. Treat `queued` and `already_running` as attachment to the same operation.
3. Poll `/api/v1/radar/status` every 8–10 seconds only while
   `manual_refresh.state` is `queued` or `running`.
4. Disable repeat refresh while active.
5. Stop polling for `completed`, `completed_with_warnings`, or `failed`.
6. On completion, refresh the paginated accumulated Radar. Warnings keep results
   and show a non-blocking partial-provider notice. Failure keeps prior results
   and shows a safe retry message.

## Responsive acceptance criteria

- Desktop: summary grid, filters, and cards without horizontal scrolling.
- Tablet: summary collapses to two columns; advanced sections remain expandable.
- Mobile/iPhone: one-column cards, 44px minimum action targets, wrapping chips,
  no fixed-width tables, and provider/provenance data behind disclosure controls.
- Primary card order: title, authors, year, source, evidence type, relevant
  geography, access action, integrity warning; advanced metadata is collapsed.

## Pre-publication gate

Do not publish until contract tests pass, production authentication is available
to the authorized server-side proxy, Site v20 regression checks pass, responsive
QA is complete, and a human approves publication. OpenAlex remains optional;
the global taxonomy remains exactly 188 queries.
