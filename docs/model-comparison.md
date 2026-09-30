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

The logistic model does not beat Elo. The Poisson goal model narrowly improves
Premier League log loss by 0.0002 but is worse on its Brier score and on every
reported Greek metric. Elo therefore remains the practical overall champion.
This result is intentionally retained: the next candidate must improve the same
fixed metrics and split, not merely accuracy.
