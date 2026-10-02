# Model comparison (exploratory chronological split)

This snapshot reports a single chronological 80/20 split for each league. Each
model is trained on earlier rows and evaluated on later rows. The features use
same-day batching, so every match on a date sees results strictly before that
date. The metrics are descriptive, not reliable rankings: there is one test
period, the Greek sample is small, and the historical Greek schedule has gaps.

| Competition | Model | Train | Test | Log loss | Brier | RPS | Accuracy |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Premier League | Training-rate climatology | 7,944 | 1,986 | 1.0706 | 0.6479 | 0.2332 | 43.96% |
| Premier League | Elo | 7,944 | 1,986 | 0.9810 | 0.5842 | 0.2019 | 54.28% |
| Premier League | Calibrated logistic | 7,944 | 1,986 | 0.9818 | 0.5850 | 0.2021 | 53.47% |
| Premier League | Poisson | 7,944 | 1,986 | 0.9788 | 0.5831 | 0.2015 | 53.63% |
| Premier League | Validation-selected ensemble | 7,944 | 1,986 | 0.9785 | 0.5828 | 0.2013 | 53.73% |
| Super League Greece | Training-rate climatology | 852 | 213 | 1.0657 | 0.6448 | 0.2390 | 44.13% |
| Super League Greece | Elo | 852 | 213 | 0.9397 | 0.5540 | 0.1948 | 56.81% |
| Super League Greece | Calibrated logistic | 852 | 213 | 0.9575 | 0.5653 | 0.1989 | 56.81% |
| Super League Greece | Poisson | 852 | 213 | 0.9658 | 0.5725 | 0.2034 | 54.93% |
| Super League Greece | Validation-selected ensemble | 852 | 213 | 0.9504 | 0.5613 | 0.1982 | 56.34% |

The ensemble weight is selected on the late 20% of the training period, then
applied to the final test period. That procedure is implemented without direct
test-score optimization. However, the production policy for Greece was changed
to pure Elo after inspecting the earlier final-holdout result. Therefore the
historical model choice has been influenced by holdout performance, and the
table must not be described as an untouched independent test. No new policy
should be selected from these rows.

The next evaluation checkpoint replaces this single split with expanding
season-by-season walk-forward predictions, includes a base-rate climatology
baseline and Ranked Probability Score, and estimates paired uncertainty. A
closing-odds comparison requires a separately sourced, time-aligned odds
dataset and is tracked as follow-up work.

RPS is the three-category ranked probability score with outcomes ordered home
win, draw, away win; lower scores are better. The climatology probabilities use
smoothed outcome frequencies from the training rows only.
