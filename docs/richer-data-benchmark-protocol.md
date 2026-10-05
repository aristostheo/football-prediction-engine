# Richer-data research — Checkpoint 1: frozen baseline and protocol

Status: baseline and evaluation rules frozen. Production prediction code and behavior are unchanged. Exact validation/test seasons will be locked after the source-coverage audit in Checkpoint 2, using coverage metadata only and before measuring feature performance.

Snapshot date: 2026-10-05 UTC.

## Baseline identity

Repository: aristostheo/football-prediction-engine  
Repository commit at snapshot: bc3b4e5e1b0b756edbd70ac36501fccfb965fd73

Production source files and Git blob SHAs:

| File | SHA |
|---|---|
| src/football_predictor/features.py | d11db7ca018bfbbc94bfa1d677ee6c211db6f4fe |
| src/football_predictor/models.py | 126175ce492838721ab5e9443a48cc48b5009aee |
| src/football_predictor/evaluation.py | 81c964180ddbad5b9e089e9a69775ca3dba0f55a |
| src/football_predictor/prediction.py | 69358ad7710ee5ef246bfc465fd492668cb9f169 |

Bundled results: data/model/historical_matches.csv.gz  
Dataset SHA-256: 21ce84a7d8973c8ad5c1884c0a74eaeb2ed37089512b791487b4a9a5e63c670a  
Manifest generated 2026-10-02; 10,995 match rows (9,930 Premier League, 1,065 Greece); latest results through 2026-09-20. Partial 2026–27 seasons are not eligible as final test seasons.

Historical odds are a separate benchmark input, not part of the football model. The full user-provided exports used previously are retained locally and are not committed:

| Local export | Rows | SHA-256 |
|---|---:|---|
| Database - Odds - England Premier League - LS-2(1).csv | 1,900 | 1925941835a684741d885aca1ac7bfed2b1e7ab6f5f9557238c428e3d05139b4 |
| Database - Odds - Greece Super League - LS(2).csv | 1,434 | d90aae96615d9b16b7ae771e3a072951238f7c261a5c3e31698d5cf0a4a00ded |

The two 25-row preview exports are excluded.

## Locked production baseline

- Team state is constructed from prior results. Recent form uses the last five matches with equal weights; it includes points, goals for/against, venue points, rest days (capped at 97), and Elo.
- Elo starts at 1500, uses K=20 and a fixed 60-point home advantage. Gaps over 180 days reset recent form and regress Elo toward the mean using a 365-day half-life.
- Separate home- and away-goal Poisson regressions predict goal rates. Premier League 1X2 probabilities use the fixed 25% Elo / 75% independent-Poisson blend; Greece uses Elo alone.
- Production has no explicit post-fit calibration transform. H2H is not used in production 1X2 probabilities. Scorelines use independent Poisson goal rates (0–12 goals); there is no Dixon–Coles correction.
- Historical features are built by date, and matches sharing a date use the same prior state. This avoids using another same-date fixture’s result when kickoff times are unavailable.
- No xG, shots, lineup, injury, weather, or player-availability fields are present in the bundled historical results.

For the full implementation description and prior model results, see docs/probability-benchmark.md.

## Frozen evaluation rules

1. Keep the production model as an unchanged reference. All feature work remains in experiments/ or another isolated research path.
2. Use expanding chronological folds. At each kickoff, use only results and feature records from strictly earlier matches. Never use random splits, final standings, same-day results, or a match’s own post-match statistics.
3. Select feature definitions, windows, decay rates, model parameters, and calibration using earlier validation data only. Do not inspect the final test scores until those decisions are fixed.
4. Choose final seasons only after Checkpoint 2 establishes feature coverage. Select them from coverage and date metadata, before model-performance comparisons. Prefer the latest complete season with adequate xG coverage; use earlier complete seasons for expanding training and validation.
5. Compare production and each feature-enhanced challenger on the identical fixture/date intersection where the challenger has usable data. Also report the baseline on its full available fixture set and the challenger’s coverage/missingness, so a restricted sample cannot masquerade as an improvement.
6. Report each league separately. If a league has fewer than two complete held-out seasons with adequate coverage, label conclusions exploratory rather than evidence for deployment.
7. Primary metric: multiclass Log Loss. Also report Brier, RPS, accuracy (secondary), classwise calibration error/reliability buckets, and paired season-block uncertainty. For scorelines, report scoreline negative log likelihood, exact-score hit rate, and goal MAE.
8. Keep margin-free closing odds separate from independent football features. Any market-informed blend is a distinct experiment whose weights are selected on validation data only.
9. Report source coverage, missingness, match/date ranges, training/validation/test counts, and data fingerprint for every benchmark run.

## Checkpoint 2 gate

The next checkpoint audits source availability and historical timestamps. No xG experiment or external data acquisition should begin until the audit identifies a source with documented league/season coverage, match linkage, pre-kickoff usability, licensing, and cost. If those conditions cannot be verified, report the limitation and stop that feature path rather than approximating the missing data.
