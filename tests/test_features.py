from math import isnan

import pandas as pd
import pytest

from football_predictor.features import FeatureConfig, build_pre_match_features


def _matches() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_date": "2024-08-10",
                "competition": "premier_league",
                "season": "2024-25",
                "home_team": "Alpha",
                "away_team": "Bravo",
                "home_goals": 2,
                "away_goals": 0,
                "result": "H",
            },
            {
                "match_date": "2024-08-10",
                "competition": "premier_league",
                "season": "2024-25",
                "home_team": "Charlie",
                "away_team": "Delta",
                "home_goals": 0,
                "away_goals": 1,
                "result": "A",
            },
            {
                "match_date": "2024-08-17",
                "competition": "premier_league",
                "season": "2024-25",
                "home_team": "Alpha",
                "away_team": "Charlie",
                "home_goals": 1,
                "away_goals": 1,
                "result": "D",
            },
        ]
    )


def test_features_use_only_results_before_the_match_date() -> None:
    features = build_pre_match_features(_matches(), config=FeatureConfig(elo_k_factor=20.0))

    first_day = features.iloc[:2]
    assert first_day["home_matches_played"].tolist() == [0.0, 0.0]
    assert first_day["away_matches_played"].tolist() == [0.0, 0.0]
    assert first_day["home_elo"].tolist() == [1500.0, 1500.0]
    assert first_day["away_elo"].tolist() == [1500.0, 1500.0]

    second_day = features.iloc[2]
    assert second_day["home_form_points_per_match"] == 3.0
    assert second_day["away_form_points_per_match"] == 0.0
    assert second_day["home_days_since_last_match"] == 7.0
    assert second_day["away_days_since_last_match"] == 7.0
    assert second_day["home_elo"] > 1500.0
    assert second_day["away_elo"] < 1500.0
    assert isnan(first_day.iloc[0]["home_days_since_last_match"])


def test_features_reject_duplicate_same_day_team_appearances() -> None:
    matches = _matches()
    matches.loc[1, "home_team"] = "Alpha"

    with pytest.raises(ValueError, match="more than once"):
        build_pre_match_features(matches)


def test_rest_days_are_capped_to_the_training_range() -> None:
    matches = _matches()
    matches.loc[2, "match_date"] = "2026-10-01"
    features = build_pre_match_features(matches)
    assert features.iloc[2]["home_days_since_last_match"] == 97.0
    assert features.iloc[2]["away_days_since_last_match"] == 97.0
    assert features.iloc[2]["home_matches_played"] == 0.0
    assert features.iloc[2]["home_form_points_per_match"] == 0.0
    assert abs(features.iloc[2]["home_elo"] - 1500.0) < 3.0


def test_changing_a_result_cannot_change_same_day_features() -> None:
    original = _matches()
    changed = original.copy()
    changed.loc[0, ["home_goals", "away_goals", "result"]] = [0, 3, "A"]

    baseline_features = build_pre_match_features(original)
    changed_features = build_pre_match_features(changed)
    feature_columns = [column for column in baseline_features if column not in original.columns]

    pd.testing.assert_frame_equal(
        baseline_features.loc[:1, feature_columns],
        changed_features.loc[:1, feature_columns],
    )
    assert baseline_features.loc[2, "home_elo"] != changed_features.loc[2, "home_elo"]
