from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from football_predictor.betting import ScoreDistribution, initial_selections
from football_predictor.betting_benchmark import (
    binary_metrics,
    forecast_fold,
    paired_season_interval,
    prepare_serving_features,
    season_folds,
    summarize,
)
from football_predictor.domain import Competition
from football_predictor.features import build_pre_match_features
from football_predictor.prediction import FixtureToPredict, PredictionEngine


@pytest.fixture(scope="module")
def replay():
    raw = pd.read_csv(Path(__file__).parents[1] / "data/model/historical_matches.csv.gz")
    raw = raw[(raw.competition == "premier_league") & (raw.season == "2024-25")]
    features = build_pre_match_features(raw)
    dates = sorted(features.match_date.unique())
    cutoff = dates[35]
    train = features[features.match_date < cutoff].copy()
    test = features[features.match_date.isin(dates[35:38])].copy()
    prediction = forecast_fold("premier_league", train, test)
    return raw, train, test, prediction


def test_research_first_day_matches_the_actual_serving_engine(replay):
    raw, train, test, forecast = replay
    engine = PredictionEngine(raw[pd.to_datetime(raw.match_date) < test.match_date.min()])
    # Only first-day fixtures: later forecasts deliberately use frozen season
    # coefficients, whereas a restarted serving engine would refit the model.
    for match in forecast[forecast.match_date == forecast.match_date.min()].itertuples():
        prediction = engine.predict(
            FixtureToPredict(
                Competition.PREMIER_LEAGUE,
                match.match_date.date(),
                match.home_team,
                match.away_team,
            )
        )
        assert match.home_rate == pytest.approx(prediction.components.scoreline_home_goal_rate)
        assert match.away_rate == pytest.approx(prediction.components.scoreline_away_goal_rate)
        assert (
            match.production_p_home_win,
            match.production_p_draw,
            match.production_p_away_win,
        ) == pytest.approx(prediction.model_probabilities)


def test_vectorized_research_markets_match_public_arithmetic(replay):
    _, _, _, forecast = replay
    row = forecast.iloc[0]
    raw = ScoreDistribution.poisson(row.home_rate, row.away_rate)
    aligned = raw.align_results(
        tuple(row[f"production_{column}"] for column in ("p_home_win", "p_draw", "p_away_win"))
    )
    for name, selection in initial_selections().items():
        for model, grid in (("goal_raw", raw), ("goal_aligned", aligned)):
            estimate = grid.estimate(selection)
            assert row[f"{name}__{model}"] == pytest.approx(estimate.conditional_win)
            assert row[f"{name}__{model}__push"] == pytest.approx(estimate.push)


def test_non_premier_league_replay_matches_serving_elo_and_goal_components():
    raw = pd.read_csv(Path(__file__).parents[1] / "data/model/historical_matches.csv.gz")
    raw = raw[(raw.competition == "super_league_greece") & (raw.season == "2024-25")]
    features = build_pre_match_features(raw)
    cutoff = sorted(features.match_date.unique())[30]
    train, test = features[features.match_date < cutoff], features[features.match_date == cutoff]
    forecast = forecast_fold("super_league_greece", train, test)
    engine = PredictionEngine(raw[pd.to_datetime(raw.match_date) < cutoff])
    for match in forecast.itertuples():
        predicted = engine.predict(
            FixtureToPredict(
                Competition.SUPER_LEAGUE_GREECE,
                match.match_date.date(),
                match.home_team,
                match.away_team,
            )
        )
        assert (
            match.production_p_home_win,
            match.production_p_draw,
            match.production_p_away_win,
        ) == pytest.approx(predicted.model_probabilities)
        assert match.home_rate == pytest.approx(predicted.components.scoreline_home_goal_rate)


