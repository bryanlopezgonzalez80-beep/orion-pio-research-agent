# Orion Deep Harvest — Next Generation

This release evolves the existing Deep Harvest incrementally. It keeps the 188-query global catalog and published API contracts while introducing explicit evidence-intelligence boundaries.

## Processing model

```text
discover -> normalize -> canonicalize -> deduplicate -> persist
         -> enrichment -> integrity -> geography -> access -> citations
```

Discovery remains cheap and provider-isolated. Enrichment and citation chaining are bounded, optional stages. PostgreSQL remains the production system of record; SQLite remains available for local development and tests.

## Source registry

`source_registry.py` is the central capability registry. A source can have multiple roles: discovery, enrichment, citation graph, full text, validation, access provider, regional, or data source. Capability does not assert quality, reachability, licensing, or peer review.

Crossref, OpenAlex, Semantic Scholar, PubMed, Europe PMC, CORE, DOAJ, DataCite, ERIC, arXiv, SciELO, Redalyc, and Latindex have declared roles. Some are currently registry/enrichment targets rather than automated harvesters. Licensed connectors are fail-safe access stubs and remain inactive even when enablement, server-side credentials, and authorization flags exist; a reviewed adapter must be implemented before harvesting can become active.

No connector receives end-user credentials. Enabling a stub is not authorization to harvest; licensing and provider terms must be reviewed first.

## Identity and provenance

`evidence_pipeline.py` normalizes DOI values and prioritizes DOI, PMID/PMCID, OpenAlex, Semantic Scholar, and publisher identifiers. Title-author-year is a conservative last resort. `paper_external_ids` stores aliases without replacing the existing paper identifier. `metadata_provenance` records which sources supplied each field.

## Integrity

`evidence_integrity.py` stores independent indicators instead of an opaque score. A DOI is never treated as peer-review proof, arXiv is classified as a preprint source, and retractions remain visible with evidence flags. Study design remains `UNKNOWN` when metadata is insufficient.

## Access

`access_resolver.py` selects the best known legitimate route: confirmed OA, repository, institutional OpenURL, licensed provider, publisher, DOI, or metadata only. A URL is not presented as a PDF unless the provider confirmed it. Authentication occurs at the institution or provider; Orion never accepts or stores those credentials.

Optional institutional settings are `ORION_INSTITUTION_NAME`, `ORION_OPENURL_BASE`, and `ORION_OPENURL_ENABLED`.

## Historical backfill

The default target is 12 historical months per scheduled run (`ORION_BACKFILL_TARGET_MONTHS_PER_RUN`). This is a target, not a guarantee. Checkpoints are stored per month, provider, task type, and query/journal. Completed tasks are not repeated. Rate-limited and retryable tasks remain resumable, and the month cursor advances only when all critical tasks are complete.

Manual refresh still calls `run_deep_harvest(include_backfill=False)`, so it does not run historical backfill or unbounded enrichment.

## Citation graph

`citation_graph.py` enforces `ORION_CITATION_MAX_DEPTH` (default 1), `ORION_CITATION_MAX_NODES` (default 100), and `ORION_CITATION_MIN_RELEVANCE` (default 0.65). Provider failures are isolated and recorded without aborting other providers.

## Safety and remaining integrations

- Schema changes are additive; no corpus rows are deleted.
- No secrets are returned by the registry or stored in provenance.
- O*NET, BLS, FEVS, and NIOSH remain a separate future `DATA_SOURCE` track and are not stored as papers.
- CORE, DOAJ, DataCite, ERIC, SciELO, and citation-provider network adapters require provider-specific implementation and terms validation before production automation. This release establishes their contracts without pretending they are already harvested.
- The GPT Site is unchanged. New API fields are additive and existing response fields remain available.
