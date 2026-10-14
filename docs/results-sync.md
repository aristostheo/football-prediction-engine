# Import newer completed results locally

The Goal API importer adds finished results to an ignored local model snapshot.
It does not change model weights, add betting odds as features, or modify the
Git-tracked OpenFootball bundle.

## Run from the repository root

First preview the range, without an API key or network requests:

```bash
uv run python -m football_predictor.results_sync --dry-run
```

Then import using your existing Goal API key:

```bash
GOAL_API_KEY='YOUR_GOAL_KEY' uv run python -m football_predictor.results_sync
```

The initial default catch-up checks all seven leagues, starting two days before
each league's latest stored result and ending yesterday in UTC. On the October 14 snapshot,
that is September 18 through October 13: 182 date queries and up to five league
catalogue lookups. Extra pages also count against the **250-request hard cap**.
The cap applies to new network requests in this run, not your account's total
daily usage. Cached responses do not consume the cap. A provider
error or exhausted request budget stops the run without publishing partial
results. There are no automatic retries that consume more quota.

To start with the Premier League only:

```bash
GOAL_API_KEY='YOUR_GOAL_KEY' uv run python -m football_predictor.results_sync --league premier_league
```

`--league` can be repeated. `--since YYYY-MM-DD`, `--through YYYY-MM-DD` and
`--max-requests N` allow a bounded backfill. Each league's range must be 1–60
days, cannot skip the unqueried gap after its latest result, and cannot include
today or future dates. If the history is over 60 days old, backfill in consecutive
chunks using `--through`, or use a separately verified historical source.

After a successful import, inspect the actual cutoffs:

```bash
uv run python -m football_predictor --check-data
```

Stop your backend with Ctrl+C, then restart it with the usual keys:

```bash
GOAL_API_KEY='YOUR_GOAL_KEY' THE_ODDS_API_KEY='YOUR_ODDS_KEY' uv run uvicorn football_predictor.api:app --host 0.0.0.0 --port 8000
```

The API automatically uses `data/local/historical_matches.csv.gz` when present.
`HISTORICAL_MATCHES_PATH`, if explicitly configured, still takes precedence.
The engine reloads when the backend restarts; it does not refit during an
already-running process. Forecast context and the displayed history date will
then reflect the imported games. Original journal forecasts remain unchanged.

Repeat the sync after pulling new bundled data. It reconciles the latest bundle
with your local snapshot before querying, preserving locally imported results.
Both local data files are ignored by Git, so they do not cause pull conflicts.
The public-source scheduled workflow continues to update only the tracked bundle
and does not use your local key or upload Goal API results.

## What is accepted

