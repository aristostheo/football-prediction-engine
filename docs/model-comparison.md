# Model comparison (exploratory chronological split)

This snapshot reports a single chronological 80/20 split for each league. Each
model is trained on earlier rows and evaluated on later rows. The features use
same-day batching, so every match on a date sees results strictly before that
date. The metrics are descriptive, not reliable rankings: there is one test
period, the Greek sample is small, and the historical Greek schedule has gaps.

| Competition | Model | Train | Test | Log loss | Brier | RPS | Accuracy |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Premier League | Training-rate climatology | 7,944 | 1,986 | 1.0706 | 0.6479 | 0.2332 | 43.96% |
| Premier League | Elo | 7,944 | 1,986 | 0.9805 | 0.5838 | 0.2017 | 53.98% |
| Premier League | Calibrated logistic | 7,944 | 1,986 | 0.9792 | 0.5833 | 0.2013 | 53.37% |
| Premier League | Poisson | 7,944 | 1,986 | 0.9765 | 0.5817 | 0.2008 | 53.47% |
| Premier League | Validation-selected ensemble | 7,944 | 1,986 | 0.9765 | 0.5815 | 0.2007 | 53.63% |
| Super League Greece | Training-rate climatology | 852 | 213 | 1.0657 | 0.6448 | 0.2390 | 44.13% |
| Super League Greece | Elo | 852 | 213 | 0.9650 | 0.5712 | 0.2029 | 56.81% |
| Super League Greece | Calibrated logistic | 852 | 213 | 0.9617 | 0.5680 | 0.2003 | 55.87% |
| Super League Greece | Poisson | 852 | 213 | 0.9627 | 0.5707 | 0.2025 | 56.34% |
| Super League Greece | Validation-selected ensemble | 852 | 213 | 0.9627 | 0.5707 | 0.2025 | 56.34% |

The ensemble weight is selected on the late 20% of the training period, then
applied to the final test period. That procedure is implemented without direct
test-score optimization. However, the production policy for Greece was changed
to pure Elo after inspecting the earlier final-holdout result. Therefore the
historical model choice has been influenced by holdout performance, and the
table must not be described as an untouched independent test. No new policy
should be selected from these rows.

The single-split table remains for continuity, but the expanding-season results
below are the preferred comparison. A closing-odds benchmark using local
Footiqo exports is now available; its measured snapshot, match coverage, and
uncertainty are documented in [the benchmark guide](market-benchmark.md).
Because these test seasons have now been inspected, they are exploratory for
future model selection. Keep future-season results separate when evaluating
changes selected after this benchmark.

RPS is the three-category ranked probability score with outcomes ordered home
win, draw, away win; lower scores are better. The climatology probabilities use
smoothed outcome frequencies from the training rows only.

## Expanding-window season walk-forward

Each test fold is one complete season. Training uses all earlier matches, and
the feature stream updates ratings online within the test season. The most
recent five complete Premier League seasons and every available complete Greek
season after the initial training season are tested. Partial seasons fail the
schedule check and are excluded. Current folds cover five PL seasons (1,900
matches) and four Greek seasons (728 matches).

| Competition | Model | Test seasons | Log loss | Brier | RPS | Accuracy |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Premier League | Climatology | 2021-22–2025-26 | 1.0695 | 0.6471 | 0.2326 | 44.16% |
| Premier League | Elo | 2021-22–2025-26 | 0.9787 | 0.5826 | 0.2009 | 54.11% |
| Premier League | Logistic | 2021-22–2025-26 | 0.9766 | 0.5816 | 0.2002 | 54.05% |
| Premier League | Poisson | 2021-22–2025-26 | 0.9738 | 0.5799 | 0.1996 | 53.74% |
| Premier League | Ensemble | 2021-22–2025-26 | 0.9741 | 0.5799 | 0.1997 | 53.84% |
| Super League Greece | Climatology | 2019-20, 2020-21, 2023-24, 2024-25 | 1.0778 | 0.6525 | 0.2306 | 43.41% |
| Super League Greece | Elo | 2019-20, 2020-21, 2023-24, 2024-25 | 0.9854 | 0.5861 | 0.1985 | 52.88% |
| Super League Greece | Logistic | 2019-20, 2020-21, 2023-24, 2024-25 | 0.9811 | 0.5840 | 0.1970 | 52.06% |
| Super League Greece | Poisson | 2019-20, 2020-21, 2023-24, 2024-25 | 0.9805 | 0.5819 | 0.1960 | 51.79% |
| Super League Greece | Ensemble | 2019-20, 2020-21, 2023-24, 2024-25 | 0.9840 | 0.5840 | 0.1968 | 52.88% |

Paired 95% season-block bootstrap intervals for log-loss differences against
Elo are below. A positive difference means the candidate has higher log loss
than Elo. The interval resamples entire test seasons and weights each sampled
season equally.

