# Data sources and ingestion policy

## Historical results source

The bundled snapshot uses public OpenFootball repositories with a concise,
text-based results format:

- [OpenFootball England](https://github.com/openfootball/england) for the
  Premier League, with completed seasons from 2000-01 to 2025-26 and results
  from the in-progress 2026-27 season.
- [OpenFootball Europe](https://github.com/openfootball/europe) for Super
  League Greece, Ligue 1, and Primeira Liga.
- [OpenFootball Espana](https://github.com/openfootball/espana) for La Liga.
- [OpenFootball Deutschland](https://github.com/openfootball/deutschland) for
  Bundesliga.
- [OpenFootball Italy](https://github.com/openfootball/italy) for Serie A.

The five newly added leagues have 13,955 parsed results: La Liga 3,109,
Bundesliga 2,484, Serie A 3,090, Ligue 1 2,762, and Primeira Liga 2,510. Each
has eight complete seasons from 2018-19 through 2025-26. Partial 2026-27
results are included in those totals. Ligue 1's 2019-20 season stopped early
(279 matches), so it is deliberately excluded from complete-season tests.
Counts and per-season provenance are in
`data/model/historical_matches.manifest.json`.

Each canonical row retains its exact source URL and retrieval timestamp. The
October 10, 2026 snapshot contains partial 2026-27 results in all seven
leagues. The Greek 2025-26 file contains 62 scored regular-season matches and
remains incomplete in the upstream data. Greek coverage also has explicit gaps
for 2021-22 and 2022-23. Missing results are not filled or inferred. The five
new league policies use pure Elo for 1X2 probabilities; they have not been
independently tuned or selected for production. Their scoreline estimates are
provided by the existing separate Poisson goal model.

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

The optional API service prefers Goal API for upcoming fixtures in all seven
supported leagues, with API-Football available as a fallback. Providers are
used only to discover fixtures: the versioned historical dataset remains the
source of model inputs and each prediction exposes its history date. The optional
[local results sync](results-sync.md) imports validated completed Goal API results
into an ignored local snapshot; it becomes the runtime input after restarting.
See
[live-fixtures.md](live-fixtures.md) for setup and endpoint details.

## Rebuilding the dataset

From the repository root, refresh the compressed model history and its
provenance manifest directly from the public source files:

```bash
uv run python -m football_predictor --refresh
```

The command chooses the season from the current date, validates every completed
Premier League season and all match rows, records a SHA-256 checksum for each
source file and the generated dataset, then replaces the local bundle. It
refuses to update if any previously recorded fixture disappears; review that
upstream change before retrying with `--allow-removed-matches`. Download or
validation failures leave the current dataset intact. GitHub Actions runs this
refresh weekly on Tuesday and can also be started from the Actions tab. It
commits the dataset and manifest only when match results change. The Render
service is configured to deploy on a commit, so successful data updates roll
out with the application.

The original local-repository build remains available:

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
