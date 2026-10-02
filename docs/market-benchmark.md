# Closing-odds benchmark

The benchmark compares the existing walk-forward forecasts against independent
1X2 closing odds. Odds are a reference line only: this workflow does not feed
them into model training or change the deployed prediction policy.

## Data source and handling

The current candidate source is [Footiqo's historical football database](https://footiqo.com/database/).
Its league pages provide CSV/Excel exports, identify historical 1X2 prices as
closing odds, and describe the data as suitable for independent analysis,
modelling, and backtesting. The site says these odds are sourced from 1xBet.
Coverage varies by competition, match, and season, so the report includes
matched-fixture coverage.

Export the 1X2 odds view for the Premier League and Super League Greece, then
combine the rows in a local CSV. The CSV is not bundled or uploaded by this
project. Keep the source attribution with any published findings:
“Footiqo Football Data — https://footiqo.com/football-data/”.
Review the provider's current terms before reusing data beyond personal
research; the provider's terms prohibit copying or redistributing its content
without permission.

The CLI accepts either the canonical columns below or a Footiqo export with
\`matchDate,Country,League,homeTeam,awayTeam,H,D,A\`. The loader maps only the two
supported competitions, normalizes known team aliases, and ignores other
competitions in a combined export.

| Canonical column | Meaning |
| --- | --- |
| \`competition\` | \`premier_league\` or \`super_league_greece\` |
| \`match_date\` | Match date |
| \`home_team\` | Home club |
| \`away_team\` | Away club |
| \`odds_home\` | Decimal home-win price |
| \`odds_draw\` | Decimal draw price |
| \`odds_away\` | Decimal away-win price |

The source odds' overround is removed with the multiplicative method:
\`p_i = (1 / odds_i) / sum(1 / odds)\`. This creates a fair-probability vector
that sums to one. Rows without three valid prices are excluded. Duplicate
date/team fixtures after alias normalization fail fast rather than being
silently double-counted.

## Evaluation rules

- Every model is refit separately for each complete test season using only
  earlier matches.
- Market and model scores use exactly the fixtures that have usable odds.
- Scores include log loss, Brier score, ranked probability score, and accuracy.
- The report gives odds coverage versus all otherwise-eligible test matches.
- Log-loss differences are paired by season; uncertainty resamples whole test
  seasons. With only a few seasons, intervals are necessarily coarse.
- Dates are matched at calendar-day precision because the match history stores
  dates, not kickoff timestamps. A small number of time-zone/date discrepancies
  can reduce measured coverage.
- A single bookmaker is a weaker reference than a multi-bookmaker consensus.
  This benchmark should be described as 1xBet closing odds, not a market-wide
  consensus.

## Run it

Build the historical features as in the model-comparison guide, then run:

    uv run python -m football_predictor.model_cli \
      --input /tmp/historical_match_features.csv \
      --walk-forward \
      --market-odds /path/to/local_closing_odds.csv

The JSON output is aggregate scores and uncertainty only; the odds rows and
source file stay local.
