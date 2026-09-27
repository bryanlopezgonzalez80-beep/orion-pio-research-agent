# Orion Research Platform — Site build brief

Upgrade the existing published Orion Site in place and preserve its current public URL.

Build these primary areas: Search, Library, AI Analyzer, Topic Explorer, Evidence Dashboard, Legal Research (Puerto Rico / Federal U.S. / International), Teaching, Consulting, Workshop Builder, Favorites, Collections, Alerts, History, Sources, and Account.

Use D1 for durable structured records and R2 for user-owned/authorized files. Every academic search must normalize, deduplicate, classify, persist and then display results. Add source health, cache status and transparent per-source errors. Manual refresh must not have an artificial UI limit; protect providers with caching, backoff, quotas and circuit breakers. Add daily refresh at 07:00 Puerto Rico using the supported scheduler or the repository GitHub Actions workflow.

Use the repository's `orion_platform.py` source registry and query routing logic. For legal research, prioritize official primary sources and do not claim non-official results establish current law. Source login controls must open official account pages; do not collect or store third-party passwords. API keys must come only from Site secrets/environment variables.

When Sign in with ChatGPT is available, make collections, favorites, alerts and history user-scoped. Keep Site audience access separate from in-app identity.

Before publish, test anonymous/public visitor, authenticated visitor, empty result, duplicated DOI, malformed date, source timeout, HTTP 429, HTTP 5xx, revoked API key, partial provider outage, cache hit, cache expiry, Spanish/accented queries, Puerto Rico legal query, federal query, international query, mobile layout and persistence after refresh.
