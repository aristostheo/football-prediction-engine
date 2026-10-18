# Market freshness, readiness and error handling

Follow-up to the [October 14 review](2026-10-14-review.md) and
[journal/CI checkpoint](2026-10-15-journal-and-ci.md).

## Completed

- Cached market reads retain their original retrieval timestamp. The response
  also carries the oldest/newest valid reported quote updates, available source
  identities and the number of books with usable timestamps. Market-level update
  times take priority over bookmaker-level times. Missing, invalid, future and
  timezone-less update times remain unknown.
- Concurrent odds reads for the same league share one upstream fetch. The existing
  ten-minute cache remains; there is no extra periodic odds polling.
- Both dashboards distinguish retrieval time from reported quote age and preserve
  full quote precision. Editing prices clears live-snapshot provenance. The classic
  view also ignores odds responses made stale by fixture/mode/league/input changes.
- New journal records keep snapshot metadata separately from comparison time,
  without changing the original model probabilities or forecast timestamp. CSV
  exports include these audit fields and the history cutoff. Legacy comparison
  timestamps are explicitly labelled; older bookmaker update times are not invented.
- Added `/ready`: loads the engine through the existing shared initializer,
  reports per-league model readiness/result cutoffs and configured provider flags,
  and returns 503 when data/model loading fails or a league model is absent.
  Usable but dated data reports 200/degraded. `/health` remains a lightweight
  liveness endpoint and stays responsive during readiness initialization.
- Missing assets and unknown API paths return proper 404 JSON, while SPA navigation
  still works. A missing dashboard index returns 503.
- API-Football malformed JSON and unexpected top-level/nested shapes become
  controlled provider errors. Goal/Odds transport decoding errors are also handled.
- Non-finite historical prices and live bookmaker prices are excluded rather than
  producing invalid probability comparisons.

## Validation

- 291 backend tests passed; Python lint and `git diff --check` passed.
- 14 frontend tests passed; ESLint and the TypeScript/Vite production build passed.
- Regression cases cover cache timestamp stability/expiry, valid/unknown quote
  provenance, eight concurrent odds readers sharing one fetch, non-finite prices,
  malformed provider shapes, missing files/API paths, missing-history readiness,
  liveness during model initialization, all seven loaded model cutoffs, and journal
  comparison/export timestamps with original forecasts preserved.

Tests use controlled provider responses. No authenticated live football/odds calls
were made because keys are unavailable in this environment. No fresh device or
rendered-browser check was performed. The frontend tests cover helpers/storage;
they are not a mounted React or Safari/WebKit interaction suite.

## Boundaries and remaining work

This checkpoint does not change production probability weights, Elo/form/H2H
logic, goal fitting, historical results or the independent-model/market separation.
Readiness provider flags mean configured, not authenticated or plan-verified. Its
21-day freshness threshold does not understand international breaks or schedules.

The broader review still has open work: Greek historical/stage coverage,
postponement/reschedule linkage, durable model/data identity in the editable
browser journal, browser/device regressions, bounded next-match scans and wider
quota accounting, and reproducible research folds/refit cadence. No claim is made
that those larger checkpoints or the complete review are finished.

## Local use

Pull main, run `npm run build` in `web`, then restart the backend with your existing
keys. No results-sync run is required for this update. Open
`http://localhost:8000/ready` to inspect the loaded model's status; the first call
can take as long as the initial model fit and makes no provider calls.
