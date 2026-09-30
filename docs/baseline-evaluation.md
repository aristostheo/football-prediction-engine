# Initial Elo baseline evaluation

The V1 baseline converts pre-match Elo ratings into home-win, draw, and away-win
probabilities. It is an online benchmark: each prediction uses only ratings from
earlier match dates, while previous test-period results may update later ratings.
That mirrors how the model would operate after deployment and introduces no
future leakage.

The holdout is the final 20% of each competition, selected chronologically with
no row shuffling.

| Competition | Matches | Log loss | Brier score | Accuracy |
| --- | ---: | ---: | ---: | ---: |
| Premier League | 1,900 | 0.9888 | 0.5892 | 54.11% |
| Super League Greece | 194 | 0.9857 | 0.5860 | 51.03% |

These are baseline measurements, not the final model. The next comparison will
use the same time-aware split and metrics for calibrated statistical and
machine-learning candidates.
