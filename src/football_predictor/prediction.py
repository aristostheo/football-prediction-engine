"""Runtime prediction engine for future fixtures using the locked model policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from football_predictor.domain import Competition
from football_predictor.evaluation import add_elo_probabilities
from football_predictor.features import (
    build_future_fixture_features,
    build_pre_match_features_and_states,
)
from football_predictor.models import (
    FEATURE_COLUMNS,
    _fit_poisson_model,
    _outcome_probabilities_from_goal_rates,
    blend_probabilities,
)
from football_predictor.team_names import resolve_team_name


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
        self._features, self._final_states = build_pre_match_features_and_states(self._history)
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
        history_through = self.latest_result_date(fixture.competition)
        if fixture.kickoff_date <= history_through:
            raise ValueError("fixture date must be after the latest locally recorded result")
        known_teams = set(history["home_team"]) | set(history["away_team"])
        canonical_fixture = FixtureToPredict(
            competition=fixture.competition,
            kickoff_date=fixture.kickoff_date,
            home_team=resolve_team_name(fixture.home_team, fixture.competition, known_teams),
            away_team=resolve_team_name(fixture.away_team, fixture.competition, known_teams),
        )
        unknown_teams = {canonical_fixture.home_team, canonical_fixture.away_team}.difference(
            known_teams
        )
        if unknown_teams:
            raise ValueError(
                f"No historical results available for these teams in {competition}: "
                f"{sorted(unknown_teams)}. Check the team names or update the historical dataset."
            )
        if canonical_fixture.home_team == canonical_fixture.away_team:
            raise ValueError("home and away teams must be different clubs")

        fixture_features = self._fixture_features(canonical_fixture)
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
            fixture=canonical_fixture,
            home_win_probability=float(prediction["p_home_win"]),
            draw_probability=float(prediction["p_draw"]),
            away_win_probability=float(prediction["p_away_win"]),
            model_policy=policy,
            history_through=history_through,
            history_age_days=(fixture.kickoff_date - history_through).days,
        )

    def latest_result_date(self, competition: Competition) -> date:
        """Return the latest locally recorded result for one competition."""
        history = self._history[self._history["competition"] == competition.value]
        if history.empty:
            raise ValueError(f"no historical matches for {competition.value}")
        return max(history["match_date"])

    def _fixture_features(self, fixture: FixtureToPredict) -> pd.DataFrame:
        return build_future_fixture_features(
            competition=fixture.competition.value,
            match_date=fixture.kickoff_date,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            final_states=self._final_states,
        )
