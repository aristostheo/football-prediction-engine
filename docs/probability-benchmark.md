# Experimental probability benchmark

Status: research only. The production prediction path was not changed.

This benchmark asks whether a goal-based Dixon–Coles model, recent-match weighting, Elo, H2H, a tree model, or an ensemble improves the deployed probabilities. It uses chronological validation and later-season testing. Results are evidence for the next decision, not a production release.

## 1. Existing production method

Source inspected: src/football_predictor/features.py, models.py, evaluation.py, prediction.py, and market.py.

- Pre-match features are built in competition/date order. All matches on one date receive the same prior team state; their scores are applied only after all that date’s feature rows are emitted.
- Form uses the most recent five matches, with equal weights. It includes points per match, goals for/against per match, venue-specific points, and match count. Rest days are capped at 97.
- Elo starts at 1500, updates with K=20 from the match result, and uses a fixed 60-point home advantage. A gap over 180 days clears recent form and regresses Elo toward 1500 with a 365-day half-life.
- The goal model fits separate home- and away-goal Poisson regressions. It imputes missing values, standardizes features, and selects regularization from alpha values 0.01, 0.1, 1, and 10 with three chronological folds.
- Premier League 1X2 probabilities are 25% Elo and 75% independent-Poisson outcome probabilities. Greece uses Elo probabilities alone. The prediction module has a promoted/unseen-team fallback using Elo 1400 and shrinkage toward league priors.
- The production path has no separate probability-calibration transform. Its fitted regression, regularization, and fixed blend are not the same as an explicit calibration step.
- H2H summaries are displayed as context but do not affect production 1X2 probabilities.
- Scoreline probabilities are currently formed from independent Poisson goal rates, truncated at 0–12 goals and normalized. There is no low-score Dixon–Coles adjustment.

Main weaknesses observed: equal weighting within the five-match form window; fixed Elo/home parameters; independent goal assumptions; no low-score correction; Greek production ignores the fitted goal model for 1X2; limited and gapped Greek history; and no historical xG, shots, lineups, injuries, or weather in the bundled match data.

## 2. Data and time splits

Bundled source: data/model/historical_matches.csv.gz, manifest generated 2026-10-02. It contains 10,995 results: 9,930 Premier League and 1,065 Greek Super League matches. Results run through 2026-09-20. Partial 2026–27 seasons (50 Premier League and 35 Greek matches) were excluded from validation and test. The latest complete Premier League season is 2025–26.

The model-selection design is expanding by season. Every fold fits on matches dated before that season and predicts the entire season. Candidate decay/model choice uses validation seasons only; test seasons are later and untouched by those choices.

| League | Validation seasons | Validation matches and dates | Final test seasons | Test matches and dates | Training sizes for final test folds |
|---|---|---:|---|---:|---|
| Premier League | 2016–17 to 2020–21 | 1,900; 2016-08-13 to 2021-05-23 | 2021–22 to 2025–26 | 1,900; 2021-08-13 to 2026-05-24 | 7,980; 8,360; 8,740; 9,120; 9,500 |
| Greece Super League | 2019–20, 2020–21 | 364; 2019-08-24 to 2021-03-14 | 2023–24, 2024–25 | 364; 2023-08-18 to 2025-03-09 | 604; 786 |

For the Premier League validation folds, training sizes were 6,080, 6,460, 6,840, 7,220, and 7,600. Greek validation training sizes were 240 and 422. Counts vary by fold because each later season includes the earlier seasons. Greece has no bundled 2021–22 or 2022–23 results; its final test therefore contains only two season blocks.

Historical odds were supplied locally as Footiqo/1xBet 1X2 exports, not committed to the repository. They are de-vigged by normalizing reciprocal decimal prices. On the final test, odds matched 1,900/1,900 Premier League fixtures and 361/364 Greek fixtures. Across the full four-season Greek odds sample, three fixture rows did not match the canonical results by date/team key. This is a single-bookmaker closing-price benchmark, not a consensus market. The raw exports are intentionally not stored in the repository.

## 3. Leakage controls

- The existing feature builder groups by competition and date and updates team state only after same-date features are emitted.
- A direct mutation check changed outcomes on and after 2025-08-30 and confirmed that all 10,494 earlier rows’ pre-match features were unchanged.
- A second mutation changed a result on a date with four fixtures and confirmed that all four same-date feature rows were unchanged.
- Every candidate fold fits goal/team parameters only on rows before the test season. H2H searches also require a prior match date strictly before the fixture date.
- Validation seasons select decay, H2H, and ensemble settings; final test seasons are later.

These checks found no obvious future-result leakage in the tested paths. They do not prove that every upstream historical source timestamp reflects the original kickoff-time data. Odds are used only as a separate benchmark or as a validation-selected market blend, never as features in the independent football model.

