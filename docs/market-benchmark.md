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

Export the 1X2 odds view for the Premier League and Super League Greece as
separate CSV files. Pass both paths to the CLI; no manual merge is needed. The
CSV files are not bundled or uploaded by this project. Keep the source
attribution with any published findings:
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
      --market-odds /path/to/premier_league_odds.csv /path/to/greece_odds.csv

The JSON output is aggregate scores and uncertainty only; the odds rows and
source file stay local.

To evaluate a market-assisted policy, add `--market-assist`:

    uv run python -m football_predictor.model_cli \
      --input /tmp/historical_match_features.csv \
      --walk-forward \
      --market-odds /path/to/premier_league_odds.csv /path/to/greece_odds.csv \
      --market-assist

For each test season, this selects a single market weight using only earlier
out-of-fold forecasts with usable odds, then scores that fixed weight on the
test season. At least 400 earlier matched forecasts from two season blocks are
required. The live prediction form accepts optional decimal home, draw, and
away prices; all three must be supplied together. It removes the overround
and returns market-implied probabilities. The no-odds path continues to use
the model.

## Benchmark snapshot (2026-10-02)

The attached Footiqo exports were matched against the same complete-season
walk-forward fixtures used in the model comparison. The three quoted prices
were de-vigged row by row. Premier League coverage was 1,900/1,900 matches;
Greek coverage was 725/728 (99.6%). The three unmatched Greek matches are
excluded because the export has no usable matching prices for them.

| Competition | Forecast | Matches | Log loss | Brier | RPS | Accuracy |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Premier League | Footiqo / 1xBet closing odds | 1,900 | 0.9570 | 0.5679 | 0.1940 | 55.37% |
| Premier League | Best tested model (Poisson) | 1,900 | 0.9738 | 0.5799 | 0.1996 | 53.74% |
| Greece Super League | Footiqo / 1xBet closing odds | 725 | 0.9163 | 0.5405 | 0.1779 | 55.17% |
| Greece Super League | Best tested model (Poisson) | 725 | 0.9746 | 0.5805 | 0.1951 | 51.86% |

Paired differences below are model log loss minus closing-odds log loss. Positive
values favor the closing odds. Intervals resample whole seasons, so only five
Premier League and four Greek season blocks contribute.

| Competition | Model | Mean difference | 95% season-block interval |
| --- | --- | ---: | ---: |
| Premier League | Elo | 0.0217 | [0.0138, 0.0306] |
| Premier League | Ensemble | 0.0171 | [0.0104, 0.0227] |
| Premier League | Logistic | 0.0196 | [0.0142, 0.0266] |
| Premier League | Poisson | 0.0169 | [0.0116, 0.0219] |
| Greece Super League | Elo | 0.0687 | [0.0409, 0.0965] |
| Greece Super League | Ensemble | 0.0624 | [0.0462, 0.0880] |
| Greece Super League | Logistic | 0.0637 | [0.0417, 0.0834] |
| Greece Super League | Poisson | 0.0584 | [0.0462, 0.0758] |

On this benchmark, closing odds scored better than all tested model candidates
in both leagues. These results are now an exploratory baseline: choices made
after inspecting them must be assessed on future data before being described
as an independent improvement. In particular, do not tune against these
test-season odds and then report the same seasons as untouched evaluation.
This is a single-provider benchmark, not a multi-bookmaker consensus, and the
small number of season blocks makes the uncertainty intervals coarse.

## Sequential market-assist check (2026-10-02)

The market weight was selected by log loss using only earlier out-of-fold
forecasts, requiring at least 400 prior matched fixtures across two season
blocks. The most recent four eligible Premier League seasons and two eligible
Greek seasons were scored. Every fold selected a market weight of 1.00, so the
market-assisted score is identical to the closing-market score. This is
evidence to expose market-implied probabilities as an optional forecast when
users have odds; it is not evidence that a model/market blend improves on the
odds alone.

| Competition | Test seasons | Matches | Model log loss | Closing odds log loss | Selected market weight |
| --- | --- | ---: | ---: | ---: | ---: |
| Premier League | 2022-23 to 2025-26 | 1,520 | 0.9781 | 0.9616 | 1.00 on all 4 folds |
| Greece Super League | 2023-24 to 2024-25 | 361 | 1.0001 | 0.9252 | 1.00 on both folds |

For this sequential evaluation, the deployed-style comparison is Elo/Poisson
blend for the Premier League and Elo for Greece. The test fixture sets are
limited to seasons with enough earlier data to choose a market weight; they
therefore differ from the broader benchmark table above. Odds remain local,
and these historical outcomes were used for development decisions, so they
are not an untouched future test.
