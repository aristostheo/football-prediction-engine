# StatsBomb Open Data xG coverage audit

**Audit date:** October 28, 2026

**Purpose:** Determine whether StatsBomb Open Data can support a leakage-safe xG
experiment for the current seven-league project. This is a coverage audit, not a
model benchmark. Production prediction code and probabilities were not changed.

## Finding

The public StatsBomb archive is useful for football research, but it does not
provide sufficiently broad overlap with the project's bundled match history for
a credible xG walk-forward comparison. Of 24,950 bundled results, 584 match
records (2.34%) matched StatsBomb's event-available match catalog by league,
date, and canonical home/away teams; all 584 also had matching final scores.

| Competition | StatsBomb event-available matches | Exact matches in our history | Overlapping seasons |
| --- | ---: | ---: | --- |
| Premier League | 418 | 418 | 2003/04 (38), 2015/16 (380) |
| La Liga | 867 | 89 | 2018/19 (29), 2019/20 (27), 2020/21 (33) |
| Bundesliga | 68 | 28 | 2023/24 (28) |
| Ligue 1 | 435 | 49 | 2021/22 (21), 2022/23 (28) |
| Serie A | 381 | 0 | None |
| Super League Greece | 0 | 0 | No competition entry found |
| Primeira Liga | 0 | 0 | No competition entry found |
| **Total** | **2,169** | **584** | — |

The archive includes a full 2015/16 match set for the Premier League, La Liga,
and Serie A, and 377 Ligue 1 matches. Its 2015/16 Bundesliga set contains 34
matches. However, only the Premier League 2015/16 matches overlap our bundled
history as a complete season. The other recent overlaps are fragments, while
Serie A's StatsBomb records predate the project's Serie A history, which begins
in 2018/19. Greece and Portugal have no matching StatsBomb competition data.

The match catalog reports event availability, but we did not download and
validate shot-level xG completeness for every overlap. A schema spot-check of
StatsBomb match `3825739` found 3,947 events, including 26 shots with
`statsbomb_xg` values. That confirms the field exists; it does not establish
full-archive completeness.

## Why there is no xG model score table

A single complete overlapping Premier League season would leave only a small
late-season holdout after building prior-match xG features. The other leagues
have too few matches and too few contiguous seasons to tune or validate xG
features chronologically. Pooling those fragments would mix different leagues,
eras, and coverage patterns and could make the added feature look better or
worse for reasons unrelated to xG.

We therefore did **not** train an xG candidate, compute an xG performance delta,
or propose adding StatsBomb data to the production model. Reporting a score from
this coverage would imply stronger evidence than the data supports. The
existing production model remains unchanged.

## Reproduction

The audit reads the official [Hudl StatsBomb Open Data repository](https://github.com/hudl/open-data)
and the bundled `data/model/historical_matches.csv.gz`. It uses the project's
league-specific aliases, exact match date and home/away order, then verifies
the final score. It makes no Goal API or Odds API requests and stores no raw
StatsBomb match/event files in this repository.

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/hudl/open-data.git /tmp/statsbomb-open-data
cd /tmp/statsbomb-open-data
git sparse-checkout set data/competitions.json data/matches
cd -
PYTHONPATH=src python experiments/statsbomb_coverage.py --statsbomb-root /tmp/statsbomb-open-data --output data/research/statsbomb_open_data_coverage.csv
```

StatsBomb asks people who publish analysis based on Open Data to credit
StatsBomb and use its logo. Check its current terms before distributing data or
derived match-level xG in a public product.

## What would make the next xG test worthwhile

We need a legal source with consistent match-level xG for multiple consecutive
seasons in the leagues we want to evaluate. Then the experiment can build
pre-match rolling xG/xGA using completed earlier matches only, compare the
production baseline and production-plus-xG on the same future matches, and
report log loss, Brier score, calibration, coverage, and uncertainty. A provider
trial or paid feed should be evaluated against that requirement before adding
another integration.