## 4. Experimental models

The separate implementation is experiments/probability_benchmark.py. It fits a log-linear goal model with learned league intercept, learned global home effect, team attack and defense effects, and optional pre-match Elo difference. Opponent quality is adjusted through the simultaneous attack/defense effects rather than raw goals-per-game. Training likelihood uses exponential weights with half-life candidates of no decay, 90, 180, 365, and 730 days. Low-score 0–0, 0–1, 1–0, and 1–1 cells receive Dixon–Coles tau corrections; rho is estimated from training data. Score matrices are normalized and summed into 1X2 probabilities.

The validation-selected model was 365-day half-life without Elo in the Premier League, and 180-day half-life without Elo in Greece. Adding Elo was tested as an ablation. Team-specific home effects were not added because the Greek season sample is too small and the model already estimates league-specific home effects.

A calibrated HistGradientBoostingClassifier was also evaluated on the available pre-match features (Elo, five-match form, goals for/against, venue points, match counts, and rest). It used chronological sigmoid calibration. LightGBM and XGBoost were not installed in the analysis environment, so this is a scikit-learn tree-model comparison, not a claim about those libraries.

Calibration was measured for each model. The experimental Dixon–Coles probabilities were additionally temperature-scaled using validation-only predictions; that did not improve Premier League test log loss and improved Greece by less than 0.001.

## 5. Final chronological test results

Scores are on the stated final test fixtures. Lower Log Loss, Brier, RPS, and calibration error are better; higher accuracy is better. Market rows use the odds-matched subset. The current production policy is fixed, not recalibrated.

| League | Model | N | Log Loss | Brier | RPS | Accuracy |
|---|---|---:|---:|---:|---:|---:|
| Premier League | Production (fixed Elo/Poisson policy) | 1,900 | 0.9741 | 0.5799 | 0.1997 | 0.5384 |
| Premier League | Dixon–Coles, decay selected on validation | 1,900 | 0.9963 | 0.5945 | 0.2071 | 0.5111 |
| Premier League | Calibrated HistGradientBoosting | 1,900 | 0.9943 | 0.5925 | 0.2050 | 0.5321 |
| Premier League | Production/DC blend, DC weight selected on validation | 1,900 | 0.9764 | 0.5812 | 0.2004 | 0.5311 |
| Premier League | De-vigged closing odds | 1,900 | 0.9570 | 0.5679 | 0.1940 | 0.5537 |
| Greece Super League | Production Elo policy | 364 | 1.0012 | 0.5969 | 0.2053 | 0.5330 |
| Greece Super League | Dixon–Coles, decay selected on validation | 364 | 0.9704 | 0.5721 | 0.1946 | 0.5385 |
| Greece Super League | Calibrated HistGradientBoosting | 364 | 1.0255 | 0.6140 | 0.2136 | 0.4945 |
| Greece Super League | Production/DC blend, DC weight selected on validation | 364 | 0.9675 | 0.5717 | 0.1943 | 0.5495 |
| Greece Super League | De-vigged closing odds | 361 | 0.9252 | 0.5449 | 0.1804 | 0.5540 |

The independent market was best in both leagues. On Premier League test fixtures, the production model’s Log Loss exceeded the closing-market Log Loss by 0.0171; the existing five-season paired season-block bootstrap estimated a 95% interval of 0.0111 to 0.0227. The market-assisted walk-forward procedure selected 100% market weight, so the model did not add useful information to those closing prices.

Premier League Dixon–Coles was worse than production by 0.0222 Log Loss. Its paired differences by test season were +0.0010, +0.0482, +0.0123, +0.0359, and +0.0138. A five-season block bootstrap gives a positive average difference, but there are only five blocks and the spread is large; this is evidence against replacing the model, not a precise estimate of future loss.

Greece Dixon–Coles improved over production by 0.0309 Log Loss across the two test seasons. The season differences were −0.0543 and −0.0075. Two season blocks are too few to establish a stable league-wide improvement. The odds benchmark still beat it by about 0.043 Log Loss on the 361 matched fixtures.

## 6. Calibration

One-vs-rest expected calibration error (ECE) for home/draw/away probabilities:

| League/model | Home ECE | Draw ECE | Away ECE |
|---|---:|---:|---:|
| Premier League production | 0.0196 | 0.0052 | 0.0122 |
| Premier League Dixon–Coles | 0.0184 | 0.0067 | 0.0192 |
| Greece production | 0.0862 | 0.0128 | 0.0646 |
| Greece Dixon–Coles | 0.0298 | 0.0336 | 0.0459 |

Maximum-outcome confidence buckets show the average stated confidence and actual accuracy for the predicted most likely outcome. Small bins should not be over-read.

