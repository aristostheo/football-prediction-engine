# Betting markets — checkpoint 1

Measured on 2026-10-18. Offline research and arithmetic only: no production predictor, API, frontend, historical bundle or provider integration was changed. The Betting tab is checkpoint 2.

## Decision

Keep the production 1X2 policy and current scorelines unchanged. The new settlement/calculation layer is ready for integration, but the goal-derived markets remain experimental. The benchmark does not justify presenting every new market as validated or promoting result-aligned scorelines universally.

Team-goal estimates show the clearest improvement over league base rates. Match totals and BTTS show mixed results; Greek total-goal/BTTS estimates underperform base rates on this sample. Making a score matrix agree with headline 1X2 probabilities solves coherence mathematically, but does not consistently improve goal-market or scoreline accuracy. In Portugal it worsens scoreline log likelihood by about 0.0052. Do not select a different matrix separately for each line based on these test results.

Resolve the 2019–20 date inference issue described below before a production goal-market decision. Repeat the same locked evaluation after that data correction, then use earlier folds for any calibration and reserve a later period for confirmation.

## Implemented

- `src/football_predictor/betting.py`: regulation-time result, total goals, team goals, BTTS, correct score, double chance and draw-no-bet; full win/loss/refund probabilities; fair decimal odds and expected net return; complete two-way margin removal.
- `src/football_predictor/betting_benchmark.py`: reproducible expanding-season evaluation, market calibration buckets, binary scores, scoreline metrics, production consistency audit and paired season-block intervals.
- Independent Poisson grid reproduces existing rate capping at 8 and normalized 0–12 goal support. Captured probability mass and rate-capping status are exposed, not hidden. An outside-grid correct-score request is rejected.
- Experimental result alignment rescales each home-win/draw/away-win part of the score matrix to the existing headline probabilities, preserving score ratios within each part. It is a coherence transformation, not a fitted calibration or new attack/defence model.
- No new football features, H2H effects, market blending, betting recommendations or wagering functionality were added.

## Settlement and comparison contract

All selections refer to 90 minutes plus stoppage time, excluding extra time and penalties. The caller must establish a completed regulation-time result; postponed, abandoned and unresolved fixtures cannot be settled just because goal fields exist.

| Market | Contract |
|---|---|
| Total/team goals | Half lines have no refund; whole lines refund on equality. Quarter-goal Asian lines are explicitly rejected for now. |
| BTTS | Both teams score at least once; Yes/No are complementary. |
| Correct score | Probability comes from the full score matrix, never renormalized over the top three scores. |
| Double chance | Sum appropriate 1X2 outcomes. The three double-chance options overlap and must not be normalized together as a partition. |
| Draw no bet | Draw is a refund; home and away prices refer to probabilities conditional on no draw. |

Fair decimal odds are `(P(win) + P(loss)) / P(win)`, returning no price when there is no win support. This equals `1 / P(win)` only when refunds are impossible. Expected net return per unit stake is `P(win) * (offered_odds - 1) - P(loss)`; refunds contribute zero net return.

Keep actual bookmaker prices, margin-free market probabilities and model fair prices separate. Normalize an Over/Under or Yes/No pair only for the identical bookmaker, event, period and line. Incomplete correct-score quotes cannot support full-market margin removal unless all other outcomes are accounted for. A model-minus-market difference is in percentage points; it is not a measured profit expectation. Exact-score probabilities and larger apparent differences need the same validation discipline as 1X2.

## Locked evaluation protocol

