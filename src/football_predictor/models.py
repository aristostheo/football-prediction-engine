"""Time-aware calibrated statistical model comparison."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from football_predictor.domain import MatchResult
from football_predictor.evaluation import (
    EvaluationMetrics,
    add_elo_probabilities,
    evaluate_probabilities,
    expected_calibration_error,
)

FEATURE_COLUMNS = (
    "home_matches_played",
    "away_matches_played",
    "home_form_points_per_match",
    "away_form_points_per_match",
    "home_form_goals_for_per_match",
    "away_form_goals_for_per_match",
    "home_form_goals_against_per_match",
    "away_form_goals_against_per_match",
    "home_home_points_per_match",
    "away_away_points_per_match",
    "home_days_since_last_match",
    "away_days_since_last_match",
    "home_elo",
    "away_elo",
    "elo_difference",
)


@dataclass(frozen=True)
class ModelScore:
    metrics: EvaluationMetrics
    calibration_error: dict[str, float]


@dataclass(frozen=True)
class LeagueModelComparison:
    train_matches: int
    test_matches: int
    elo_baseline: ModelScore
    calibrated_logistic_regression: ModelScore
    poisson_goal_model: ModelScore


def compare_models_chronologically(
    features: pd.DataFrame, *, test_fraction: float = 0.2
) -> dict[str, LeagueModelComparison]:
    """Compare Elo and calibrated logistic regression using each league's future holdout."""
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between zero and one")
    required = {
        "competition",
        "match_date",
        "result",
        "home_goals",
        "away_goals",
        *FEATURE_COLUMNS,
    }
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"missing model columns: {sorted(missing)}")

    comparisons: dict[str, LeagueModelComparison] = {}
    for competition, league_features in features.groupby("competition", sort=True):
        ordered = league_features.sort_values("match_date", kind="stable").reset_index(drop=True)
        split_at = int(len(ordered) * (1 - test_fraction))
        train = ordered.iloc[:split_at]
        test = ordered.iloc[split_at:]
        if len(train) < 40 or len(test) == 0:
            raise ValueError(f"not enough chronological data for {competition}")

        baseline_predictions = add_elo_probabilities(test)
        logistic_predictions = _fit_predict_logistic(train, test)
        poisson_predictions = _fit_predict_poisson(train, test)
        comparisons[str(competition)] = LeagueModelComparison(
            train_matches=len(train),
            test_matches=len(test),
            elo_baseline=_score(baseline_predictions),
            calibrated_logistic_regression=_score(logistic_predictions),
            poisson_goal_model=_score(poisson_predictions),
        )
    return comparisons


def _fit_predict_logistic(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Fit preprocessing and calibration on training rows only, then predict the future holdout."""
    base_estimator = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(C=0.3, max_iter=1000, random_state=42),
            ),
        ]
    )
    model = CalibratedClassifierCV(
        estimator=base_estimator,
        method="sigmoid",
        cv=TimeSeriesSplit(n_splits=3),
    )
    model.fit(train[list(FEATURE_COLUMNS)], train["result"])
    predicted = model.predict_proba(test[list(FEATURE_COLUMNS)])
    columns = _probability_columns(model.classes_)
    probabilities = test.copy()
    for index, column in enumerate(columns):
        probabilities[column] = predicted[:, index]
    return probabilities


def _fit_predict_poisson(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Fit separate, time-tuned Poisson regressors for home and away goals."""
    home_model = _fit_poisson_model(train, "home_goals")
    away_model = _fit_poisson_model(train, "away_goals")
    home_rates = home_model.predict(test[list(FEATURE_COLUMNS)])
    away_rates = away_model.predict(test[list(FEATURE_COLUMNS)])

    probabilities = test.copy()
    probability_rows = [
        _outcome_probabilities_from_goal_rates(float(home_rate), float(away_rate))
        for home_rate, away_rate in zip(home_rates, away_rates, strict=True)
    ]
    probability_frame = pd.DataFrame(probability_rows, index=probabilities.index)
    for column in probability_frame:
        probabilities[column] = probability_frame[column]
    probabilities["expected_home_goals"] = home_rates
    probabilities["expected_away_goals"] = away_rates
    return probabilities


def _fit_poisson_model(train: pd.DataFrame, target: str) -> GridSearchCV:
    pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", PoissonRegressor(max_iter=1000)),
        ]
    )
    model = GridSearchCV(
        estimator=pipeline,
        param_grid={"model__alpha": (0.01, 0.1, 1.0, 10.0)},
        scoring="neg_mean_poisson_deviance",
        cv=TimeSeriesSplit(n_splits=3),
    )
    model.fit(train[list(FEATURE_COLUMNS)], train[target])
    return model


def _outcome_probabilities_from_goal_rates(home_rate: float, away_rate: float) -> dict[str, float]:
    """Sum independent Poisson scorelines from 0-0 through 12-12 and normalize."""
    home_probabilities = _poisson_probabilities(home_rate)
    away_probabilities = _poisson_probabilities(away_rate)
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    for home_goals, home_probability in enumerate(home_probabilities):
        for away_goals, away_probability in enumerate(away_probabilities):
            scoreline_probability = home_probability * away_probability
            if home_goals > away_goals:
                home_win += scoreline_probability
            elif home_goals == away_goals:
                draw += scoreline_probability
            else:
                away_win += scoreline_probability
    total = home_win + draw + away_win
    return {
        "p_home_win": home_win / total,
        "p_draw": draw / total,
        "p_away_win": away_win / total,
    }


def _poisson_probabilities(rate: float, max_goals: int = 12) -> list[float]:
    if rate <= 0:
        raise ValueError("Poisson goal rate must be positive")
    probabilities = [exp(-rate)]
    for goals in range(1, max_goals + 1):
        probabilities.append(probabilities[-1] * rate / goals)
    return probabilities


def _probability_columns(classes: object) -> list[str]:
    mapping = {
        MatchResult.HOME_WIN.value: "p_home_win",
        MatchResult.DRAW.value: "p_draw",
        MatchResult.AWAY_WIN.value: "p_away_win",
    }
    columns = [mapping[str(label)] for label in classes]
    if set(columns) != set(mapping.values()):
        raise ValueError("training data must include home wins, draws, and away wins")
    return columns


def _score(predictions: pd.DataFrame) -> ModelScore:
    return ModelScore(
        metrics=evaluate_probabilities(predictions),
        calibration_error=expected_calibration_error(predictions),
    )