def test_first_appearance_prior_does_not_change_known_or_gap_reset_teams(replay):
    _, train, test, _ = replay
    test = test.iloc[:2].copy()
    test.loc[test.index[0], "home_team"] = "Unseen club"
    test.loc[test.index[0], "home_days_since_last_match"] = np.nan
    test.loc[test.index[0], "home_matches_played"] = 0
    test.loc[test.index[1], "home_days_since_last_match"] = 97
    test.loc[test.index[1], "home_matches_played"] = 0
    prepared, unknown = prepare_serving_features(train, test)
    assert list(unknown) == [True, False]
    assert prepared.home_elo.iloc[0] == 1400
    assert prepared.home_elo.iloc[1] == test.home_elo.iloc[1]
    assert test.home_elo.iloc[0] != 1400


def test_heldout_results_do_not_influence_fitting_or_same_day_features(replay):
    raw, train, test, forecast = replay
    changed = raw.copy()
    cutoff = test.match_date.min()
    mask = pd.to_datetime(changed.match_date) == cutoff
    changed.loc[mask, ["home_goals", "away_goals", "result"]] = [7, 0, "H"]
    features = build_pre_match_features(changed)
    numeric = list(prepare_serving_features(train, test)[0].select_dtypes("number").columns)
    # Labels are allowed to change, pre-match features are not.
    numeric = [c for c in numeric if c not in {"home_goals", "away_goals"}]
    earlier = features[features.match_date <= cutoff]
    original = build_pre_match_features(raw)
    pd.testing.assert_frame_equal(
        earlier[numeric], original[original.match_date <= cutoff][numeric]
    )
    altered_test = features[features.match_date == cutoff]
    altered = forecast_fold("premier_league", train, altered_test)
    probability_columns = [
        c for c in forecast.columns if c.endswith(("__goal_raw", "__goal_aligned"))
    ]
    pd.testing.assert_frame_equal(
        altered[probability_columns],
        forecast[forecast.match_date == cutoff][probability_columns].reset_index(drop=True),
    )
    with pytest.raises(ValueError, match="strictly precede"):
        forecast_fold("premier_league", test, train)


def test_binary_calibration_has_no_overlapping_or_missing_boundary_values():
    probabilities = np.linspace(0, 1, 11)
    actual = (probabilities >= 0.5).astype(float)
    result = binary_metrics(probabilities, actual)
    assert sum(bucket["n"] for bucket in result["calibration"]) == 11
    assert result["accuracy"] == 1
    assert result["brier"] >= 0
    with pytest.raises(ValueError):
        binary_metrics(np.array([float("nan")]), np.array([1]))
    assert paired_season_interval(pd.DataFrame({"season": []}), np.array([]))["delta"] is None


def test_refunds_are_excluded_from_binary_metrics_and_reported(replay):
    forecast = replay[3]
    summary = summarize(forecast)
    pushes = (forecast["dnb_home__actual"] == "push").sum()
    assert summary["markets"]["dnb_home"]["pushes"] == pushes
    assert summary["markets"]["dnb_home"]["goal_aligned"]["matches"] == len(forecast) - pushes
    assert summary["goal_aligned_1x2"] == pytest.approx(summary["production_1x2"])
    assert summary["scorelines"]["goal_raw"]["scored_matches"] == len(forecast)
    interval = paired_season_interval(forecast, np.zeros(len(forecast)))
    assert interval == {"delta": 0, "lower_95": 0, "upper_95": 0, "season_blocks": 1}


def test_folds_are_complete_and_train_dates_strictly_precede_tests():
    raw = pd.read_csv(Path(__file__).parents[1] / "data/model/historical_matches.csv.gz")
    raw.match_date = pd.to_datetime(raw.match_date)
    folds = list(season_folds(raw))
    assert len({competition for competition, _, _, _ in folds}) == 7
    assert len(folds) >= 30
    for competition, _, train, test in folds:
        assert train.match_date.max() < test.match_date.min()
        assert "2019-20" not in set(test.season)
        assert test.season.nunique() == 1
        if competition == "premier_league":
            assert len(test) == 380
        if competition == "super_league_greece":
            assert len(test) == 182
    assert sum(len(test) for _, _, _, test in folds) > 10000
