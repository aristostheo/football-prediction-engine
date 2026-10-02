from datetime import date, timedelta
from math import isfinite

import pandas as pd
import pytest

from football_predictor.models import (
    FEATURE_COLUMNS,
    _complete_season_order,
    _outcome_probabilities_from_goal_rates,
    _season_block_log_loss_intervals,
    blend_probabilities,
    compare_models_chronologically,
)


def test_walk_forward_folds_include_only_schedule_complete_seasons() -> None:
    teams = [f"Team {index}" for index in range(20)]
    rows = []
    current_date = date(2024, 8, 1)
    for first in range(len(teams)):
        for second in range(first + 1, len(teams)):
            for home, away in ((teams[first], teams[second]), (teams[second], teams[first])):
                rows.append(
                    {
                        "competition": "premier_league",
                        "season": "2024-25",
                        "match_date": current_date,
                        "home_team": home,
                        "away_team": away,
                    }
                )
                current_date += timedelta(days=1)
    rows.extend(
        [
            {
                "competition": "premier_league",
                "season": "2025-26",
                "match_date": current_date,
                "home_team": "Team 0",
                "away_team": "Team 1",
            }
        ]
    )

    assert _complete_season_order(pd.DataFrame(rows)) == ["2024-25"]


def test_walk_forward_paired_bootstrap_is_repeatable_and_ordered() -> None:
    def probabilities(home_probability: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "result": ["H", "A"],
                "p_home_win": [home_probability, 1 - home_probability],
                "p_draw": [0.1, 0.1],
                "p_away_win": [0.9 - home_probability, home_probability - 0.1],
            }
        )

    folds = {
        "2024-25": {"elo": probabilities(0.7), "climatology": probabilities(0.5)},
        "2025-26": {"elo": probabilities(0.7), "climatology": probabilities(0.5)},
    }
    first = _season_block_log_loss_intervals(folds, bootstrap_samples=100, random_seed=17)
    second = _season_block_log_loss_intervals(folds, bootstrap_samples=100, random_seed=17)

    assert first == second
    interval = first["climatology - elo"]
    assert interval["lower_95"] <= interval["mean_difference"] <= interval["upper_95"]


def test_poisson_scoreline_probabilities_are_normalized() -> None:
    probabilities = _outcome_probabilities_from_goal_rates(2.1, 0.7)

    assert abs(sum(probabilities.values()) - 1) < 1e-12
    assert probabilities["p_home_win"] > probabilities["p_away_win"]


def test_probability_blend_is_normalized() -> None:
    elo = pd.DataFrame(
        {"p_home_win": [0.5], "p_draw": [0.3], "p_away_win": [0.2], "result": ["H"]}
    )
    poisson = pd.DataFrame(
        {"p_home_win": [0.7], "p_draw": [0.2], "p_away_win": [0.1], "result": ["H"]}
    )

    blended = blend_probabilities(elo, poisson, elo_weight=0.25)

    assert blended["p_home_win"].iloc[0] == pytest.approx(0.65)
    assert abs(blended[["p_home_win", "p_draw", "p_away_win"]].iloc[0].sum() - 1) < 1e-12


def test_model_comparison_trains_on_past_rows_and_scores_future_rows() -> None:
    rows = []
    outcomes = ("H", "D", "A")
    for index in range(90):
        result = outcomes[index % len(outcomes)]
        row = {
            "competition": "premier_league",
            "match_date": pd.Timestamp("2020-01-01") + pd.DateOffset(days=index),
            "result": result,
            "home_goals": (index + 1) % 4,
            "away_goals": index % 3,
        }
        for feature_index, feature in enumerate(FEATURE_COLUMNS):
            row[feature] = float(index + feature_index)
        rows.append(row)

    comparison = compare_models_chronologically(pd.DataFrame(rows), test_fraction=0.2)

    premier_league = comparison["premier_league"]
    assert premier_league.train_matches == 72
    assert premier_league.test_matches == 18
    assert premier_league.calibrated_logistic_regression.metrics.matches == 18
    assert premier_league.poisson_goal_model.metrics.matches == 18
    assert isfinite(premier_league.poisson_goal_model.metrics.log_loss)
    ensemble = premier_league.validation_selected_elo_poisson_ensemble
    assert ensemble.elo_weight in {0.0, 0.25, 0.5, 0.75, 1.0}
    assert ensemble.test_score.metrics.matches == 18
    assert set(premier_league.elo_baseline.calibration_error) == {"H", "D", "A"}
