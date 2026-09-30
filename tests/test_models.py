from math import isfinite

import pandas as pd

from football_predictor.models import (
    FEATURE_COLUMNS,
    _outcome_probabilities_from_goal_rates,
    compare_models_chronologically,
)


def test_poisson_scoreline_probabilities_are_normalized() -> None:
    probabilities = _outcome_probabilities_from_goal_rates(2.1, 0.7)

    assert abs(sum(probabilities.values()) - 1) < 1e-12
    assert probabilities["p_home_win"] > probabilities["p_away_win"]


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
    assert set(premier_league.elo_baseline.calibration_error) == {"H", "D", "A"}
