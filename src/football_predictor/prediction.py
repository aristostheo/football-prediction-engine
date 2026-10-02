"""Runtime prediction engine for future fixtures using the locked model policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
from threadpoolctl import threadpool_limits

from football_predictor.domain import Competition
from football_predictor.evaluation import add_elo_probabilities
from football_predictor.features import (
    TeamState,
    build_future_fixture_features,
    build_pre_match_features_and_states,
)
from football_predictor.models import (
    FEATURE_COLUMNS,
    _fit_poisson_model,
    _outcome_probabilities_from_goal_rates,
    blend_probabilities,
)
from football_predictor.team_names import is_registered_team, resolve_team_name

PROMOTED_TEAM_START_ELO = 1400.0
PROMOTED_TEAM_MODEL_WEIGHT = 0.5


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
        self._outcome_priors = {
            competition: _smoothed_outcome_prior(matches["result"])
            for competition, matches in self._history.groupby("competition", sort=False)
        }
        with threadpool_limits(limits=1):
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
        unregistered_teams = {
            team
            for team in unknown_teams
            if not is_registered_team(team, fixture.competition)
        }
        if unregistered_teams:
            raise ValueError(
                f"Unrecognized teams in {competition}: {sorted(unregistered_teams)}. "
                "Check the team names or update the team registry."
            )
        if canonical_fixture.home_team == canonical_fixture.away_team:
            raise ValueError("home and away teams must be different clubs")

        fixture_states = dict(self._final_states)
        for team in unknown_teams:
            fixture_states[(competition, team)] = TeamState(elo=PROMOTED_TEAM_START_ELO)
        fixture_features = self._fixture_features(canonical_fixture, fixture_states)
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
        if unknown_teams:
            probabilities = _shrink_to_prior(
                probabilities,
                self._outcome_priors[competition],
                model_weight=PROMOTED_TEAM_MODEL_WEIGHT,
            )
            policy = f"{policy}_promoted_prior"
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

    def _fixture_features(
        self,
        fixture: FixtureToPredict,
        final_states: dict[tuple[str, str], TeamState] | None = None,
    ) -> pd.DataFrame:
        return build_future_fixture_features(
            competition=fixture.competition.value,
            match_date=fixture.kickoff_date,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            final_states=final_states or self._final_states,
        )


def _smoothed_outcome_prior(results: pd.Series) -> dict[str, float]:
    counts = results.value_counts()
    denominator = len(results) + 3
    return {
        "p_home_win": float((counts.get("H", 0) + 1) / denominator),
        "p_draw": float((counts.get("D", 0) + 1) / denominator),
        "p_away_win": float((counts.get("A", 0) + 1) / denominator),
    }


def _shrink_to_prior(
    probabilities: pd.DataFrame, prior: dict[str, float], *, model_weight: float
) -> pd.DataFrame:
    adjusted = probabilities.copy()
    for column, prior_probability in prior.items():
        adjusted[column] = (
            model_weight * adjusted[column].to_numpy()
            + (1 - model_weight) * prior_probability
        )
    return adjusted
