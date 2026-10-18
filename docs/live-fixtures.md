# Live fixtures and API service

The service exposes an optional live-fixture adapter and a prediction endpoint:

```bash
GOAL_API_KEY=your_goal_key \
THE_ODDS_API_KEY=your_odds_api_key \
uv run uvicorn football_predictor.api:app --reload
```

- `GET /health` confirms that the service is running.
- `GET /ready` loads the local prediction engine if needed and reports model
  availability and actual results cutoffs for all seven leagues. Missing/unusable
  history or a missing league model returns HTTP 503. A usable engine with dated
  history returns HTTP 200 with `status: degraded`; the 21-day age threshold is
  a coverage warning, not a match-schedule check. The first request can take as
  long as model initialization. This runs in a worker thread so `/health` stays
  responsive. Provider flags report configuration only; readiness makes no live
  provider calls and does not test key validity or plan coverage.
- `GET /fixtures?competition=premier_league&date=YYYY-MM-DD` reads scheduled
  fixtures from Goal API when `GOAL_API_KEY` is configured.
- `POST /predict` accepts canonical names or registered club aliases and a fixture date after
  the local historical dataset's final result.
- `GET /odds` retrieves upcoming 1X2 market odds for a scheduled fixture when
  `THE_ODDS_API_KEY` is configured. Results are a bookmaker consensus with each
  book's margin removed and are cached for 10 minutes.
  Concurrent reads for a league share one upstream fetch. `fetched_at` remains
  the original snapshot retrieval time on cache hits. `oldest_quote_at` and
  `newest_quote_at` preserve reported bookmaker/1X2-market update times, with
  market-level times preferred; absent, malformed, timezone-less or future times
  remain unknown. `timestamped_bookmaker_count` reports how many usable books
  supplied valid times, and `bookmakers` lists available source identifiers.
  These inverse fair-consensus prices are not necessarily offered betting prices.

- `GET /fixtures/next?competition=...&from=YYYY-MM-DD` checks upcoming dates in order and returns the earliest future fixture in its three-week search window.
- `GET /teams?competition=...` returns teams from that league's most recent recorded season for searchable hypothetical matchups.
- `GET /team-badges?competition=...` reads the league's team catalogue from the configured live fixture provider and returns trusted badge URLs keyed by the predictor's canonical team names. Missing provider data leaves the initials fallback in place.

The supported competitions are Premier League, Super League Greece, La Liga,
Bundesliga, Serie A, Ligue 1, and Primeira Liga. The dashboard opens on the next scheduled match for the selected league. Use
**Explore matchup** to choose any two teams from searchable league-specific
options. Those forecasts use the latest available results and are labeled
hypothetical. Odds are optional and collapsed until requested. If no fixture is
found in the initial three-week window, users can search the following window.

## Provider decision

