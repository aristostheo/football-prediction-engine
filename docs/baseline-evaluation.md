# Initial Elo baseline evaluation

The V1 Elo baseline turns each match's pre-match ratings into home-win, draw,
and away-win probabilities. Ratings update online after each match date, so a
later test match may use results from an earlier test-period date. No row
shuffling is used.

The current snapshot reports a single final-20% chronological split. These
results are descriptive and should not be used alone to claim that one model
will outperform another. The final Greek holdout was inspected when choosing
the production policy, so it is not an independent test set.

| Competition | Matches | Log loss | Brier score | RPS | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Premier League | 1,986 | 0.9805 | 0.5838 | 0.2017 | 53.98% |
| Super League Greece | 213 | 0.9650 | 0.5712 | 0.2029 | 56.81% |

See [model comparison](model-comparison.md) for the corresponding candidate
models, expanding-season walk-forward metrics, and the evaluation limitations.
