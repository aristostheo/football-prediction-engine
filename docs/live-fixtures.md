Warning: truncated output (original token count: 2529)
Total output lines: 170

# Live fixtures and API service

The service exposes an optional live-fixture adapter and a prediction endpoint:

```bash
GOAL_API_KEY=your_goal_key \
THE_ODDS_API_KEY=your_odds_api_key \
uv run uvicorn football_predictor.api:app --reload
```

- `GET /health` confirms that the service is running.
- `GET /fixtures?competition=premier_league&date=YYYY-MM-DD` reads scheduled
  fixtures from Goal API when `GOAL_API_KEY` is configured.
- `POST /predict` accepts canonical names or registered club aliases and a fixture date after
  the local historical dataset's final result.
- `GET /odds` retrieves upcoming 1X2 market odds for a scheduled fixture when
  `THE_ODDS_API_KEY` is configured. Results are a bookmaker consensus with each
  book's margin removed and are cached for 10 minutes.

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
fixture discovery. The user's free plan allows 1,000 re…1529 tokens truncated…nverted to margin-removed market probabilities and shown beside the
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
