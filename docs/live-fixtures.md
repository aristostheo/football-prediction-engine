# Live fixtures and API service

The service exposes an optional live-fixture adapter and a prediction endpoint:

```bash
GOAL_API_KEY=your_key \
uv run uvicorn football_predictor.api:app --reload
```

- `GET /health` confirms that the service is running.
- `GET /fixtures?competition=premier_league&date=YYYY-MM-DD` reads scheduled
  fixtures from Goal API when `GOAL_API_KEY` is configured.
- `POST /predict` accepts canonical names or registered club aliases and a fixture date after
  the local historical dataset's final result.

## Provider decision

V1 prefers the optional [Goal API](https://goal-api.com/) adapter for current
fixture discovery. Its free plan covers both supported leagues and allows 1,000
requests per day. The date-fixture endpoint's `leagueId` filter uses Goal API's
internal league `id` from `/leagues`, not the provider's numeric `apiId` (152 for
the Premier League and 178 for Super League Greece).

[API-Football](https://www.api-football.com/) remains an optional fallback when
`API_FOOTBALL_KEY` is also configured. Provider order is:

1. Goal API when `GOAL_API_KEY` is present.
2. API-Football when `API_FOOTBALL_KEY` is present and Goal API fails, or when
   it is the only configured provider.

Keys are read only by the backend from environment variables and must never be
committed or exposed to the browser. Manual prediction remains available with
no provider key.

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
are rejected. Manually entered date-only predictions remain available but are
not included in the prospective scorecard because their timing cannot be
verified.

The scorecard looks up completed outcomes in the bundled dataset after a
refresh and reports log loss, Brier score, ranked probability score, classwise
calibration error, and accuracy. If odds were entered, it scores the model and margin-removed market
probabilities on the same fixtures. Re-forecasting a fixture replaces its
saved entry, so the scorecard uses the latest timestamped forecast before
kickoff. The live sample is exploratory; historical walk-forward results
remain the primary evidence until enough prospective matches have completed.

## Freshness guardrail

The response always reports `history_through` and `history_age_days`. The
service deliberately refuses to back-predict a date at or before the local
history's latest recorded match, preventing future information from entering a
historical prediction. Fixture discovery requires a live-provider key, while a
prediction only needs the local historical dataset. The predictor resolves
registered provider labels and club aliases. A registered club with no results
gets a 1400 Elo starting prior, and its probabilities are shrunk halfway toward
the league's training-period outcome rates; the `model_policy` response marks
this with `_promoted_prior`. Unregistered names remain rejected. Results can be
refreshed weekly from OpenFootball; explicit mapping through provider team IDs
remains future hardening work.

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
advantage is included in the Elo comparison. If three odds are entered, the
headline probabilities use margin-removed market prices, and the model-only
probabilities remain visible separately. Injuries, lineups, weather, and odds
are not features in the current model.

## Team-name coverage

`team_names.py` includes every club label in the bundled history and aliases
for promoted clubs. It handles common English abbreviations (Bournemouth,
Brighton, Man Utd, Tottenham, Wolves), Greek transliterations (AEK Athens,
Olympiacos, PAOK, OFI, Kifisia), Greek-script aliases, capitalization, accents,
punctuation, and club suffixes. Resolution is scoped to the selected league and
prefers the recent historical label when a club also has an older label.

Iraklis and Kalamata now have recorded 2026-27 results. If another registered
promoted club appears before its first local result, the engine uses the cautious
prior described above. Unknown or ambiguous names are not guessed. Tests cover
both leagues' alias resolution and the fixture-selection-to-prediction API flow.
Live provider rosters still depend on the configured provider.

The parser now handles OpenFootball's `[awarded]` suffix and canonicalizes team
labels before validation. The bundled results no longer contain the two phantom
Greek club names caused by that parsing issue. See [data-source coverage](data-sources.md)
for current-season completeness and known Greek season gaps.
