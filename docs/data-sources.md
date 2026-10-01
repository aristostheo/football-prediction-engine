# Data sources and ingestion policy

## Initial historical-results source

The first production ingest uses public CC0 OpenFootball repositories with the
same concise, text-based results format:

- [OpenFootball England](https://github.com/openfootball/eng-england) for the
  Premier League, with completed seasons from 2000-01 to 2024-25 in V1.
- [OpenFootball Europe](https://github.com/openfootball/europe) for Super
  League Greece. V1 includes its available completed files: 2018-19, 2019-20,
  2020-21, 2023-24, and 2024-25.

Raw data remains outside this repository; each generated canonical row retains
the exact file URL and retrieval timestamp. The Greek coverage has explicit
gaps, which are preserved rather than filled or inferred.

The adapter is intentionally source-neutral at its output boundary. It converts
an external file into `HistoricalMatch` records, then the canonical dataset
builder applies cross-source validation.

## Live-fixture source

The optional API service reads upcoming fixtures from API-Football. It is used
only to discover fixtures: the local, versioned historical dataset remains the
source of model inputs and always exposes its freshness in each prediction.
See [live-fixtures.md](live-fixtures.md) for setup and endpoint details.

## Rebuilding the initial dataset

Clone the two source repositories outside this repository, then run:

```bash
uv run python -m football_predictor \
  --england-root /path/to/eng-england \
  --europe-root /path/to/europe
```

This writes an ignored CSV and JSON manifest under `data/processed/`. The
manifest fixes the source-file set, records the retrieval time, and gives a
per-competition match count.

## Competition-stage policy for V1

The V1 dataset includes regular-season fixtures only. Super League Greece
championship, European-playoff, and relegation stages are parsed but excluded.
Those stages change the fixture population and should be added only with an
explicit modelling policy, rather than being mixed into league form by default.
