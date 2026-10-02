# Data sources and ingestion policy

## Historical results source

The bundled snapshot uses public OpenFootball repositories with a concise,
text-based results format:

- [OpenFootball England](https://github.com/openfootball/england) for the
  Premier League, with completed seasons from 2000-01 to 2025-26 and results
  from the in-progress 2026-27 season.
- [OpenFootball Europe](https://github.com/openfootball/europe) for Super
  League Greece. It includes available completed files for 2018-19, 2019-20,
  2020-21, 2023-24, and 2024-25, plus partial results from 2025-26 and 2026-27.

Each canonical row retains its exact source URL and retrieval timestamp. The
Greek 2025-26 file currently contains 62 scored regular-season matches, and the
2026-27 file contains 35; neither is treated as a completed season. Coverage
also has explicit gaps for 2021-22 and 2022-23. The missing results are not
filled or inferred.

The adapter converts each external file into `HistoricalMatch` records, then
applies duplicate, team-name, score, and completed-season schedule checks.

## Closing-odds benchmark source

The optional benchmark accepts a local export from
[Footiqo's historical football database](https://footiqo.com/database/).
Its league pages offer historical 1X2 closing odds for the Premier League and
Super League Greece; the site identifies 1xBet as the odds source and describes
the database as available for independent modelling and backtesting. The
benchmark removes the quoted margin and compares the odds against models on
the same walk-forward fixtures.

The raw odds export is not bundled or uploaded. Cite “Footiqo Football Data”
and link to https://footiqo.com/football-data/ when presenting results. The
provider's terms prohibit copying or redistributing its content without
permission. Check [market-benchmark.md](market-benchmark.md) for the expected
CSV format, method, run command, and limits.

## Live fixtures

The optional API service prefers Goal API for upcoming fixtures in both
supported leagues, with API-Football available as a fallback. Providers are
used only to discover fixtures: the versioned historical dataset remains the
source of model inputs and each prediction exposes its history date. See
[live-fixtures.md](live-fixtures.md) for setup and endpoint details.

## Rebuilding the dataset

Clone `openfootball/england` and `openfootball/europe` outside this repository,
then run:

```bash
uv run python -m football_predictor \
  --england-root /path/to/england \
  --europe-root /path/to/europe
```

This writes an ignored CSV and JSON manifest under `data/processed/`. The
manifest records retrieval time, match counts, source URLs, and whether each
season passed the complete-season schedule check.

## Competition-stage policy

The dataset includes regular-season fixtures only. Greek championship,
European-playoff, and relegation stages are excluded because they change the
fixture population and need a separate modelling policy.
