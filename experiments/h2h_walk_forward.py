"""Nested walk-forward experiment: does recent head-to-head history help W/D/L?

Run from the repository root:
    PYTHONPATH=src python experiments/h2h_walk_forward.py
The H2H posterior uses only the previous five meetings strictly before kickoff,
is shrunk toward each match's existing model probabilities, and its blend weight
is selected only from earlier complete-season folds.
"""
from __future__ import annotations

import json
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
H2H_BLEND_CANDIDATES = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40)
H2H_PRIOR_STRENGTH = 6.0


def _baseline(competition: str, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    elo = add_elo_probabilities(test)
    if competition == "premier_league":
        poisson = _fit_predict_poisson(train, test)
        return blend_probabilities(elo, poisson, elo_weight=0.25)
    return elo


def _h2h_posterior(
    history: pd.DataFrame, test: pd.DataFrame, baseline: pd.DataFrame
) -> pd.DataFrame:
    posterior_rows: list[list[float]] = []
    for match, base in zip(
        test.itertuples(index=False), baseline.itertuples(index=False), strict=True
    ):
        meetings = history[
            (history["match_date"] < match.match_date)
            & (
                (
                    (history["home_team"] == match.home_team)
                    & (history["away_team"] == match.away_team)
                )
                | (
                    (history["home_team"] == match.away_team)
                    & (history["away_team"] == match.home_team)
                )
            )
        ].sort_values("match_date").tail(5)

        counts = [0, 0, 0]
        for meeting in meetings.itertuples(index=False):
            if meeting.result == "D":
                counts[1] += 1
            elif meeting.home_team == match.home_team:
                counts[0] += 1
            else:
                counts[2] += 1

        prior = [float(getattr(base, column)) for column in PROBABILITY_COLUMNS]
        denominator = H2H_PRIOR_STRENGTH + len(meetings)
        posterior_rows.append(
            [
                (H2H_PRIOR_STRENGTH * prior[index] + counts[index]) / denominator
                for index in range(3)
            ]
        )
    return pd.DataFrame(posterior_rows, index=test.index, columns=PROBABILITY_COLUMNS)


def _blend_h2h(
    baseline: pd.DataFrame, posterior: pd.DataFrame, h2h_weight: float
) -> pd.DataFrame:
    forecast = baseline.copy()
    for column in PROBABILITY_COLUMNS:
        forecast[column] = (
            (1 - h2h_weight) * baseline[column].to_numpy()
            + h2h_weight * posterior[column].to_numpy()
        )
    return forecast


def _log_loss(forecasts: pd.DataFrame) -> float:
    return sum(_per_match_log_loss(forecasts)) / len(forecasts)


def compare(
    matches: pd.DataFrame, *, max_test_seasons: int = 5, bootstrap_samples: int = 10_000
) -> dict[str, dict[str, object]]:
    raw = matches.copy()
    raw["match_date"] = pd.to_datetime(raw["match_date"], format="ISO8601")
    features = build_pre_match_features(raw)
    output: dict[str, dict[str, object]] = {}

    for competition, league in features.groupby("competition", sort=True):
        history = raw[raw["competition"] == competition].copy()
        league = league.sort_values("match_date").reset_index(drop=True)
        seasons = _complete_season_order(league)[-max_test_seasons:]

        folds: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
        for season in seasons:
            test = league[league["season"] == season].copy()
            train = league[league["match_date"] < test["match_date"].min()].copy()
            if len(train) < 200:
                continue
            baseline = _baseline(str(competition), train, test)
            posterior = _h2h_posterior(history, test, baseline)
            baseline["result"] = test["result"].to_numpy()
            posterior["result"] = test["result"].to_numpy()
            folds[str(season)] = (baseline, posterior)

        tested_seasons = list(folds)
        baseline_parts: list[pd.DataFrame] = []
        h2h_parts: list[pd.DataFrame] = []
        season_differences: list[float] = []
        selected_weights: dict[str, float] = {}

        for index, season in enumerate(tested_seasons):
            baseline, posterior = folds[season]
            if index == 0:
                weight = 0.0
            else:
                earlier_baselines = pd.concat(
                    [folds[prior][0] for prior in tested_seasons[:index]], ignore_index=True
                )
                earlier_posteriors = pd.concat(
                    [folds[prior][1] for prior in tested_seasons[:index]], ignore_index=True
                )
                weight = min(
                    (
                        _log_loss(_blend_h2h(earlier_baselines, earlier_posteriors, candidate)),
                        candidate,
                    )
                    for candidate in H2H_BLEND_CANDIDATES
                )[1]

            selected_weights[season] = weight
            candidate = _blend_h2h(baseline, posterior, weight)
            candidate["result"] = baseline["result"].to_numpy()
            baseline_parts.append(baseline)
            h2h_parts.append(candidate)
            season_differences.append(_log_loss(candidate) - _log_loss(baseline))

        if not tested_seasons:
            continue
        baseline_all = pd.concat(baseline_parts, ignore_index=True)
        h2h_all = pd.concat(h2h_parts, ignore_index=True)
        rng = Random(42)
        bootstrapped = sorted(
            sum(rng.choice(season_differences) for _ in season_differences)
            / len(season_differences)
            for _ in range(bootstrap_samples)
        )
        low_index = int((bootstrap_samples - 1) * 0.025)
        high_index = int((bootstrap_samples - 1) * 0.975)
        output[str(competition)] = {
            "test_seasons": tested_seasons,
            "matches": len(baseline_all),
            "baseline_log_loss": _log_loss(baseline_all),
            "h2h_log_loss": _log_loss(h2h_all),
            "h2h_minus_baseline_log_loss": _log_loss(h2h_all) - _log_loss(baseline_all),
            "paired_season_block_95_interval": [
                bootstrapped[low_index],
                bootstrapped[high_index],
            ],
            "selected_h2h_weight_by_season": selected_weights,
        }
    return output


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("data/model/historical_matches.csv.gz")
    )
    parser.add_argument("--max-test-seasons", type=int, default=5)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    args = parser.parse_args()
    if args.max_test_seasons < 1 or args.bootstrap_samples < 1:
        parser.error("season and bootstrap counts must be positive")
    matches = pd.read_csv(args.input)
    print(
        json.dumps(
            compare(
                matches,
                max_test_seasons=args.max_test_seasons,
                bootstrap_samples=args.bootstrap_samples,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
