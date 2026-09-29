# Geographic Evidence Intelligence

Orion preserves the existing 188-query Global Deep Harvest. Geographic Evidence Intelligence is a separate rotating layer with independent query catalogs, cursors, budgets, metrics, and persisted status. It deliberately increases recall for Puerto Rico first, the United States second, and Latin America/Caribbean third without constructing an unbounded geography-by-topic matrix.

## What the classifier means

Geographic fields describe different evidence and must not be conflated:

- `study_location`: only an explicit sample or study location;
- `author_affiliation_location`: location inferred from structured or textual affiliation metadata;
- `publication_location`: explicit publication location when a provider supplies it;
- `geographic_mentions`: places mentioned in title, abstract, topics, or keywords;
- `geography_primary` and `geography_tags`: the strongest primary interpretation and all detected relevance labels;
- `geography_basis`: transparent bases such as `sample_explicit`, `affiliation`, or `query_context`;
- `geography_confidence`: confidence associated with the strongest named basis, not an opaque combined score.

An author at a Puerto Rico university does not prove a Puerto Rico sample. Bare `San Juan` is intentionally ambiguous; Puerto Rico requires disambiguating context. Query context is retained as lower-confidence relevance instead of being presented as an observed sample location.

## Discovery and sources

The booster uses existing scholarly integrations, caching, retries, source health, and circuit breakers. OpenAlex and Semantic Scholar participate only when their existing optional credentials are configured. No new credential is required.

Puerto Rico journal names are searched through permitted scholarly metadata APIs. CONUCO is registered as a directed/manual source: Orion does not scrape it and never assumes all CONUCO material is peer reviewed. Evidence types distinguish journal articles, preprints, conferences, reports, datasets, professional publications, theses/dissertations, and unknown material. arXiv remains a preprint source.

The future Data Intelligence catalog identifies O*NET, BLS, OPM/FedScope/FEVS, and NIOSH as separate workforce-data sources. Statistical series are not inserted into `papers`.

## Operations

Optional variables and defaults:

- `ORION_GEO_PR_QUERIES_PER_RUN=6`
- `ORION_GEO_US_QUERIES_PER_RUN=4`
- `ORION_GEO_LATAM_QUERIES_PER_RUN=3`
- `ORION_GEO_RUNTIME_SECONDS=180`

Daily automation runs global live harvest, Geographic Intelligence, and historical backfill in that order. Manual refresh remains asynchronous and runs a bounded booster without historical backfill. Individual provider/query failures and progress-callback failures do not discard prior work or abort the remaining geographic layers.

Deep Harvest does not crawl the entire Internet. It seeks maximum practical and lawful coverage through automatable academic metadata sources and directed links when automation is unavailable or unauthorized.

## Persistence and rollback

Geographic columns and PostgreSQL indexes are additive. Existing papers remain valid with empty/default geographic fields. Rollback consists of reverting the application commit; the nullable columns and indexes can remain harmlessly in place. Removing production columns is neither required nor recommended.
