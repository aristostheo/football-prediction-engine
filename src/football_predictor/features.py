"""Leakage-safe pre-match form, rest, and Elo features."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from math import nan

import pandas as pd


@dataclass(frozen=True)
class FeatureConfig:
    """Fixed V1 choices for rolling team context and Elo updates."""

    form_window: int = 5
    initial_elo: float = 1500.0
    elo_k_factor: float = 20.0
    elo_home_advantage: float = 60.0
    max_rest_days: int = 97
    history_gap_reset_days: int = 180
    elo_gap_half_life_days: float = 365.0


@dataclass
class TeamState:
    """Only information available before a team's next match."""

    all_results: deque[tuple[int, int, int]] = field(default_factory=deque)
    home_results: deque[tuple[int, int, int]] = field(default_factory=deque)
    away_results: deque[tuple[int, int, int]] = field(default_factory=deque)
    last_match_date: date | None = None
    elo: float = 1500.0


_REQUIRED_COLUMNS = {
    "match_date",
    "competition",
    "season",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
    "result",
}


def build_pre_match_features(
    matches: pd.DataFrame, *, config: FeatureConfig = FeatureConfig()
) -> pd.DataFrame:
    """Attach only pre-match features to canonical historical rows.

    All fixtures on the same competition date receive features from exactly the
    same prior state. Their outcomes are committed only after every feature row
    for that date has been emitted, preventing accidental same-day leakage.
    """
    features, _ = build_pre_match_features_and_states(matches, config=config)
    return features


def build_pre_match_features_and_states(
    matches: pd.DataFrame, *, config: FeatureConfig = FeatureConfig()
) -> tuple[pd.DataFrame, dict[tuple[str, str], TeamState]]:
    """Build leakage-safe features and the terminal per-team states in one pass."""
    missing = _REQUIRED_COLUMNS.difference(matches.columns)
    if missing:
        raise ValueError(f"missing required match columns: {sorted(missing)}")
    if config.form_window < 1:
        raise ValueError("form_window must be at least one")
    if config.max_rest_days < 1 or config.history_gap_reset_days < 1:
        raise ValueError("rest-day and history-gap limits must be positive")
    if config.elo_gap_half_life_days <= 0:
        raise ValueError("Elo gap half-life must be positive")

    ordered = matches.copy()
    ordered["match_date"] = pd.to_datetime(ordered["match_date"], format="ISO8601")
    ordered = ordered.sort_values(
        ["competition", "match_date", "home_team", "away_team"], kind="stable"
    ).reset_index(drop=True)

    states: dict[tuple[str, str], TeamState] = defaultdict(
        lambda: TeamState(elo=config.initial_elo)
    )
    feature_rows: list[dict[str, float]] = []

    for (_, match_date), day_matches in ordered.groupby(["competition", "match_date"], sort=False):
        day_keys: set[tuple[str, str]] = set()
        for match in day_matches.itertuples(index=False):
            home_key = (match.competition, match.home_team)
            away_key = (match.competition, match.away_team)
            if home_key in day_keys or away_key in day_keys:
                raise ValueError(
                    "a team appears more than once on the same competition date: "
                    f"{match.competition} {match_date.date()}"
                )
            day_keys.update((home_key, away_key))
            home_state = states[home_key]
            away_state = states[away_key]
            _prepare_state_after_gap(home_state, match_date.date(), config)
            _prepare_state_after_gap(away_state, match_date.date(), config)
            feature_rows.append(
                _feature_row(
                    home_state=home_state,
                    away_state=away_state,
                    match_date=match_date.date(),
                    config=config,
                )
            )

        for match in day_matches.itertuples(index=False):
            _update_states(
                home_state=states[(match.competition, match.home_team)],
                away_state=states[(match.competition, match.away_team)],
                home_goals=int(match.home_goals),
                away_goals=int(match.away_goals),
                match_date=match_date.date(),
                config=config,
            )

    features = pd.DataFrame(feature_rows)
    return pd.concat([ordered, features], axis=1), dict(states)


