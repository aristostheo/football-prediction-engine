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
