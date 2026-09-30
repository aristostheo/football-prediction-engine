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

Current candidates:

- [openfootball](https://github.com/openfootball) for open historical schedules/results, including Greece.
- A separately reviewed provider for current fixtures and richer Premier League statistics later.

We will document the final source and licence before downloading production data.

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

## Milestone 1 status

The foundation, canonical match schema, normalization rules, and validation suite are in place. The first OpenFootball source adapter now parses regular-season historical results without mixing in Greek play-off stages. Next: select the final Premier League source and produce the first two-league historical dataset.