def build_future_fixture_features(
    *,
    competition: str,
    match_date: date,
    home_team: str,
    away_team: str,
    final_states: Mapping[tuple[str, str], TeamState],
    config: FeatureConfig = FeatureConfig(),
) -> pd.DataFrame:
    """Build one future row from cached team states without replaying match history."""
    try:
        home_state = final_states[(competition, home_team)]
        away_state = final_states[(competition, away_team)]
    except KeyError as error:
        raise ValueError(f"team state is unavailable for {error.args[0][1]}") from error
    return pd.DataFrame(
        [
            _feature_row(
                home_state=home_state, away_state=away_state, match_date=match_date, config=config
            )
        ]
    )


def _feature_row(
    *, home_state: TeamState, away_state: TeamState, match_date: date, config: FeatureConfig
) -> dict[str, float]:
    home_elo = home_state.elo
    away_elo = away_state.elo
    return {
        "home_matches_played": float(len(home_state.all_results)),
        "away_matches_played": float(len(away_state.all_results)),
        "home_form_points_per_match": _points_per_match(home_state.all_results),
        "away_form_points_per_match": _points_per_match(away_state.all_results),
        "home_form_goals_for_per_match": _goals_per_match(home_state.all_results, index=0),
        "away_form_goals_for_per_match": _goals_per_match(away_state.all_results, index=0),
        "home_form_goals_against_per_match": _goals_per_match(home_state.all_results, index=1),
        "away_form_goals_against_per_match": _goals_per_match(away_state.all_results, index=1),
        "home_home_points_per_match": _points_per_match(home_state.home_results),
        "away_away_points_per_match": _points_per_match(away_state.away_results),
        "home_days_since_last_match": _days_since(
            home_state.last_match_date, match_date, config.max_rest_days
        ),
        "away_days_since_last_match": _days_since(
            away_state.last_match_date, match_date, config.max_rest_days
        ),
        "home_elo": home_elo,
        "away_elo": away_elo,
        "elo_difference": home_elo + config.elo_home_advantage - away_elo,
    }


def _update_states(
    *,
    home_state: TeamState,
    away_state: TeamState,
    home_goals: int,
    away_goals: int,
    match_date: date,
    config: FeatureConfig,
) -> None:
    home_points = _points_for(home_goals, away_goals)
    away_points = _points_for(away_goals, home_goals)
    home_state.all_results.append((home_goals, away_goals, home_points))
    home_state.home_results.append((home_goals, away_goals, home_points))
    away_state.all_results.append((away_goals, home_goals, away_points))
    away_state.away_results.append((away_goals, home_goals, away_points))
    for results in (
        home_state.all_results,
        home_state.home_results,
        away_state.all_results,
        away_state.away_results,
    ):
        while len(results) > config.form_window:
            results.popleft()

    expected_home = _expected_home_score(home_state.elo, away_state.elo, config.elo_home_advantage)
    actual_home = 1.0 if home_goals > away_goals else 0.5 if home_goals == away_goals else 0.0
    adjustment = config.elo_k_factor * (actual_home - expected_home)
    home_state.elo += adjustment
    away_state.elo -= adjustment
    home_state.last_match_date = match_date
    away_state.last_match_date = match_date


def _prepare_state_after_gap(state: TeamState, match_date: date, config: FeatureConfig) -> None:
    if state.last_match_date is None:
        return
    gap_days = (match_date - state.last_match_date).days
    if gap_days <= config.history_gap_reset_days:
        return
    state.all_results.clear()
    state.home_results.clear()
    state.away_results.clear()
    regression = 0.5 ** (gap_days / config.elo_gap_half_life_days)
    state.elo = config.initial_elo + (state.elo - config.initial_elo) * regression


def _points_for(goals_for: int, goals_against: int) -> int:
    if goals_for > goals_against:
        return 3
    if goals_for == goals_against:
        return 1
    return 0


def _points_per_match(results: Iterable[tuple[int, int, int]]) -> float:
    values = list(results)
    return sum(result[2] for result in values) / len(values) if values else 0.0


def _goals_per_match(results: Iterable[tuple[int, int, int]], *, index: int) -> float:
    values = list(results)
    return sum(result[index] for result in values) / len(values) if values else 0.0


def _days_since(previous_date: date | None, match_date: date, cap: int) -> float:
    return float(min((match_date - previous_date).days, cap)) if previous_date else nan


def _expected_home_score(home_elo: float, away_elo: float, home_advantage: float) -> float:
    return 1.0 / (1.0 + 10 ** ((away_elo - home_elo - home_advantage) / 400.0))
