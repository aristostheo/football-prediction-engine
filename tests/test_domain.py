from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from football_predictor.domain import Competition, HistoricalMatch, MatchResult


def make_match(**overrides: object) -> HistoricalMatch:
    values: dict[str, object] = {
        "match_date": "2025-08-16",
        "competition": Competition.PREMIER_LEAGUE,
        "season": "2025-26",
        "home_team": "Arsenal",
        "away_team": "Manchester United",
        "home_goals": 1,
        "away_goals": 0,
        "source_name": "Example source",
        "source_url": "https://example.com/matches.csv",
        "retrieved_at": datetime(2026, 9, 30, tzinfo=UTC),
    }
    values.update(overrides)
    return HistoricalMatch(**values)


def test_result_is_derived_from_score() -> None:
    assert make_match(home_goals=2, away_goals=2).result is MatchResult.DRAW
    assert make_match(home_goals=0, away_goals=1).result is MatchResult.AWAY_WIN


def test_a_team_cannot_play_itself() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        make_match(away_team="Arsenal")

