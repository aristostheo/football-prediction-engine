# European Football Prediction Engine

A leakage-safe, probabilistic football match prediction system for the **Premier League** and **Super League Greece**.

The project will estimate pre-match probabilities for home win, draw, and away win. It will evaluate models chronologically with log loss, Brier score, accuracy, and calibration — not just winner-picking accuracy.

## Scope for V1

- Historical results from both target competitions
- A normalized match dataset with explicit data provenance
- Pre-match features only: form, goal rates, home/away performance, rest, and Elo
- Baseline probabilistic models followed by model comparison
- Chronological backtesting and a small prediction API/UI after the model is validated

## Non-negotiable modelling rules

1. **No future leakage.** A row for a match may use only information available before that match kicked off.
2. **Chronological evaluation.** We never randomly shuffle matches across train and test data.
3. **Probabilities over assertions.** The core output is `P(home win)`, `P(draw)`, and `P(away win)`.
4. **Source provenance.** Every imported file records its source, retrieval date, competition, and season.
5. **Separate competition context.** League-specific history is not blended accidentally; cross-league modelling will be an explicit later decision.

## Initial data policy

The first ingestion path will target open/public-domain historical results where possible. We will not bundle third-party raw data in this repository. The ingestion layer will be source-adapter based, so a source can be replaced without rewriting the model pipeline.

The initial historical dataset uses CC0-licensed OpenFootball repositories:

- [eng-england](https://github.com/openfootball/eng-england) for Premier League results
- [europe](https://github.com/openfootball/europe) for Super League Greece results

The first reproducible build covers Premier League completed seasons from
2000-01 to 2024-25 and the available Greek completed seasons. It keeps Greek
coverage gaps explicit and excludes post-regular-season stages.

## Repository layout

```text
src/football_predictor/  # domain models, source adapters, validation, later features/models
tests/                   # deterministic unit tests
data/raw/                # ignored raw source downloads
data/processed/          # ignored generated datasets
docs/                    # methodology and source decisions
```

## Local setup

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

## Build model-ready features

After generating `historical_matches.csv`, build leakage-safe feature rows:

```bash
uv run python -m football_predictor.feature_cli \
  --input data/processed/historical_matches.csv
```

Evaluate the online Elo baseline without random shuffling:

```bash
uv run python -m football_predictor.baseline_cli \
  --input data/processed/historical_match_features.csv
```

Compare it with a time-calibrated logistic model, still using each league's
chronological holdout:

```bash
uv run python -m football_predictor.model_cli \
  --input data/processed/historical_match_features.csv
```

## Milestone 1 status

The foundation, canonical match schema, source selection, leakage-safe feature
engine, Elo probability baseline, calibrated logistic comparison, Poisson goal
model, and validation-selected ensemble are in place. The current policy uses
the ensemble for the Premier League and Elo for Super League Greece, selected
without tuning on the final holdout. Next: expose these trained prediction paths
through a FastAPI service and integrate a reviewed current-fixture source.