- The existing, documented [date fixture endpoint](https://goal-api.com/blog/football-fixtures-standings-page), with Goal API's internal league IDs and complete pagination. Five league IDs are resolved using the existing catalogue adapter.
- Finished `FINISHED`/`FT` fixtures whose UTC kickoff matches the requested date
  and precedes retrieval, with a consistent season and a declared regular-stage
  label (`Current`, `Regular`, `Regular Season` or `regular-season`).
- Registered, explicit club aliases, mapped to the same canonical history.
- Non-negative integer regulation-time goals. Explicit malformed full-time
  scores are rejected rather than replaced with a running or extra-time total.

Postponed, cancelled, live, extra-time/penalty and nonregular-stage fixtures are
excluded. Missing stage/season metadata on a finished fixture fails the import;
unknown club labels require a reviewed registry addition. The importer collects
all unknown clubs across the selected dates and leagues, reports them together,
and refuses to publish the snapshot until they are resolved. Wrong-league responses,
repeated pages, changing totals, missing pagination and partial pages fail closed.

## Merge and provenance

Prior fixture identities cannot disappear. Matching overlaps must agree on
season, goals and outcome; conflicting scores need manual source review.
New duplicate venue pairs and same-day team collisions are rejected. All merged
rows pass the canonical HistoricalMatch and collection validators. The existing
baseline contains a repeated Greek venue pair in 2023-24; it is retained for
source review, while newly introduced repetitions remain blocked.

Rows retain source name, provider fixture URL and retrieval timestamp. The local
manifest records query dates, accepted/skipped counts, response hashes, input-facts
hash, dataset checksum and requests used. Credentials are never stored. Successful
raw responses are cached locally for one hour under `data/local/goal_api_cache/`,
which is ignored by Git; this allows retries after a failed import to reuse
completed requests. The original fetch times are retained in imported rows and
manifest response metadata. `--fresh` bypasses the cache, and expired or invalid
cache entries are refetched. Files are staged before replacement; a failed manifest publication
rolls back the CSV. An unchanged rerun preserves both files' bytes. An empty
response does not create a fresh-looking local snapshot.

## Limits and verification

The importer cannot establish that an empty provider response means no match was
played, or guarantee that every historical result is present. The coverage table
reports the latest accepted result, not complete season coverage. Late source
corrections and metadata ambiguities remain possible; conflicts are deliberately
not resolved by guessing. Previously saved forecasts cannot be retroactively
updated and still count as their original, dated predictions.

Offline tests use realistic provider-shaped payloads and the complete 24,950-row
bundle. They exercise regulation scores, all failure/merge controls, pagination,
request caps including catalogue calls, idempotence, checksum/rollback behavior,
runtime path selection and pre-match leakage controls. Authenticated provider
verification requires running the command on the computer with your key. Until
that succeeds and the reported cutoff advances, freshness remains unresolved.

Validation after the alias/retry fix on October 14: all 210 backend tests,
backend lint and the diff whitespace check passed. The earlier sync checkpoint
also passed ten frontend tests and frontend lint/build. The refresh workflow runs
ingestion, coverage and sync tests without provider credentials.

## October 14 alias fix

The provider spelling `Celta de Vigo` is now an explicit alias of `RC Celta de Vigo`.
Tests cover both the completed-result parsing path and league isolation; reserve-team
names are not guessed. The previously failed version had no retry cache, so its
54 responses cannot be recovered. One retry must fetch those dates again; subsequent
immediate retries reuse the new cache. The user's log confirms 10 newer Premier
League and seven newer Greek results were returned, but none was published by
that failed run. Coverage remains pending a successful complete merge.

The complete user retry reported seven more provider spellings. All map to
clubs already present in the bundle; no new team histories or priors are added:

| Provider label | Existing canonical identity |
| --- | --- |
| Elversberg | SV 07 Elversberg |
| Paderborn | SC Paderborn 07 |
| Deportivo de La Coruña | RC Deportivo La Coruña |
| Racing de Santander / Racingde Santander | Real Racing Club de Santander |
| Troyes | ESTAC Troyes |
| Estrela | CF Estrela da Amadora |
| Frosinone | Frosinone Calcio |

Tests cover all aliases, exact historical identity, completed-result parsing,
reserve-team rejection and serving predictions using the existing histories.
These mappings do not change the model design. Retry within the one-hour cache
window to reuse the 187 saved responses; expired entries are fetched again.

Club identity references: [Elversberg](https://sv07elversberg.de/),
[Paderborn](https://www.scp07.de/),
[Deportivo](https://www.rcdeportivo.es/es/datos-generales),
[Racing](https://www.realracingclub.es/el-club),
[Troyes](https://www.estac.fr/),
[Estrela](https://www.ligaportugal.pt/team/112/estrela-amadora/20262027),
[Frosinone](https://www.frosinonecalcio.com/).


## Daily quota control

After a complete, validated sync, `data/local/results_sync_state.json` remembers
the last checked date for each league. Subsequent default runs cover only dates
since that checkpoint with a one-day overlap, plus unresolved unfinished games
within the 60-day window. A normal next-day run checks three dates per league:
21 league/date queries across all seven leagues, plus at most five catalogue
lookups and extra pages. A same-day repeat normally checks 14 league/date pairs;
within the one-hour cache window those responses can cost zero new API requests.
A week without matches does not expand every daily run back to the last result.

The checkpoint advances only after the full selected scope passes validation.
An empty successful response advances checked dates but never changes the model's
reported last result. Failed imports keep the checkpoint unchanged. If local
history is removed or its league cutoff/count changes independently, a matching
checkpoint is required before skipping dates; otherwise the importer falls back
to a catch-up plan. `--since` explicitly requests a backfill and overrides the
short routine window. This remains useful for provider results published more
than a day late; checked dates are not proof of complete coverage.

Run the sync after matchdays. Opening the dashboard does not invoke this importer.
`--max-requests` caps new network calls in that run, including extra pages and
catalogue queries; it cannot account for calls made by the dashboard or other
clients on the same API key. The 1,000-request account allowance remains shared
across those clients.

Validation for the seven-alias and daily-quota update: the full 239-test backend
suite passed, followed by 65 targeted checkpoint/import tests including an added
failure test. That failure test confirms an unsuccessful CLI import cannot advance
checked dates or publish a local snapshot. Backend lint and diff checks passed.