- Dataset: `data/model/historical_matches.csv.gz`, 24,950 rows; SHA-256 `ed3b8b61194f5baa2f30da1dbc2142b79a94ed4abcd7e3b2842542164a5ffc82`.
- 33 expanding-season folds, 10,984 distinct test matches. Six leagues use 2021–22 through 2025–26; Greece uses 2020–21, 2023–24 and 2024–25. Partial seasons and interrupted/ineligible seasons are not final test folds.
- Each goal model is fit on strictly earlier dates once per season. The existing alpha grid (0.01, 0.1, 1, 10) is selected within that training data by the existing Poisson fitting recipe. The team-state features still update after earlier match dates during each test season. No model coefficient is fitted to a held-out match.
- This is a season-frozen model replay, not a day-by-day coefficient-refit reproduction of every historical deployment. First-day parity is checked against the actual serving engine for Premier League and Greece. Registered first appearances use the current promoted-team prior.
- Production-recipe baseline: PL 25% Elo / 75% Poisson; the other six leagues use Elo for 1X2. The existing model has no extra calibration transform here.
- Comparators: existing raw Poisson score matrix; result-aligned experimental matrix; train-only Laplace-smoothed binary league climatology. A train-only league-mean Poisson distribution supplies a simple scoreline baseline.
- The fixed market family includes 1X2, match Over 0.5–4.5, BTTS, each team Over 0.5–2.5, double chance and draw-no-bet. Under/No are complements with identical binary log loss and Brier. Correct scores are evaluated jointly by scoreline NLL, rather than choosing a few scores after viewing results.
- Primary market metrics are binary log loss and Brier; ten calibration bins, ECE and accuracy are reported. Refund matches are excluded from conditional binary metrics and counted separately. Their model refund probabilities are retained in the per-match output.
- Scoreline metrics: negative log likelihood, exact-score hit rate and mean absolute goal error averaged across home/away. Mean goal error uses the distribution mean, not the most likely score. All test scorelines were within support; no matches were silently discarded.
- Confidence intervals use 2,000 paired resamples of whole seasons, seed 42. Five season blocks (three in Greece) give limited precision; many correlated markets are examined and intervals are not corrected for multiple comparisons. These previously examined historical seasons are exploratory, not a pristine untouched holdout. Do not infer betting profitability.
- No new calibration, blending weights or per-league candidate selection were fitted in this checkpoint. Historical odds for these additional markets are unavailable locally, so there is no bookmaker benchmark or ROI claim.

## Dataset and date limitation

The audit found **258 rows in the 2019–20 season dated before August 2019**: Premier League 66, La Liga 57, Serie A 88 and Primeira Liga 47. Examples include matches in the July resumption of that season. The source adapter currently infers an omitted year with `month >= 7` belonging to the starting year, which is unsuitable for pandemic seasons continuing in July.

The benchmark retains the exact bundled input for production-input parity and flags this in the JSON. These suspect rows are training-only in this run and cannot expose a 2021+ test outcome to fitting, but their incorrect ordering can corrupt learned historical form/Elo/rest and prior benchmark conclusions. No replacement dates were guessed. A separate parser/source audit and a validated dataset rebuild are required. Greek season gaps, missing playoffs and partial 2025–26 data remain additional limitations.

The existing training-only `TimeSeriesSplit` is row based and can split a date internally. It never accesses an outer test season, but a future tuning upgrade should group internal folds by date. It was preserved here to keep the deployed fitting recipe comparable.

## Test populations

| League | Test matches | Test dates | Test seasons |
|---|---:|---|---|
| Premier League | 1,900 | 2021-08-13 → 2026-05-24 | 2021-22, 2022-23, 2023-24, 2024-25, 2025-26 |
| Greece | 546 | 2020-09-11 → 2025-03-09 | 2020-21, 2023-24, 2024-25 |
| La Liga | 1,900 | 2021-08-13 → 2026-05-24 | 2021-22, 2022-23, 2023-24, 2024-25, 2025-26 |
| Bundesliga | 1,530 | 2021-08-13 → 2026-05-16 | 2021-22, 2022-23, 2023-24, 2024-25, 2025-26 |
| Serie A | 1,900 | 2021-08-21 → 2026-05-24 | 2021-22, 2022-23, 2023-24, 2024-25, 2025-26 |
| Ligue 1 | 1,678 | 2021-08-06 → 2026-05-17 | 2021-22, 2022-23, 2023-24, 2024-25, 2025-26 |
| Primeira Liga | 1,530 | 2021-08-06 → 2026-05-16 | 2021-22, 2022-23, 2023-24, 2024-25, 2025-26 |

## Goal-market log loss

Lower is better. Base = training-only binary league climatology. Raw = existing separate goal distribution. Aligned = that distribution constrained to headline 1X2. Full Brier, accuracy, calibration and interval results for all 20 selections are in the linked JSON.

