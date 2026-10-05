"""Nested walk-forward experiment for head-to-head probability inputs.

Run from the repository root:
    PYTHONPATH=src python experiments/h2h_walk_forward.py

The candidate H2H estimate compares longer meeting windows and calendar-time
recency weights. All meetings on the forecast date are excluded. H2H variants
and blend weights are selected from earlier complete-season folds only.
"""
from __future__ import annotations

import argparse
import json
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
from random import Random

import pandas as pd

from football_predictor.evaluation import add_elo_probabilities
from football_predictor.features import build_pre_match_features
from football_predictor.models import (
    _complete_season_order,
    _fit_predict_poisson,
    _per_match_log_loss,
    blend_probabilities,
)

PROBABILITY_COLUMNS = ("p_home_win", "p_draw", "p_away_win")
BLEND_WEIGHTS = (0.0, 0.05, 0.10, 0.20, 0.30, 0.50)
HISTORY_WINDOWS = ("last5", "last10", "last20", "all")
DECAY_HALF_LIVES_YEARS = (2, 5, 10)
PRIOR_STRENGTH = 6.0


def _baseline(competition: str, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    elo = add_elo_probabilities(test)
    if competition == "premier_league":
        poisson = _fit_predict_poisson(train, test)
        return blend_probabilities(elo, poisson, elo_weight=0.25)
    return elo


def _meeting_index(
    matches: pd.DataFrame,
) -> dict[tuple[str, tuple[str, str]], list[tuple[pd.Timestamp, str, str]]]:
    index: dict[tuple[str, tuple[str, str]], list[tuple[pd.Timestamp, str, str]]] = (
        defaultdict(list)
    )
    for row in matches.itertuples(index=False):
        teams = tuple(sorted((str(row.home_team), str(row.away_team))))
        index[(str(row.competition), teams)].append(
            (row.match_date, str(row.home_team), str(row.result))
        )
    for meetings in index.values():
        meetings.sort(key=lambda item: item[0])
    return dict(index)


def _h2h_posteriors(
    competition: str,
    test: pd.DataFrame,
    baseline: pd.DataFrame,
    index: dict[tuple[str, tuple[str, str]], list[tuple[pd.Timestamp, str, str]]],
) -> dict[str, pd.DataFrame]:
    specs = [
        *HISTORY_WINDOWS,
        *(f"decay{half_life}y" for half_life in DECAY_HALF_LIVES_YEARS),
    ]
    rows: dict[str, list[list[float]]] = {spec: [] for spec in specs}

    for match, base in zip(
        test.itertuples(index=False), baseline.itertuples(index=False), strict=True
    ):
        teams = tuple(sorted((str(match.home_team), str(match.away_team))))
        meetings = index.get((competition, teams), [])
        meeting_dates = [meeting[0] for meeting in meetings]
        cutoff = bisect_left(meeting_dates, match.match_date)
        prior_meetings = meetings[:cutoff]
        prior = [float(getattr(base, column)) for column in PROBABILITY_COLUMNS]

        for spec in specs:
            if spec.startswith("last"):
                selected = prior_meetings[-int(spec[4:]) :]
                weights = [1.0] * len(selected)
            elif spec == "all":
                selected = prior_meetings
                weights = [1.0] * len(selected)
            else:
                half_life_years = int(spec[5:-1])
                selected = prior_meetings
                weights = [
                    0.5 ** ((match.match_date - meeting[0]).days / (365.25 * half_life_years))
                    for meeting in selected
                ]

            counts = [0.0, 0.0, 0.0]
            for meeting, weight in zip(selected, weights, strict=True):
                _, historical_home, result = meeting
                if result == "D":
                    counts[1] += weight
                elif (result == "H" and historical_home == match.home_team) or (
                    result == "A" and historical_home != match.home_team
                ):
                    counts[0] += weight
                else:
                    counts[2] += weight

            denominator = PRIOR_STRENGTH + sum(weights)
            rows[spec].append(
                [
                    (PRIOR_STRENGTH * prior[outcome] + counts[outcome]) / denominator
                    for outcome in range(3)
                ]
            )

    return {
        spec: pd.DataFrame(
            values, index=test.index, columns=PROBABILITY_COLUMNS
        )
        for spec, values in rows.items()
    }


def _blend_h2h(
    baseline: pd.DataFrame, posterior: pd.DataFrame, weight: float
) -> pd.DataFrame:
    forecast = baseline.copy()
    for column in PROBABILITY_COLUMNS:
        forecast[column] = (
            (1 - weight) * baseline[column].to_numpy()
            + weight * posterior[column].to_numpy()
        )
    return forecast


def _log_loss(forecasts: pd.DataFrame) -> float:
    return sum(_per_match_log_loss(forecasts)) / len(forecasts)


def compare(
    matches: pd.DataFrame,
    *,
    max_test_seasons: int = 10,
    bootstrap_samples: int = 10_000,
    recency_only: bool = False,
) -> dict[str, dict[str, object]]:
    raw = matches.copy()
    raw["match_date"] = pd.to_datetime(raw["match_date"], format="ISO8601")
    features = build_pre_match_features(raw)
    h2h_index = _meeting_index(raw)
    output: dict[str, dict[str, object]] = {}

    for competition, league in features.groupby("competition", sort=True):
        league = league.sort_values("match_date").reset_index(drop=True)
        seasons = _complete_season_order(league)[-max_test_seasons:]
        folds: dict[str, tuple[pd.DataFrame, dict[str, pd.DataFrame]]] = {}

        for season in seasons:
            test = league[league["season"] == season].copy()
            train = league[league["match_date"] < test["match_date"].min()].copy()
            if len(train) < 200:
                continue
            baseline = _baseline(str(competition), train, test)
            posteriors = _h2h_posteriors(str(competition), test, baseline, h2h_index)
            if recency_only:
                posteriors = {
                    name: posterior
                    for name, posterior in posteriors.items()
                    if name.startswith("decay")
                }
            baseline["result"] = test["result"].to_numpy()
            for posterior in posteriors.values():
                posterior["result"] = test["result"].to_numpy()
            folds[str(season)] = (baseline, posteriors)

        tested_seasons = list(folds)
        if not tested_seasons:
            continue

        selected_by_season: dict[str, dict[str, float | str]] = {}
        baseline_parts: list[pd.DataFrame] = []
        candidate_parts: list[pd.DataFrame] = []
        season_differences: list[float] = []
        season_results: list[dict[str, object]] = []

        for position, season in enumerate(tested_seasons):
            baseline, posteriors = folds[season]
            if position == 0:
                spec, weight = "none", 0.0
            else:
                earlier_baselines = pd.concat(
                    [folds[prior][0] for prior in tested_seasons[:position]],
                    ignore_index=True,
                )
                earlier_posteriors = {
                    name: pd.concat(
                        [folds[prior][1][name] for prior in tested_seasons[:position]],
                        ignore_index=True,
                    )
                    for name in posteriors
                }
                best = (_log_loss(earlier_baselines), "none", 0.0)
                for name, posterior in earlier_posteriors.items():
                    for candidate_weight in BLEND_WEIGHTS[1:]:
                        candidate_score = _log_loss(
                            _blend_h2h(earlier_baselines, posterior, candidate_weight)
                        )
                        candidate = (candidate_score, name, candidate_weight)
                        if candidate < best:
                            best = candidate
                _, spec, weight = best

            selected_by_season[season] = {"history": spec, "weight": weight}
            candidate = (
                baseline.copy()
                if spec == "none"
                else _blend_h2h(baseline, posteriors[spec], weight)
            )
            candidate["result"] = baseline["result"].to_numpy()
            baseline_parts.append(baseline)
            candidate_parts.append(candidate)
            baseline_season_loss = _log_loss(baseline)
            candidate_season_loss = _log_loss(candidate)
            difference = candidate_season_loss - baseline_season_loss
            season_differences.append(difference)
            season_results.append(
                {
                    "season": season,
                    "baseline_log_loss": baseline_season_loss,
                    "recency_h2h_log_loss": candidate_season_loss,
                    "difference": difference,
                    "selected_history": spec,
                    "selected_weight": weight,
                }
            )

        baseline_all = pd.concat(baseline_parts, ignore_index=True)
        candidate_all = pd.concat(candidate_parts, ignore_index=True)
        rng = Random(42)
        bootstrapped = sorted(
            sum(rng.choice(season_differences) for _ in season_differences)
            / len(season_differences)
            for _ in range(bootstrap_samples)
        )
        low_index = int((bootstrap_samples - 1) * 0.025)
        high_index = int((bootstrap_samples - 1) * 0.975)
        baseline_loss = _log_loss(baseline_all)
        candidate_loss = _log_loss(candidate_all)
        output[str(competition)] = {
            "candidate_set": "recency-weighted only" if recency_only else "all history options",
            "test_seasons": tested_seasons,
            "matches": len(baseline_all),
            "baseline_log_loss": baseline_loss,
            "recency_h2h_log_loss": candidate_loss,
            "h2h_minus_baseline_log_loss": candidate_loss - baseline_loss,
            "paired_season_block_95_interval": [
                bootstrapped[low_index],
                bootstrapped[high_index],
            ],
            "selected_h2h_by_season": selected_by_season,
            "season_results": season_results,
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("data/model/historical_matches.csv.gz")
    )
    parser.add_argument("--max-test-seasons", type=int, default=10)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument(
        "--recency-only",
        action="store_true",
        help="select only among 2-, 5-, or 10-year recency half-lives",
    )
    args = parser.parse_args()
    if args.max_test_seasons < 1 or args.bootstrap_samples < 1:
        parser.error("season and bootstrap counts must be positive")
    matches = pd.read_csv(args.input)
    result = compare(
        matches,
        max_test_seasons=args.max_test_seasons,
        bootstrap_samples=args.bootstrap_samples,
        recency_only=args.recency_only,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
