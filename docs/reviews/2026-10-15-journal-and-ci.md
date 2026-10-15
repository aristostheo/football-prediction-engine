# Journal backfills and continuous checks

Follow-up to the [October 14 review](2026-10-14-review.md).

## Changes

- Added separate backend and frontend GitHub Actions jobs for pushes and pull
  requests to main. They install locked dependencies and run Python tests/lint,
  frontend tests/lint, and the TypeScript/Vite production build. Provider keys are
  not required; these checks use offline fixtures.
- Removed the journal's 14-day live-result cutoff. Local history is checked first,
  then the configured fixture provider can settle older unresolved forecasts.
- Replaced separate fixture-discovery and result caches with one bounded cache.
  Simultaneous requests for the same league/date share one provider load. Cached
  empty replies and provider failures also prevent immediate repeated calls.
- Limited each result-check request to eight uncached date loads and eight actual
  Goal HTTP attempts, counting pagination, league resolution and HTTP errors.
  Journal checks additionally share a 100-attempt UTC-day allowance per running
  API process. Cached and local results remain readable after budget exhaustion.
- Never-checked dates take priority over stale cache refreshes, allowing larger
  journals to progress rather than repeatedly spending their budget on the same
  recent dates.
- Added journal labels for deferred checks and unavailable providers. Previously
  confirmed results and the original saved forecast remain intact.
- Provider settlement requires matching league, UTC date, home/away orientation,
  finished status, non-negative integer scores and a consistent 1X2 result. A 0–0
  result is valid. The provider adapter supplies regulation-time scores for
  extra-time/penalty fixtures; extra-time or shootout scores alone cannot settle
  a regulation-time forecast.

## Quota limits

The 100-request allowance only covers journal checks. It does not count browsing
fixtures, badges, CLI results synchronization or other API clients. The cache and
allowance are in memory and reset on backend restart; multiple processes each
have their own allowance. They do not enforce an account-wide 1,000/day ceiling.
The existing incremental CLI sync and its request cap remain separate. See
[live fixture setup](../live-fixtures.md) for cache lifetimes and journal behavior.

## Validation

- 261 backend tests passed; Python lint passed.
- 10 frontend tests passed; ESLint and the TypeScript/Vite build passed.
- Tests include old-result batching, 0–0 settlement, discovery/journal cache reuse,
  future/local-only lookups, invalid provider-result rejection, shared daily
  allowances, HTTP failures, pagination/catalogue request accounting, cache
  expiration/eviction and concurrent load sharing.
- No authenticated live-provider requests were made: provider keys are unavailable
  in this environment. Historical data and production model parameters were not
  changed. The user's separately synced local results remain on their computer.

## Next work

Continue the review's remaining robustness fixes, starting with odds snapshot
timestamps, readiness reporting and missing static assets. Re-run model research
only after source coverage and runtime behavior are stable.

## Local update

Pull main, rebuild the frontend and restart the backend using the existing local
provider keys. This change does not require another results-sync run.