| Competition | Candidate − Elo | Mean difference | 95% interval |
| --- | --- | ---: | ---: |
| Premier League | Climatology | 0.0908 | [0.0703, 0.1101] |
| Premier League | Logistic | -0.0021 | [-0.0047, 0.0006] |
| Premier League | Poisson | -0.0048 | [-0.0101, -0.0009] |
| Premier League | Ensemble | -0.0046 | [-0.0083, -0.0016] |
| Super League Greece | Climatology | 0.0924 | [0.0774, 0.1073] |
| Super League Greece | Logistic | -0.0044 | [-0.0339, 0.0252] |
| Super League Greece | Poisson | -0.0049 | [-0.0221, 0.0123] |
| Super League Greece | Ensemble | -0.0014 | [-0.0151, 0.0123] |

The large climatology gaps are clear in both competitions. Differences among
Elo, logistic, Poisson, and the ensemble are much smaller; the Greek intervals
include zero and use only four season blocks. Even the narrower Premier League
intervals should be treated as provisional because five season blocks provide
limited evidence for model selection. The deployed policy is not changed based
on these already-inspected folds.

## Exploratory Elo parameter check

A small development-only sweep rebuilt Premier League Elo features with
K-factors 15, 20, 25, and 30 and home advantages 60 or 90. It scored the six
complete seasons from 2015-16 through 2020-21, averaging season log loss.
The lowest grid score was K=25/home advantage=60 at 0.97998; the current
K=20/home advantage=60 scored 0.98016. The paired mean difference was only
-0.00018, with a six-season block-bootstrap 95% interval of [-0.00137,
0.00105]. This is not evidence of a reliable gain, and choosing the best value
from the same grid makes its score optimistic. The production parameters remain
unchanged. Greek parameters were not tuned independently because the available
continuous complete-season sample is too small.

These historical comparisons and the closing-odds snapshot are now development
evidence, not untouched final tests. The in-progress 2026-27 season is reserved
for prospective evaluation after the season is complete. Any parameter or
calibration choice made from historical seasons must be frozen before that
evaluation.

Run the season walk-forward comparison locally with:

```bash
uv run python -m football_predictor.feature_cli \
  --input data/model/historical_matches.csv.gz \
  --output /tmp/historical_match_features.csv
uv run python -m football_predictor.model_cli \
  --input /tmp/historical_match_features.csv \
  --walk-forward
```


## Head-to-head probability experiment

**Correction:** the first H2H calculation incorrectly credited every non-draw result to the historical home club, even when it lost. Those earlier H2H metrics are invalid and should be disregarded. The count display was corrected to orient wins and losses to the forecasted home team, and a regression test now covers both venue orders, wins, losses, draws, and exclusion of same-day results.

The expanded experiment compares the previous 5, 10, or 20 meetings and all prior meetings. It also tests calendar-time exponential decay with 2-, 5-, and 10-year half-lives, so more recent matches receive greater weight. Every H2H estimate is shrunk toward the current model forecast with prior strength 6. The H2H mixture weight and history method are selected using only earlier complete-season folds. The first test season uses the unchanged model. Same-day results are excluded.

| Competition | Test seasons | Matches | Existing log loss | Nested history selection | H2H − existing | Paired season-block 95% interval |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Premier League | 2016-17–2025-26 | 3,800 | 0.96877 | Mix of last 10, 5–10% H2H weight | -0.00052 | [-0.00130, 0.00021] |
| Super League Greece | 2019-20, 2020-21, 2023-24, 2024-25 | 728 | 0.98543 | All prior meetings, 30–50% H2H weight | -0.01182 | [-0.02201, -0.00275] |

A separate run constrained the candidate set to recency-weighted histories only:

| Competition | Existing log loss | Recency-weighted H2H log loss | H2H − existing | Paired season-block 95% interval |
| --- | ---: | ---: | ---: | ---: |
| Premier League | 0.96877 | 0.96861 | -0.00016 | [-0.00069, 0.00034] |
| Super League Greece | 0.98543 | 0.97422 | -0.01122 | [-0.02052, -0.00274] |

Lower log loss is better. The expanded H2H variants show no clear PL gain; both PL intervals include zero, and the change is very small. Greece shows a promising improvement in all three seasons where the nested process selected a nonzero H2H weight. However, there are only four Greek test-season blocks, the history omits two seasons, and several years of results are missing. The season-block interval is therefore fragile, and the Greek result needs another independent evaluation before changing production W/D/L probabilities. H2H remains context-only in the dashboard for now.

Run both candidate sets from the repository root:

```bash
PYTHONPATH=src python experiments/h2h_walk_forward.py
PYTHONPATH=src python experiments/h2h_walk_forward.py --recency-only
```
