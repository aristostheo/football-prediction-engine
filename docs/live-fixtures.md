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

## Freshness guardrail

The response always reports `history_through` and `history_age_days`. The
service deliberately refuses to back-predict a date at or before the local
history's latest completed match, preventing future information from entering a
historical prediction. Fixture discovery requires a live-provider key, while a
prediction only needs the local historical dataset. The predictor resolves
common provider labels and club suffixes against locally recorded team names,
while unknown or ambiguous teams remain rejected. Current-result synchronization
and explicit mapping through provider team IDs remain future hardening steps.

## Team-name coverage

`team_names.py` registers all 46 English clubs and 20 Greek clubs represented in
the bundled history. It handles common English abbreviations (Bournemouth,
Brighton, Man Utd, Tottenham, Wolves), Greek transliterations (AEK Athens,
Olympiacos, PAOK, OFI, Kifisia), Greek-script aliases, capitalization, accents,
punctuation, and club suffixes. Resolution is scoped to the selected league and
prefers the recent historical label when a club also has an older label.

Iraklis and Kalamata have recognized names but no results in the bundled dataset;
their predictions return a clear missing-history error. Unknown or ambiguous
names are not guessed. The audit tests cover all real clubs in the local dataset
and the fixture-selection-to-prediction API flow for both leagues. Live API roster
verification requires a configured provider key; no key was available in the
development environment during this audit.

Two historical awarded-match rows contain malformed parser labels (`[awarded]`
and combined fixture text). These are not registered as club aliases. Historical
result cleanup and refreshing the dataset remain separate work.