| League | O2.5 base | O2.5 raw | O2.5 aligned | BTTS base | BTTS raw | BTTS aligned |
|---|---:|---:|---:|---:|---:|---:|
| Premier League | 0.6914 | 0.6840 | 0.6843 | 0.6919 | 0.6901 | 0.6898 |
| Greece | 0.7007 | 0.7128 | 0.7083 | 0.6974 | 0.7022 | 0.7068 |
| La Liga | 0.6922 | 0.6845 | 0.6849 | 0.6928 | 0.6938 | 0.6936 |
| Bundesliga | 0.6691 | 0.6595 | 0.6600 | 0.6729 | 0.6701 | 0.6709 |
| Serie A | 0.6998 | 0.6978 | 0.6957 | 0.6978 | 0.6930 | 0.6945 |
| Ligue 1 | 0.6920 | 0.6854 | 0.6863 | 0.6899 | 0.6892 | 0.6885 |
| Primeira Liga | 0.6959 | 0.6782 | 0.6786 | 0.6942 | 0.6915 | 0.6921 |

| League | Home O1.5 base | Home O1.5 raw | Away O1.5 base | Away O1.5 raw |
|---|---:|---:|---:|---:|
| Premier League | 0.6929 | 0.6436 | 0.6703 | 0.6296 |
| Greece | 0.6813 | 0.6256 | 0.6472 | 0.6277 |
| La Liga | 0.6792 | 0.6383 | 0.6181 | 0.5919 |
| Bundesliga | 0.6936 | 0.6592 | 0.6727 | 0.6438 |
| Serie A | 0.6784 | 0.6408 | 0.6494 | 0.6087 |
| Ligue 1 | 0.6866 | 0.6541 | 0.6544 | 0.6284 |
| Primeira Liga | 0.6798 | 0.6076 | 0.6373 | 0.5831 |

## Scoreline and consistency results

| League | League Poisson NLL | Raw NLL | Aligned NLL | Raw exact hit | Raw goal MAE | Mean maximum 1X2 mismatch |
|---|---:|---:|---:|---:|---:|---:|
| Premier League | 3.1111 | 2.9752 | 2.9754 | 11.3% | 0.928 | 1.05 pp |
| Greece | 2.9453 | 2.8283 | 2.8274 | 12.6% | 0.855 | 6.31 pp |
| La Liga | 2.9115 | 2.8140 | 2.8157 | 14.8% | 0.857 | 2.66 pp |
| Bundesliga | 3.2171 | 3.0925 | 3.0914 | 11.3% | 1.004 | 6.72 pp |
| Serie A | 2.9380 | 2.8255 | 2.8235 | 14.9% | 0.881 | 4.24 pp |
| Ligue 1 | 3.0594 | 2.9632 | 2.9648 | 11.2% | 0.932 | 4.00 pp |
| Primeira Liga | 2.9887 | 2.7998 | 2.8050 | 14.2% | 0.858 | 4.16 pp |

Mismatch is the largest absolute difference among H/D/A for each fixture, averaged across fixtures. Alignment reduces this mismatch to floating-point precision by construction and preserves production 1X2, not by discovering extra predictive signal. No rate cap was triggered in these test matches; the smallest original grid captured mass was 0.999716.

| League | Aligned − raw score NLL | Paired 95% season interval |
|---|---:|---|
| Premier League | +0.00016 | [-0.00100, +0.00181] |
| Greece | -0.00096 | [-0.01631, +0.02181] |
| La Liga | +0.00165 | [-0.00085, +0.00466] |
| Bundesliga | -0.00107 | [-0.00764, +0.00828] |
| Serie A | -0.00206 | [-0.00527, +0.00160] |
| Ligue 1 | +0.00156 | [-0.00265, +0.00752] |
| Primeira Liga | +0.00521 | [+0.00032, +0.01009] |

## Historical examples

Fixed examples: the last chronologically stored test fixture in the listed league. These are historical predictions, not forecasts for upcoming games.

