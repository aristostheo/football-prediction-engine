# Elo versus calibrated logistic regression

The first model comparison uses the exact same leakage-safe feature set and the
final chronological 20% of each competition. Models are fit independently per
league. The logistic pipeline median-imputes missing first-match rest values,
standardizes features, fits L2-regularized multinomial logistic regression, and
uses three time-ordered calibration folds on training data only.

The Poisson candidate separately models home and away expected goals. Its
regularization is selected with three chronological training folds, then
independent Poisson scorelines from 0-0 to 12-12 are summed and normalized into
W/D/L probabilities.

| Competition | Model | Log loss | Brier score | Accuracy |
| --- | --- | ---: | ---: | ---: |
| Premier League | Elo baseline | 0.9888 | 0.5892 | 54.11% |
| Premier League | Calibrated logistic | 0.9914 | 0.5907 | 52.89% |
| Premier League | Poisson goal model | 0.9886 | 0.5893 | 53.26% |
| Super League Greece | Elo baseline | 0.9857 | 0.5860 | 51.03% |
| Super League Greece | Calibrated logistic | 1.0021 | 0.5967 | 51.03% |
| Super League Greece | Poisson goal model | 1.0080 | 0.6019 | 48.45% |
| Premier League | Validation-selected ensemble | **0.9879** | **0.5888** | 53.63% |
| Super League Greece | Validation-selected ensemble | 0.9893 | 0.5887 | 51.03% |

The logistic model does not beat Elo. The Poisson goal model narrowly improves
Premier League log loss by 0.0002 but is worse on its Brier score and on every
reported Greek metric. The validation-selected ensemble improves both Premier
League probability metrics, while pure Elo remains better for Greece. These
results are intentionally retained: later candidates must improve the same fixed
metrics and split, not merely accuracy.

## Ensemble selection without holdout tuning

For each league, the initial 80% pre-holdout training period is divided again:
the earliest 80% fits Poisson and the latest 20% selects one of five fixed Elo
weights (`1.0`, `0.75`, `0.5`, `0.25`, `0.0`) by validation log loss. The chosen
weight is then used once on the untouched final 20% holdout, with Poisson
refitted on all pre-holdout training rows.

| Competition | Selected Elo weight | Final policy |
| --- | ---: | --- |
| Premier League | 0.25 | Use the 25% Elo / 75% Poisson ensemble. |
| Super League Greece | 0.75 | Keep pure Elo; the ensemble is worse on final holdout. |