V1 prefers the optional [Goal API](https://goal-api.com/) adapter for current
fixture discovery. The user's free plan allows 1,000 requests per day. The
date-fixture endpoint's `leagueId` filter uses Goal API's internal league `id`
from `/leagues`, not its numeric coverage/API identifier. Existing Premier
League and Greece internal IDs are configured directly. For the five new
competitions, the provider searches `/leagues?search=...`, matches both the
league name and its country (search results can span countries), and caches the
returned internal ID for that server process.
Each resolved league costs one additional request on first use after a server
restart.

The API caches fixture dates for ten minutes and team badge catalogues for a
day. A first uncached "next match" search can still query one date at a time,
up to the configured 21-day window. Switching leagues or reloading after cache
expiry uses more requests, so avoid repeatedly refreshing while testing. These
caches are in-memory and reset when the local server restarts.

[API-Football](https://www.api-football.com/) remains an optional fallback when
`API_FOOTBALL_KEY` is also configured. Provider order is:

1. Goal API when `GOAL_API_KEY` is present.
2. API-Football when `API_FOOTBALL_KEY` is present and Goal API fails, or when
   it is the only configured provider.

Keys are read only by the backend from environment variables and must never be
committed or exposed to the browser. Manual prediction remains available with
no fixture-provider key. Live market odds are optional; set `THE_ODDS_API_KEY`
in the backend environment (including the Render service environment) to enable
the dashboard's **Load live market odds** control. The user interface can still
accept manually entered 1X2 odds without this key.

The live odds adapter uses The Odds API sport keys for the selected competition,
European bookmaker region, and 1X2 h2h market. It averages
per-book margin-removed probabilities across books that quote all three
outcomes, then presents fair decimal prices for the existing market forecast
path. A fixture must match both teams and kickoff time. A missing quote or
provider error is shown in the dashboard; no quote is guessed. The adapter is
for prospective dashboard use only: its free-tier data is not used for
historical training or walk-forward evaluation. Quotes are fetched on demand
and cached in memory for ten minutes.

Run the server from the repository root. Predictions load the included
`data/model/historical_matches.csv.gz` by default. Set `HISTORICAL_MATCHES_PATH`
only when you want to use a different historical dataset.

To update that bundled history from OpenFootball locally, run
`uv run python -m football_predictor --refresh` from the repository root. It
downloads and validates all configured seasons, rejects unexpected fixture
removals, and writes a provenance manifest. GitHub Actions also runs the same
check every Tuesday and can be started manually from the Actions tab. It
commits only when match results change; the hosted Render service then deploys
that commit. The API itself does not fetch results per request. For local
development, restart the service after refreshing the dataset.

## Prospective scorecard

The dashboard records timestamped forecasts only when an upcoming fixture has
an exact timezone-aware kickoff time, which comes from live fixture discovery.
Records stay in that browser's local storage; they are not uploaded as user
history or shared across browsers. Forecast requests that arrive after kickoff
are rejected. Hypothetical matchup forecasts have no scheduled kickoff and are
not included in the prospective scorecard.

The Touchline forecast journal preserves the saved model probabilities, top
pick, and (for new entries) predicted scoreline. After a confirmed result, it
shows those beside the actual outcome and regulation-time final score. Older
records remain usable; a scoreline that was never saved is shown as unavailable.

The scorecard looks up completed outcomes in the active local history and reports
log loss, Brier score, ranked probability score, classwise calibration error,
and accuracy. For unresolved past forecasts, including those older than 14 days,
it also checks the configured live fixture provider for a confirmed regulation-time
score. Newest dates are checked first, but never-checked dates take priority over
reloading expired cache entries so larger journals can make progress.
If the provider is unavailable, those entries stay pending. If odds were entered, it scores the
model and margin-removed market
probabilities on the same fixtures. Re-forecasting a fixture replaces its
saved entry, so the scorecard uses the latest timestamped forecast before
kickoff. The live sample is exploratory; historical walk-forward results
remain the primary evidence until enough prospective matches have completed.

While the journal is open and the page is visible, it checks results every five
minutes; **Check results** also refreshes them. Unfinished, postponed, cancelled,
and unavailable results remain pending. Scores from extra time or penalties
are not used to settle a regulation-time 1X2 forecast. Confirmed results are
cached locally for subsequent journal visits. This is browser-local storage,
not an account or cross-device sync. An odds comparison added after generating
a forecast retains the original model probabilities and forecast timestamp;
the market snapshot has its own timestamp.

New journal comparisons store the live snapshot's retrieval time, reported quote
range and source identities separately from `market_compared_at`, the time the
comparison was attached. Manual comparisons carry no invented provider times.
The journal CSV includes those fields plus the model's history cutoff. Old
`market_fetched_at` values represented comparison time; exports retain them only
under **Legacy comparison timestamp**, without inventing historical quote times.
These additions do not make the editable browser-local journal an immutable
research log or add a dataset/model hash to older records.

The built dashboard still supports SPA navigation. Missing assets and unknown
API paths return JSON HTTP 404 instead of HTML; a missing dashboard index returns
HTTP 503. API-Football malformed JSON/shapes are surfaced as controlled provider
errors so fallback/error UI can work. Non-finite historical or live market prices
are excluded rather than creating invalid probability comparisons.

Journal backfills are bounded to eight uncached league/date loads per API request
and eight actual Goal API HTTP attempts, including league catalogue resolution,
pagination and failed attempts. A shared allowance additionally caps journal checks
at 100 Goal API attempts per UTC day **per running API process**. These limits do
not meter fixture discovery, badges, the results-sync command or other clients;
they are not an account-wide guarantee against the provider's 1,000/day limit.
Restarting the backend resets this in-memory allowance and cache.

Fixture discovery and journal checks share the same bounded cache and concurrent
loads: past dates older than 14 days are cached for 24 hours, recent dates for five
minutes, future dates for ten minutes, and provider errors for five minutes. Empty
responses are cached too. Local-history and cached lookups cost no provider calls.
Budget-exhausted entries display **Queued for a later check**; provider failures
display **Result provider unavailable**. Larger journals can need several checks,
and a depleted daily allowance resumes after UTC midnight. Saved confirmed results
and original forecasts survive pending, deferred and unavailable responses.

## Freshness guardrail

The response always reports `history_through` and `history_age_days`. The
service refuses dates before the local history's latest recorded match. If a
future kickoff falls on that latest date, a cached earlier-day engine excludes
all results from the target day from features, model fitting and outcome priors.
This lets later same-day fixtures work without using earlier same-day results
whose availability cannot be reconstructed from date-only history. Past kickoffs
remain rejected. Fixture discovery requires a live-provider key, while a
prediction only needs the local historical dataset. The predictor resolves
registered provider labels and club aliases. A registered club with no results
gets a 1400 Elo starting prior, and its probabilities are shrunk halfway toward
the league's training-period outcome rates; the `model_policy` response marks
this with `_promoted_prior`. Unregistered names remain rejected. Results can be
refreshed weekly from OpenFootball; explicit mapping through provider team IDs
remains future hardening work.

When public-source cutoffs lag, use the [local completed-results importer](results-sync.md).
It saves validated Goal API results separately from the Git-tracked bundle.
Restart the backend to load the local snapshot, and use `--check-data` to verify
the actual history dates. Importing fixtures alone does not refresh the model.

The live calibration gap is a five-bin, classwise expected calibration error over
home-win, draw, and away-win probabilities; lower is better. It is descriptive
only, and can move substantially with a small prospective sample.

## Forecast context

`POST /predict` also returns a `context` object with both teams' Elo ratings,
last-five (or fewer, after a long gap) points and goal rates, and home/away
venue points per match. The dashboard shows this snapshot alongside the
probabilities. These values describe the pre-match inputs; they are not an
exact causal decomposition of the predicted probability. The Premier League
policy combines Elo with recent-form and goal-rate features. The current Greek
policy uses Elo only; its recent-form and venue figures are contextual. Home
advantage is included in the Elo comparison. If three odds are entered, they
are converted to margin-removed market probabilities and shown beside the
unchanged model forecast. Injuries, lineups, weather, and odds are not features
in the current model.

The response's `components` object makes the model calculation auditable. For
Premier League forecasts it returns the Elo and goal-model outcome distributions,
the expected-goal rates, their 25%/75% weights, and the combined model
probabilities. For Greece it returns the Elo distribution used by the current
policy. If a club has no recorded results, it also returns the pre-adjustment
core probabilities, league prior, and 50%/50% mixture weight. These components
show how the model assembled its output; they are not causal effects of
individual features.

## Team-name coverage

`team_names.py` includes every club label in the bundled history and aliases
for promoted clubs. It handles common English abbreviations (Bournemouth,
Brighton, Man Utd, Tottenham, Wolves), Greek transliterations (AEK Athens,
Olympiacos, PAOK, OFI, Kifisia), Greek-script aliases, capitalization, accents,
punctuation, and club suffixes. Resolution is scoped to the selected league and
prefers the recent historical label when a club also has an older label.

Iraklis and Kalamata now have recorded 2026-27 results. If another registered
promoted club appears before its first local result, the engine uses the cautious
prior described above. Unknown or ambiguous names are not guessed. The alias
registry includes historical clubs and common short labels for the five new
leagues. Tests cover league-scoped resolution and the fixture-selection-to-
prediction API flow. Live provider rosters still depend on the configured
provider.

The parser now handles OpenFootball's `[awarded]` suffix and canonicalizes team
labels before validation. The bundled results no longer contain the two phantom
Greek club names caused by that parsing issue. See [data-source coverage](data-sources.md)
for current-season completeness and known Greek season gaps.