| League/model | Confidence bin | N | Mean confidence | Accuracy |
|---|---:|---:|---:|---:|
| Premier League production | 60–65% | 176 | 62.2% | 64.8% |
| Premier League production | 70–75% | 89 | 72.4% | 79.8% |
| Premier League production | 80%+ | 46 | 83.7% | 93.5% |
| Premier League Dixon–Coles | 60–65% | 170 | 62.4% | 62.4% |
| Premier League Dixon–Coles | 70–75% | 87 | 72.3% | 74.7% |
| Premier League Dixon–Coles | 80%+ | 30 | 83.1% | 86.7% |
| Greece production | 60–65% | 21 | 62.2% | 71.4% |
| Greece Dixon–Coles | 60–65% | 29 | 62.6% | 72.4% |
| Greece market | 60–65% | 28 | 62.7% | 64.3% |

The Greek production ECE is high, especially for home and away outcomes. DC improves those classwise gaps on this small test, while its draw ECE is worse. Calibration is not summarized by accuracy alone; the full probability scores remain the selection criteria.

## 7. Ablations

| Ablation | Validation finding | Final test finding |
|---|---|---|
| Exponential decay | 365 days selected for PL; 180 days for Greece | The selected DC model still lost to production in PL. Greek DC won on two seasons; instability across seasons remains. |
| Elo in DC | DC+Elo did not win overall validation selection in either league | In PL, DC+Elo at 180 days improved over DC-180 but still trailed production. In Greece it worsened DC-180. |
| Form window 5/8/10 | PL validation Log Loss: 0.96347 / 0.96296 / 0.96319; selected 8 | PL test: 0.97407 / 0.97378 / 0.97379. Gain from 5 to 8 is only 0.00030. Greece is Elo-only in production, so its form window does not alter 1X2 probabilities. |
| H2H removed / overall / venue-aware | PL selected no H2H. Greece selected small overall H2H (20% blend after sample-size shrinkage); venue-aware was worse in validation. | PL no-H2H remained best. Greece overall H2H changed DC Log Loss from 0.97036 to 0.96707, a 0.00329 improvement; only two test seasons. |
| Advanced match statistics | Historical data has no xG/xGA, shots, chances, lineups, injuries, or weather. | Not tested; no values were fabricated. |
| Market as an input | Kept separate from independent models | Historical market probabilities outperformed all independent models. Market-assisted selection chose the market alone; it did not justify blending model probabilities into the market. |

The learned DC home-goal multiplier in the final fitted folds was 1.144 for the Premier League and 1.279 for Greece. These are league-level estimates and may be noisy, especially in Greece. Team-specific home effects were not tested.

## 8. Scoreline evaluation

The current displayed scoreline rates and experimental DC score matrix were evaluated on the same 2,264 final-test fixtures. Results:

| Scoreline model | Goal MAE per team | Exact-score hit rate | Exact-score negative log likelihood |
|---|---:|---:|---:|
| Existing independent Poisson rates | 0.920 | 11.44% | 2.964 |
| Dixon–Coles score matrix | 0.942 | 11.40% | 2.995 |

The low-score correction did not improve these scoreline metrics in this run. DC still produces a reusable full score matrix, but the current Poisson scoreline distribution performed slightly better here.

Examples from held-out matches (production H/D/A; DC H/D/A; actual):
- Brentford–Arsenal, 2021-08-13: 26.7/26.1/47.2%; 27.0/23.3/49.7%; 2–0.
- Manchester United–Fulham, 2023-05-28: 64.1/21.1/14.8%; 63.9/22.1/14.0%; 2–1.
- Manchester City–Bournemouth, 2025-05-20: 68.1/19.4/12.5%; 83.9/10.7/5.4%; 3–1.
- Aris–AEK, 2025-03-09: 32.1/27.1/40.8%; 29.3/29.4/41.3%; 0–0.

## 9. Recommendation

Recommendation: A — keep the current production system for now. Do not replace it with Dixon–Coles or the tested ensemble yet.

There is no material Premier League gain: production beats the validation-selected DC model, and the validation-selected production/DC ensemble is slightly worse than production on test. Greece DC and a validation-selected DC blend improve test scores, but the test has only two seasons, large season-to-season swings, and an incomplete history. The modest form-window and H2H gains are too small to justify complexity without more seasons. The market is the strongest benchmark and remains a separate source of probabilities.

If advancing this research, prioritize collecting more complete Greek seasons and historical team statistics (especially xG/xGA) and continue the locked-model walk-forward. Consider a production change only after repeated future-season tests confirm an improvement in log loss, Brier, RPS, and calibration. No production source or prediction behavior was changed by this experiment.
