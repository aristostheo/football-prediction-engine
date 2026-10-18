"""Runtime prediction engine for future fixtures using the locked model policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import exp
from pathlib import Path
from threading import Lock

import pandas as pd
from threadpoolctl import threadpool_limits

from football_predictor.data_status import history_coverage
from football_predictor.dataset import canonicalize_match_labels
from football_predictor.domain import Competition
from football_predictor.evaluation import add_elo_probabilities
from football_predictor.features import (
    TeamState,
    build_future_fixture_features,
    build_pre_match_features_and_states,
)
from football_predictor.market import market_probabilities_from_decimal_odds
from football_predictor.models import (
    FEATURE_COLUMNS,
    _fit_poisson_model,
    _outcome_probabilities_from_goal_rates,
    blend_probabilities,
)
from football_predictor.policy import (
    PROMOTED_TEAM_MODEL_WEIGHT,
    PROMOTED_TEAM_START_ELO,
    shrink_to_prior,
    smoothed_outcome_prior,
)
from football_predictor.team_names import is_registered_team, resolve_team_name


@dataclass(frozen=True)
class FixtureToPredict:
    competition: Competition
    kickoff_date: date
    home_team: str
    away_team: str
    kickoff_at: datetime | None = None
    odds_home: float | None = None
    odds_draw: float | None = None
    odds_away: float | None = None


@dataclass(frozen=True)
class MatchPrediction:
    fixture: FixtureToPredict
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    model_policy: str
    history_through: date
    history_age_days: int
    forecasted_at: datetime
    model_probabilities: tuple[float, float, float]
    market_probabilities: tuple[float, float, float] | None
    context: PredictionContext
    components: PredictionComponents


@dataclass(frozen=True)
class PredictionContext:
    """Observed pre-match inputs shown to users; not a causal attribution."""

    home_elo: float
    away_elo: float
    home_form_matches: int
    away_form_matches: int
    home_form_points_per_match: float
    away_form_points_per_match: float
    home_form_goals_for_per_match: float
    away_form_goals_for_per_match: float
    home_form_goals_against_per_match: float
    away_form_goals_against_per_match: float
    home_venue_points_per_match: float
    away_venue_points_per_match: float
    head_to_head_matches: int = 0
    head_to_head_home_wins: int = 0
    head_to_head_draws: int = 0
    head_to_head_away_wins: int = 0
    head_to_head_recent: tuple[str, ...] = ()
    home_form_results: tuple[str, ...] = ()
    away_form_results: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScorelineForecast:
    home_goals: int
    away_goals: int
    probability: float


@dataclass(frozen=True)
class PredictionComponents:
    """Probability components and weights that produce the model forecast."""

    elo_probabilities: tuple[float, float, float]
    goal_probabilities: tuple[float, float, float] | None
    core_model_probabilities: tuple[float, float, float]
    home_goal_rate: float | None
    away_goal_rate: float | None
    elo_weight: float
    base_model_weight: float
    league_prior_probabilities: tuple[float, float, float] | None
    top_scorelines: tuple[ScorelineForecast, ...] = ()
    scoreline_home_goal_rate: float | None = None
    scoreline_away_goal_rate: float | None = None


class PredictionEngine:
    """Predict from completed earlier days, excluding same-day results when needed."""

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
        self._history = canonicalize_match_labels(historical_matches)
        self._history["match_date"] = pd.to_datetime(self._history["match_date"]).dt.date
        self._prior_day_engines: dict[str, PredictionEngine] = {}
        self._prior_day_lock = Lock()
        self._result_lookup = {
            (str(row.competition), row.match_date, str(row.home_team), str(row.away_team)): str(
                row.result
            )
            for row in self._history.itertuples(index=False)
        }
        self._score_lookup = {
            (str(row.competition), row.match_date, str(row.home_team), str(row.away_team)): (
                int(row.home_goals),
                int(row.away_goals),
            )
            for row in self._history.itertuples(index=False)
        }
        self._features, self._final_states = build_pre_match_features_and_states(self._history)
        self._outcome_priors = {
            competition: smoothed_outcome_prior(matches["result"])
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

    def readiness(self) -> dict[str, object]:
        """Report loaded model availability and actual per-league data cutoffs."""
        leagues = history_coverage(self._history)
        for row in leagues:
            row["model_ready"] = row["competition"] in self._poisson_models
        ready = all(row["model_ready"] for row in leagues)
        status = "ready"
        if not ready:
            status = "not_ready"
        elif any(row["status"] != "recent" for row in leagues):
            status = "degraded"
        return {
            "ready": ready,
            "status": status,
            "engine": "loaded",
            "leagues": leagues,
        }

    def predict(self, fixture: FixtureToPredict) -> MatchPrediction:
        competition = fixture.competition.value
        history = self._history[self._history["competition"] == competition]
        if history.empty:
            raise ValueError(f"no historical matches for {competition}")
        history_through = self.latest_result_date(fixture.competition)
        if fixture.kickoff_date < history_through:
            raise ValueError("fixture date must be after the latest locally recorded result")
        forecasted_at = datetime.now(UTC)
        if fixture.kickoff_at is not None:
            if fixture.kickoff_at.tzinfo is None or fixture.kickoff_at.utcoffset() is None:
                raise ValueError("kickoff_at must include a timezone offset")
            if fixture.kickoff_at <= forecasted_at:
                raise ValueError("cannot create a prospective forecast after kickoff")
        if fixture.kickoff_date == history_through:
            if fixture.kickoff_at is None and fixture.kickoff_date < forecasted_at.date():
                raise ValueError("fixture date must be after the latest locally recorded result")
            # Date-only result data cannot establish within-day availability.
            # Exclude the whole target day from state, model fitting and priors.
            with self._prior_day_lock:
                prior_engine = self._prior_day_engines.get(competition)
                if prior_engine is None:
                    prior_history = history[history["match_date"] < fixture.kickoff_date]
                    if prior_history.empty:
                        raise ValueError("no historical matches available before this kickoff date")
                    prior_engine = PredictionEngine(prior_history)
                    self._prior_day_engines[competition] = prior_engine
            return prior_engine.predict(fixture)
        known_teams = set(history["home_team"]) | set(history["away_team"])
        canonical_fixture = FixtureToPredict(
            competition=fixture.competition,
            kickoff_date=fixture.kickoff_date,
            home_team=resolve_team_name(fixture.home_team, fixture.competition, known_teams),
            away_team=resolve_team_name(fixture.away_team, fixture.competition, known_teams),
            kickoff_at=fixture.kickoff_at,
        )
        unknown_teams = {canonical_fixture.home_team, canonical_fixture.away_team}.difference(
            known_teams
        )
        unregistered_teams = {
            team for team in unknown_teams if not is_registered_team(team, fixture.competition)
        }
        if unregistered_teams:
            raise ValueError(
                f"Unrecognized teams in {competition}: {sorted(unregistered_teams)}. "
                "Check the team names or update the team registry."
            )
        if canonical_fixture.home_team == canonical_fixture.away_team:
            raise ValueError("home and away teams must be different clubs")

        supplied_odds = (
            fixture.odds_home,
            fixture.odds_draw,
            fixture.odds_away,
        )
        market_probabilities = None
        if any(odds is not None for odds in supplied_odds):
            if any(odds is None for odds in supplied_odds):
                raise ValueError("provide all three decimal odds: home, draw, and away")
            try:
                market_probabilities = market_probabilities_from_decimal_odds(
                    fixture.odds_home, fixture.odds_draw, fixture.odds_away
                )
            except (TypeError, ValueError) as error:
                raise ValueError(f"invalid market odds: {error}") from error

        fixture_states = dict(self._final_states)
        for team in unknown_teams:
            fixture_states[(competition, team)] = TeamState(elo=PROMOTED_TEAM_START_ELO)
        fixture_features = self._fixture_features(canonical_fixture, fixture_states)
        feature = fixture_features.iloc[0]
        h2h = _head_to_head_summary(
            history,
            canonical_fixture.home_team,
            canonical_fixture.away_team,
            canonical_fixture.kickoff_date,
        )
        context = PredictionContext(
            home_elo=float(feature["home_elo"]),
            away_elo=float(feature["away_elo"]),
            home_form_matches=int(feature["home_matches_played"]),
            away_form_matches=int(feature["away_matches_played"]),
            home_form_points_per_match=float(feature["home_form_points_per_match"]),
            away_form_points_per_match=float(feature["away_form_points_per_match"]),
            home_form_goals_for_per_match=float(feature["home_form_goals_for_per_match"]),
            away_form_goals_for_per_match=float(feature["away_form_goals_for_per_match"]),
            home_form_goals_against_per_match=float(feature["home_form_goals_against_per_match"]),
            away_form_goals_against_per_match=float(feature["away_form_goals_against_per_match"]),
            home_venue_points_per_match=float(feature["home_home_points_per_match"]),
            away_venue_points_per_match=float(feature["away_away_points_per_match"]),
            home_form_results=_form_results(
                fixture_states[(competition, canonical_fixture.home_team)],
                int(feature["home_matches_played"]),
            ),
            away_form_results=_form_results(
                fixture_states[(competition, canonical_fixture.away_team)],
                int(feature["away_matches_played"]),
            ),
            **h2h,
        )
        elo = add_elo_probabilities(fixture_features)
        elo_probabilities = _probability_tuple(elo.iloc[0])
        home_model, away_model = self._poisson_models[competition]
        home_rate = float(home_model.predict(fixture_features[list(FEATURE_COLUMNS)])[0])
        away_rate = float(away_model.predict(fixture_features[list(FEATURE_COLUMNS)])[0])
        poisson = fixture_features.copy()
        scorelines = _top_scorelines_from_goal_rates(home_rate, away_rate)
        goal_probability_frame = _outcome_probabilities_from_goal_rates(home_rate, away_rate)
        for column, value in goal_probability_frame.items():
            poisson[column] = value
        goal_probabilities = _probability_tuple(poisson.iloc[0])
        elo_weight = 1.0
        if fixture.competition is Competition.PREMIER_LEAGUE:
            elo_weight = 0.25
            probabilities = blend_probabilities(elo, poisson, elo_weight=elo_weight)
            policy = "elo_poisson_25_75"
        else:
            probabilities = elo
            policy = "elo"
        core_model_probabilities = _probability_tuple(probabilities.iloc[0])
        base_model_weight = 1.0
        prior_probabilities = None
        if unknown_teams:
            prior = self._outcome_priors[competition]
            prior_probabilities = (
                prior["p_home_win"],
                prior["p_draw"],
                prior["p_away_win"],
            )
            base_model_weight = PROMOTED_TEAM_MODEL_WEIGHT
            probabilities = shrink_to_prior(
                probabilities,
                prior,
                model_weight=base_model_weight,
            )
            policy = f"{policy}_promoted_prior"
        prediction = probabilities.iloc[0]
        forecasted_at = datetime.now(UTC)
        if fixture.kickoff_at is not None and fixture.kickoff_at <= forecasted_at:
            raise ValueError("cannot create a prospective forecast after kickoff")
        model_probabilities = (
            float(prediction["p_home_win"]),
            float(prediction["p_draw"]),
            float(prediction["p_away_win"]),
        )
        return MatchPrediction(
            fixture=canonical_fixture,
            home_win_probability=model_probabilities[0],
            draw_probability=model_probabilities[1],
            away_win_probability=model_probabilities[2],
            model_policy=policy,
            history_through=history_through,
            history_age_days=(fixture.kickoff_date - history_through).days,
            forecasted_at=forecasted_at,
            model_probabilities=model_probabilities,
            market_probabilities=market_probabilities,
            context=context,
            components=PredictionComponents(
                elo_probabilities=elo_probabilities,
                goal_probabilities=(
                    goal_probabilities
                    if fixture.competition is Competition.PREMIER_LEAGUE
                    else None
                ),
                core_model_probabilities=core_model_probabilities,
                home_goal_rate=(
                    home_rate if fixture.competition is Competition.PREMIER_LEAGUE else None
                ),
                away_goal_rate=away_rate,
                top_scorelines=scorelines,
                scoreline_home_goal_rate=home_rate,
                scoreline_away_goal_rate=away_rate,
                elo_weight=elo_weight,
                base_model_weight=base_model_weight,
                league_prior_probabilities=prior_probabilities,
            ),
        )

    def latest_result_date(self, competition: Competition) -> date:
        """Return the latest locally recorded result for one competition."""
        history = self._history[self._history["competition"] == competition.value]
        if history.empty:
            raise ValueError(f"no historical matches for {competition.value}")
        return max(history["match_date"])

    def available_teams(self, competition: Competition) -> list[str]:
        """Return teams recorded in the most recent available season for a league."""
        history = self._history[self._history["competition"] == competition.value]
        if history.empty:
            raise ValueError(f"no historical matches for {competition.value}")
        latest_season = history["season"].astype(str).max()
        latest = history[history["season"].astype(str) == latest_season]
        return sorted(set(latest["home_team"].astype(str)) | set(latest["away_team"].astype(str)))

    def find_results(
        self, fixtures: list[tuple[str, str, date, str, str]]
    ) -> dict[str, str | None]:
        """Look up completed outcomes for canonical prospective forecast keys."""
        return {
            fixture_id: self._result_lookup.get((competition, match_date, home_team, away_team))
            for fixture_id, competition, match_date, home_team, away_team in fixtures
        }

    def find_scores(
        self, fixtures: list[tuple[str, str, date, str, str]]
    ) -> dict[str, tuple[int, int] | None]:
        return {
            fixture_id: self._score_lookup.get((competition, match_date, home_team, away_team))
            for fixture_id, competition, match_date, home_team, away_team in fixtures
        }

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


def _form_results(state: TeamState, count: int) -> tuple[str, ...]:
    if count == 0:
        return ()
    return tuple(
        "W" if points == 3 else "D" if points == 1 else "L"
        for _, _, points in list(state.all_results)[-count:]
    )


def _top_scorelines_from_goal_rates(
    home_rate: float, away_rate: float, *, count: int = 3
) -> tuple[ScorelineForecast, ...]:
    """Return the most likely scorelines from the separate Poisson goal model."""
    home = _poisson_score_probabilities(home_rate)
    away = _poisson_score_probabilities(away_rate)
    candidates = [
        ScorelineForecast(home_goals, away_goals, home_probability * away_probability)
        for home_goals, home_probability in enumerate(home)
        for away_goals, away_probability in enumerate(away)
    ]
    total = sum(item.probability for item in candidates)
    return tuple(
        ScorelineForecast(item.home_goals, item.away_goals, item.probability / total)
        for item in sorted(candidates, key=lambda item: item.probability, reverse=True)[:count]
    )


def _poisson_score_probabilities(rate: float, max_goals: int = 12) -> list[float]:
    if rate <= 0:
        raise ValueError("Poisson goal rate must be positive")
    rate = min(rate, 8.0)
    probabilities = [exp(-rate)]
    for goals in range(1, max_goals + 1):
        probabilities.append(probabilities[-1] * rate / goals)
    return probabilities


def _head_to_head_summary(
    history: pd.DataFrame, home_team: str, away_team: str, before_date: date
) -> dict[str, object]:
    meetings = history[
        (history["match_date"] < before_date)
        & (
            ((history["home_team"] == home_team) & (history["away_team"] == away_team))
            | ((history["home_team"] == away_team) & (history["away_team"] == home_team))
        )
    ].sort_values("match_date")
    home_wins = draws = away_wins = 0
    descriptions: list[str] = []
    for row in meetings.itertuples(index=False):
        if row.result == "D":
            draws += 1
            outcome = "D"
        elif (row.result == "H" and row.home_team == home_team) or (
            row.result == "A" and row.away_team == home_team
        ):
            home_wins += 1
            outcome = "H"
        else:
            away_wins += 1
            outcome = "A"
        descriptions.append(
            f"{row.match_date}: {row.home_team} "
            f"{int(row.home_goals)}–{int(row.away_goals)} {row.away_team} "
            f"({outcome} for {home_team})"
        )
    return {
        "head_to_head_matches": len(meetings),
        "head_to_head_home_wins": home_wins,
        "head_to_head_draws": draws,
        "head_to_head_away_wins": away_wins,
        "head_to_head_recent": tuple(descriptions[-5:][::-1]),
    }


def _probability_tuple(values: pd.Series) -> tuple[float, float, float]:
    return (
        float(values["p_home_win"]),
        float(values["p_draw"]),
        float(values["p_away_win"]),
    )
