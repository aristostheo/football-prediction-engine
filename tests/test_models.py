import pandas as pd

from football_predictor.models import FEATURE_COLUMNS, compare_models_chronologically


def test_model_comparison_trains_on_past_rows_and_scores_future_rows() -> None:
    rows = []
    outcomes = ("H", "D", "A")
    for index in range(90):
        result = outcomes[index % len(outcomes)]
        row = {
            "competition": "premier_league",
            "match_date": pd.Timestamp("2020-01-01") + pd.DateOffset(days=index),
            "result": result,
        }
        for feature_index, feature in enumerate(FEATURE_COLUMNS):
            row[feature] = float(index + feature_index)
        rows.append(row)

    comparison = compare_models_chronologically(pd.DataFrame(rows), test_fraction=0.2)

    premier_league = comparison["premier_league"]
    assert premier_league.train_matches == 72
    assert premier_league.test_matches == 18
    assert premier_league.calibrated_logistic_regression.metrics.matches == 18
    assert set(premier_league.elo_baseline.calibration_error) == {"H", "D", "A"}