| Match | Actual | Headline H/D/A | Over 2.5 raw / aligned | BTTS raw / aligned |
|---|---|---|---|---|
| 2026-05-24: West Ham United FC – Leeds United FC | 3–0 | 39.4%/26.7%/33.9% | 47.4% / 47.3% | 52.2% / 52.3% |
| 2025-03-09: Panetolikos – Levadiakos | 0–0 | 39.9%/27.2%/33.0% | 38.2% / 38.8% | 44.9% / 44.4% |
| 2026-05-16: SV Werder Bremen – Borussia Dortmund | 0–2 | 22.2%/25.5%/52.3% | 60.6% / 59.8% | 60.9% / 61.5% |

## Exact fold audit

Training windows overlap and expand; do not sum their row counts as distinct matches. Alpha choices are in the JSON. No separate validation-season candidate selection occurred; alpha validation is nested inside each training window.

| League | Season | Train n | Train dates | Test n | Test dates |
|---|---|---:|---|---:|---|
| Bundesliga | 2021-22 | 918 | 2018-08-24 → 2021-05-22 | 306 | 2021-08-13 → 2022-05-14 |
| Bundesliga | 2022-23 | 1,224 | 2018-08-24 → 2022-05-14 | 306 | 2022-08-05 → 2023-05-27 |
| Bundesliga | 2023-24 | 1,530 | 2018-08-24 → 2023-05-27 | 306 | 2023-08-18 → 2024-05-18 |
| Bundesliga | 2024-25 | 1,836 | 2018-08-24 → 2024-05-18 | 306 | 2024-08-23 → 2025-05-17 |
| Bundesliga | 2025-26 | 2,142 | 2018-08-24 → 2025-05-17 | 306 | 2025-08-22 → 2026-05-16 |
| La Liga | 2021-22 | 1,140 | 2018-08-17 → 2021-05-23 | 380 | 2021-08-13 → 2022-05-22 |
| La Liga | 2022-23 | 1,520 | 2018-08-17 → 2022-05-22 | 380 | 2022-08-12 → 2023-06-04 |
| La Liga | 2023-24 | 1,900 | 2018-08-17 → 2023-06-04 | 380 | 2023-08-11 → 2024-05-26 |
| La Liga | 2024-25 | 2,280 | 2018-08-17 → 2024-05-26 | 380 | 2024-08-15 → 2025-05-25 |
| La Liga | 2025-26 | 2,660 | 2018-08-17 → 2025-05-25 | 380 | 2025-08-15 → 2026-05-24 |
| Ligue 1 | 2021-22 | 1,039 | 2018-08-10 → 2021-05-23 | 380 | 2021-08-06 → 2022-05-21 |
| Ligue 1 | 2022-23 | 1,419 | 2018-08-10 → 2022-05-21 | 380 | 2022-08-05 → 2023-06-03 |
| Ligue 1 | 2023-24 | 1,799 | 2018-08-10 → 2023-06-03 | 306 | 2023-08-11 → 2024-05-19 |
| Ligue 1 | 2024-25 | 2,105 | 2018-08-10 → 2024-05-19 | 306 | 2024-08-16 → 2025-05-17 |
| Ligue 1 | 2025-26 | 2,411 | 2018-08-10 → 2025-05-17 | 306 | 2025-08-15 → 2026-05-17 |
| Premier League | 2021-22 | 7,980 | 2000-08-19 → 2021-05-23 | 380 | 2021-08-13 → 2022-05-22 |
| Premier League | 2022-23 | 8,360 | 2000-08-19 → 2022-05-22 | 380 | 2022-08-05 → 2023-05-28 |
| Premier League | 2023-24 | 8,740 | 2000-08-19 → 2023-05-28 | 380 | 2023-08-11 → 2024-05-19 |
| Premier League | 2024-25 | 9,120 | 2000-08-19 → 2024-05-19 | 380 | 2024-08-16 → 2025-05-25 |
| Premier League | 2025-26 | 9,500 | 2000-08-19 → 2025-05-25 | 380 | 2025-08-15 → 2026-05-24 |
| Primeira Liga | 2021-22 | 918 | 2018-08-10 → 2021-05-19 | 306 | 2021-08-06 → 2022-05-15 |
| Primeira Liga | 2022-23 | 1,224 | 2018-08-10 → 2022-05-15 | 306 | 2022-08-05 → 2023-05-27 |
| Primeira Liga | 2023-24 | 1,530 | 2018-08-10 → 2023-05-27 | 306 | 2023-08-11 → 2024-05-18 |
| Primeira Liga | 2024-25 | 1,836 | 2018-08-10 → 2024-05-18 | 306 | 2024-08-09 → 2025-05-17 |
| Primeira Liga | 2025-26 | 2,142 | 2018-08-10 → 2025-05-17 | 306 | 2025-08-08 → 2026-05-16 |
| Serie A | 2021-22 | 1,140 | 2018-08-18 → 2021-05-23 | 380 | 2021-08-21 → 2022-05-22 |
| Serie A | 2022-23 | 1,520 | 2018-08-18 → 2022-05-22 | 380 | 2022-08-13 → 2023-06-04 |
| Serie A | 2023-24 | 1,900 | 2018-08-18 → 2023-06-04 | 380 | 2023-08-19 → 2024-06-02 |
| Serie A | 2024-25 | 2,280 | 2018-08-18 → 2024-06-02 | 380 | 2024-08-17 → 2025-05-25 |
| Serie A | 2025-26 | 2,660 | 2018-08-18 → 2025-05-25 | 380 | 2025-08-23 → 2026-05-24 |
| Greece | 2020-21 | 422 | 2018-08-25 → 2020-03-01 | 182 | 2020-09-11 → 2021-03-14 |
| Greece | 2023-24 | 604 | 2018-08-25 → 2021-03-14 | 182 | 2023-08-18 → 2024-03-03 |
| Greece | 2024-25 | 786 | 2018-08-25 → 2024-03-03 | 182 | 2024-08-17 → 2025-03-09 |

