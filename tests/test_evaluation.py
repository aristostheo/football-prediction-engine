import pandas as pd
import pytest

from football_predictor.evaluation import (
    add_elo_probabilities,
    chronological_holdout,
    evaluate_probabilities,
    expected_calibration_error,
)


def test_elo_probabilities_are_normalized_and_evaluable() -> None:
    matches = pd.DataFrame(
        {
            "result": ["H", "D", "A"],
            "home_elo": [1500.0, 1500.0, 1450.0],
            "away_elo": [1500.0, 1500.0, 1550.0],
        }
    )
    probabilities = add_elo_probabilities(matches)

    total_probabilities = probabilities[["p_home_win", "p_draw", "p_away_win"]].sum(axis=1)
    assert (total_probabilities - 1).abs().max() < 1e-12
    metrics = evaluate_probabilities(probabilities)
    assert metrics.matches == 3
    assert 0 <= metrics.accuracy <= 1
    assert metrics.log_loss > 0
    assert metrics.brier_score > 0
    assert 0 <= metrics.ranked_probability_score <= 1


def test_ranked_probability_score_is_zero_for_perfect_probabilities() -> None:
    probabilities = pd.DataFrame(
        {
            "result": ["H", "D", "A"],
            "p_home_win": [0.999, 0.0005, 0.0005],
            "p_draw": [0.0005, 0.999, 0.0005],
            "p_away_win": [0.0005, 0.0005, 0.999],
        }
    )
    assert evaluate_probabilities(probabilities).ranked_probability_score == pytest.approx(
        0, abs=1e-6
    )


def test_chronological_holdout_uses_the_latest_rows_per_competition() -> None:
    matches = pd.DataFrame(
        {
            "competition": ["premier_league"] * 5 + ["super_league_greece"] * 5,
            "match_date": [
                "2024-08-01",
                "2024-08-08",
                "2024-08-15",
                "2024-08-22",
                "2024-08-29",
            ]
            * 2,
        }
    )

    holdout = chronological_holdout(matches, test_fraction=0.4)

    assert holdout.groupby("competition").size().to_dict() == {
        "premier_league": 2,
        "super_league_greece": 2,
    }
    assert set(holdout["match_date"]) == {"2024-08-22", "2024-08-29"}


def test_evaluation_rejects_invalid_probability_rows() -> None:
    matches = pd.DataFrame(
        {"result": ["H"], "p_home_win": [0.9], "p_draw": [0.2], "p_away_win": [-0.1]}
    )

    with pytest.raises(ValueError, match="strictly"):
        evaluate_probabilities(matches)


def test_expected_calibration_error_returns_each_outcome() -> None:
    matches = pd.DataFrame(
        {
            "result": ["H", "D", "A"],
            "p_home_win": [0.6, 0.2, 0.2],
            "p_draw": [0.2, 0.6, 0.2],
            "p_away_win": [0.2, 0.2, 0.6],
        }
    )

    errors = expected_calibration_error(matches, bins=3)

    assert set(errors) == {"H", "D", "A"}
    assert all(error >= 0 for error in errors.values())
