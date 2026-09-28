# Orion Academic Source Limits

This file records the provider constraints Orion uses for safe pacing. Limits can change; production code must still honor HTTP 429 and Retry-After when a provider sends them.

## Automated sources

| Source | Orion policy | Provider guidance used |
| --- | --- | --- |
| OpenAlex | No artificial per-request delay; cache results and back off on 429. Configure `OPENALEX_API_KEY` for normal production usage. | OpenAlex currently gives keyless use a small daily budget and a free API key a larger daily budget. Direct search calls consume metered usage; responses expose remaining usage in rate-limit headers. A hard request-rate ceiling also applies. |
| Crossref | 1.0 s minimum between list/search requests without `CROSSREF_EMAIL`; about 0.34 s with it. | Public pool list queries: 1 request/s, concurrency 1. Polite pool list queries: 3 requests/s, concurrency 3. |
| Semantic Scholar | 1.0 s minimum. | The introductory API-key limit is 1 request/s across endpoints. Unauthenticated traffic shares a public pool and may be throttled. |
| Europe PMC | 0.25 s conservative Orion pacing plus retry/backoff. | Europe PMC provides REST APIs and bulk/OAI alternatives, but its public developer pages do not publish a fixed numeric request quota. |
| arXiv | 3.0 s minimum, serialized by Orion's process-wide pacer. | Legacy API guidance: no more than one request every 3 seconds and one connection at a time. |

## Manual / complementary sources

Google Scholar, APA PsycNet, SIOP, and SSRN remain directed browser searches in Orion. Orion does not scrape these sites or pretend that they are automated API results. Every academic search response should expose links for these sources so a user can continue discovery if an automated provider is empty, rate-limited, or temporarily unavailable.

## Radar behavior

The Radar is cumulative. A live provider miss must not erase prior research. If a search produces no direct automated result, the API returns persisted Radar items with `origin=radar_fallback` and `metadata.fallback_used=true`. The UI must label these as accumulated Radar items, not as direct matches to the current query.

Each live search reports per-source telemetry:

- network request count;
- cache-hit count;
- retry count;
- whether a 429 was observed;
- result count;
- source status;
- minimum pacing interval;
- human-readable provider guidance.

This telemetry counts Orion's activity for that search. It is not a guaranteed provider-wide remaining-quota figure unless a future provider integration explicitly reads and exposes a trustworthy remaining-quota header.