## Reproduce and inspect

From the repository root:

```bash
uv run python -m football_predictor.betting_benchmark
uv run pytest -q tests/test_betting.py tests/test_betting_benchmark.py
```

The command reads the bundled snapshot by default. Outputs go to ignored `data/local/research/betting-markets.json` and `betting-markets.csv.gz`. It does not use local synced results unless explicitly supplied with `--data`, does not overwrite the historical bundle and makes no network calls. A run with a different dataset is a new benchmark with its own fingerprint and populations.

[Full measured results, calibration bins and source fingerprints](reviews/2026-10-18-betting-markets.json)

## Tests and next checkpoints

42 new tests cover regulation settlement, refunds, fair prices, no-push market comparisons, invalid inputs, matrix bounds and missing tail mass, complement/monotonicity rules, home/away orientation, classwise alignment, serving parity for both policy branches, first-appearance priors, same-date result perturbation, chronological fit boundaries, calibration-bin boundaries and complete season folds. Backend regression suite: 333 tests passed; Ruff passed. Existing production/UI files are unchanged.

1. Audit/fix omitted-year inference for the 2019–20 July restart, rebuild from verified source dates, and repeat these locked benchmarks. Treat this as a data-correctness prerequisite to a production goal-market choice.
2. Build the Betting tab with Result / Goals / Teams / Scores sections, readable percentages and two-decimal prices. Result, double chance and draw-no-bet can use the current 1X2 forecast directly. Display experimental goal-model provenance/validation limits clearly. Do not silently replace existing scorelines or use unrelated probabilities to explain each other.
3. Extend live odds only on demand, cache by event/period/market/line, show bookmaker and quote timestamp, and expose unavailable markets. Preserve manual entry. Track the separate Odds API credits: Goal API’s 1,000/day quota is not an odds allowance. Never automatically fetch every extra market for every fixture.
4. Add per-market journal snapshots and regulation-time settlement, retaining the original forecast and quote provenance. Keep probability differences distinct from expected returns; no automatic “best bet” or staking claims.

Official provider references: [markets](https://the-odds-api.com/sports-odds-data/betting-markets.html), [event odds and quota](https://the-odds-api.com/liveapi/guides/v4/). Documented market keys are not a guarantee of availability for every bookmaker/league/event. No key or paid API was used for this checkpoint.
