# European Football Prediction Engine

A leakage-safe, probabilistic football match prediction system for seven European leagues: the Premier League, Super League Greece, La Liga, Bundesliga, Serie A, Ligue 1, and Primeira Liga.

The project will estimate pre-match probabilities for home win, draw, and away win. It will evaluate models chronologically with log loss, Brier score, accuracy, and calibration — not just winner-picking accuracy.

## Scope for V1

- Historical results from all seven supported competitions
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

The historical dataset uses CC0-licensed OpenFootball repositories:

- [england](https://github.com/openfootball/england) for Premier League results
- [europe](https://github.com/openfootball/europe) for Greece, France, and Portugal
- [espana](https://github.com/openfootball/espana) for Spain
- [deutschland](https://github.com/openfootball/deutschland) for Germany
- [italy](https://github.com/openfootball/italy) for Italy

The bundled snapshot contains 24,950 results across the seven leagues. The
five newly added leagues cover 2018-19 through 2025-26, plus partial 2026-27
results. France's 2019-20 season ended early and is kept incomplete. Greek
coverage gaps remain explicit. See [data coverage](docs/data-sources.md) for
season-by-season counts and limitations.

## Repository layout

```text
src/football_predictor/  # domain models, source adapters, validation, later features/models
tests/                   # deterministic unit tests
web/                     # React + TypeScript prediction dashboard
data/raw/                # ignored raw source downloads
data/processed/          # ignored working datasets
data/model/              # compressed canonical inference input
docs/                    # methodology and source decisions
```

## Local setup

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

GitHub Actions runs backend tests/lint and frontend tests/lint/production build
on every push and on pull requests to `main`. It also runs desktop/mobile Chromium and
WebKit browser flows against mocked providers. These checks do not consume your
Goal API or Odds API allowance. See [browser checks](docs/browser-tests.md) for
local setup, coverage and device-testing limits.

The proposed match Betting tab is being developed in checkpoints. The first
checkpoint adds offline goal-market calculations and a 10,984-match chronological
benchmark; it does not change production forecasts or the UI. Read the
[betting-market findings and next steps](docs/betting-markets.md), including
markets that still need validation. The [historical date correction](docs/historical-date-correction.md)
documents corrected July/August 2020 chronology, the repeated benchmark and an
offline migration that preserves newer results in local synced snapshots.

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

## Run the prediction API

```bash
GOAL_API_KEY=your_key \
uv run uvicorn football_predictor.api:app --reload
```

See [live fixture setup](docs/live-fixtures.md) for endpoints, provider setup,
and the data-freshness policy. GitHub Actions checks for new results weekly
and commits them only when match data changes. Locally, pull updates and restart
your API to load the new snapshot. Run
`uv run python -m football_predictor --check-data` to see the actual result dates
without making API requests, or `uv run python -m football_predictor --refresh`
to download and validate the configured public results sources. A successful
refresh does not guarantee that those sources contain newer results.

To import more recent completed matches with your Goal API key, see
[local results sync](docs/results-sync.md). The API automatically loads the
validated local snapshot after restarting; the tracked bundle is preserved.

## Run the dashboard

For development, run the API command above and start Vite separately:

```bash
cd web
npm install
npm run dev
```

The production Docker image builds the dashboard and serves it from FastAPI as
one deployable service. See [deployment setup](docs/deployment.md).

Touchline is the main dashboard at `/`. It uses the real fixture catalogue,
production predictor, optional live odds, and the browser's existing favourites
and forecast journal. For a single local server, run `npm run build` in `web`,
then `uv run uvicorn football_predictor.api:app --reload` from the repository
root and open `http://localhost:8000`.

The previous dashboard remains at `/classic`. The isolated design demo remains
at `/updated-mockup` and makes no backend/API calls. See the
[live Touchline integration](docs/design/touchline-live.md) and
[concept preview gallery](docs/design/touchline.md).

## Project status

The foundation, canonical match schema, source selection, leakage-safe feature
engine, Elo probability baseline, calibrated logistic comparison, Poisson goal
model, validation-selected ensemble, FastAPI service, optional live-fixture
adapter, and React dashboard are in place. The current production policy uses
the ensemble for the Premier League and Elo for Super League Greece. The Greek
policy was chosen after inspecting the final holdout, so that holdout is
exploratory and is not an independent estimate of future performance. The
project now includes an expanding-season walk-forward evaluation with a
climatology baseline and season-block uncertainty. The bundled history is
current through September 20, 2026 across the seven leagues. The new leagues use an Elo baseline until their own production policy
is validated; their walk-forward metrics are exploratory and must not be read
as proof that they outperform other leagues or models. See [data coverage](docs/data-sources.md)
for season counts and limitations.

A closing-odds benchmark and optional live market comparison are available. The
benchmark matches odds to walk-forward fixtures, removes the bookmaker margin,
and reports coverage and season-block intervals. The dashboard can load a live
bookmaker consensus for an upcoming fixture when `THE_ODDS_API_KEY` is
configured, or accept all three 1X2 prices manually. It displays
model probabilities as the forecast and margin-removed market probabilities
separately for comparison. Historical sequential tests chose 100% market weight
on every eligible fold, so the current evidence does not support a
model/market blend. Live quotes do not alter model probabilities. See
[market benchmark setup](docs/market-benchmark.md) and
[live fixture setup](docs/live-fixtures.md).

The dashboard also keeps a prospective 2026-27 scorecard in the current
browser. The journal shows the saved model probabilities and predicted score
beside the confirmed result and regulation-time score. It checks unresolved results
with the configured fixture provider and also uses the refreshed history. It
compares model versus market probabilities when both were recorded; see
[live fixture setup](docs/live-fixtures.md) for its limits.
