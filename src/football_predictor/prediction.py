"""Runtime prediction engine for future fixtures using the locked model policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from football_predictor.domain import Competition
from football_predictor.evaluation import add_elo_probabilities
from football_predictor.features import build_pre_match_features
from football_predictor.models import (
    FEATURE_COLUMNS,
    _fit_poisson_model,
    _outcome_probabilities_from_goal_rates,
    blend_probabilities,
)


@dataclass(frozen=True)
class FixtureToPredict:
    competition: Competition
    kickoff_date: date
    home_team: str
    away_team: str


@dataclass(frozen=True)
class MatchPrediction:
    fixture: FixtureToPredict
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    model_policy: str
    history_through: date
    history_age_days: int


class PredictionEngine:
    """Build on the entire available history and predict strictly after it."""

    def __init__(self, historical_matches: pd.DataFrame) -> None:
        required = {
            "match_date",
            "competition",
            "season",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
            "result",
        }
        missing = required.difference(historical_matches.columns)
        if missing:
            raise ValueError(f"missing historical columns: {sorted(missing)}")
        self._history = historical_matches.copy()
        self._history["match_date"] = pd.to_datetime(self._history["match_date"]).dt.date
        self._features = build_pre_match_features(self._history)
        self._poisson_models = {
            competition: (
                _fit_poisson_model(features, "home_goals"),
                _fit_poisson_model(features, "away_goals"),
            )
            for competition, features in self._features.groupby("competition", sort=False)
        }

    @classmethod
    def from_csv(cls, path: Path) -> PredictionEngine:
        return cls(pd.read_csv(path))

    def predict(self, fixture: FixtureToPredict) -> MatchPrediction:
        competition = fixture.competition.value
        history = self._history[self._history["competition"] == competition]
        if history.empty:
            raise ValueError(f"no historical matches for {competition}")
        history_through = max(history["match_date"])
        if fixture.kickoff_date <= history_through:
            raise ValueError("fixture date must be after the latest locally recorded result")
        known_teams = set(history["home_team"]) | set(history["away_team"])
        unknown_teams = {fixture.home_team, fixture.away_team}.difference(known_teams)
        if unknown_teams:
            raise ValueError(f"unknown team names: {sorted(unknown_teams)}")

        fixture_features = self._fixture_features(history, fixture)
        elo = add_elo_probabilities(fixture_features)
        home_model, away_model = self._poisson_models[competition]
        home_rate = float(home_model.predict(fixture_features[list(FEATURE_COLUMNS)])[0])
        away_rate = float(away_model.predict(fixture_features[list(FEATURE_COLUMNS)])[0])
        poisson = fixture_features.copy()
        for column, value in _outcome_probabilities_from_goal_rates(home_rate, away_rate).items():
            poisson[column] = value

        if fixture.competition is Competition.PREMIER_LEAGUE:
            probabilities = blend_probabilities(elo, poisson, elo_weight=0.25)
            policy = "elo_poisson_25_75"
        else:
            probabilities = elo
            policy = "elo"
        prediction = probabilities.iloc[0]
        return MatchPrediction(
            fixture=fixture,
            home_win_probability=float(prediction["p_home_win"]),
            draw_probability=float(prediction["p_draw"]),
            away_win_probability=float(prediction["p_away_win"]),
            model_policy=policy,
            history_through=history_through,
            history_age_days=(fixture.kickoff_date - history_through).days,
        )

    def _fixture_features(self, history: pd.DataFrame, fixture: FixtureToPredict) -> pd.DataFrame:
        placeholder = history.iloc[[-1]].copy()
        placeholder["match_date"] = fixture.kickoff_date
        placeholder["home_team"] = fixture.home_team
        placeholder["away_team"] = fixture.away_team
        placeholder["home_goals"] = 0
        placeholder["away_goals"] = 0
        placeholder["result"] = "D"
        feature_history = pd.concat([history, placeholder], ignore_index=True)
        return build_pre_match_features(feature_history).tail(1)
