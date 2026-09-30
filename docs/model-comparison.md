# Elo versus calibrated logistic regression

The first model comparison uses the exact same leakage-safe feature set and the
final chronological 20% of each competition. Models are fit independently per
league. The logistic pipeline median-imputes missing first-match rest values,
standardizes features, fits L2-regularized multinomial logistic regression, and
uses three time-ordered calibration folds on training data only.

| Competition | Model | Log loss | Brier score | Accuracy |
| --- | --- | ---: | ---: | ---: |
| Premier League | Elo baseline | 0.9888 | 0.5892 | 54.11% |
| Premier League | Calibrated logistic | 0.9914 | 0.5907 | 52.89% |
| Super League Greece | Elo baseline | 0.9857 | 0.5860 | 51.03% |
| Super League Greece | Calibrated logistic | 1.0021 | 0.5967 | 51.03% |

The logistic model does not beat Elo on held-out probability quality, so Elo
remains the current champion. This result is intentionally retained: the next
candidate must improve the same fixed metrics and split, not merely accuracy.
