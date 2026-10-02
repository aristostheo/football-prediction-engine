from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from football_predictor.domain import HistoricalMatch


def validate_match_collection(matches: Iterable[HistoricalMatch]) -> list[HistoricalMatch]:
    """Validate and return matches in deterministic chronological order."""
    ordered = sorted(
        matches,
        key=lambda match: (
            match.competition.value,
            match.match_date,
            match.home_team,
            match.away_team,
        ),
    )
    seen: set[tuple[str, object, str, str]] = set()
    for match in ordered:
        if match.home_team == match.away_team:
            raise ValueError("home and away teams must be different")
        if match.home_goals < 0 or match.away_goals < 0:
            raise ValueError("goals must be non-negative")
        identity = (
            match.competition.value,
            match.match_date,
            match.home_team,
            match.away_team,
        )
        if identity in seen:
            raise ValueError(f"duplicate match: {identity}")
        seen.add(identity)
        for team in (match.home_team, match.away_team):
            if "[" in team or "]" in team or re.search(r"\s+v\s+", team, re.IGNORECASE):
                raise ValueError(f"malformed team name in match: {team!r}")
    return ordered


def validate_completed_season(
    matches: Iterable[HistoricalMatch], *, expected_matches_per_team: int
) -> list[HistoricalMatch]:
    """Require each club in a completed regular season to have a full schedule."""
    if expected_matches_per_team < 1:
        raise ValueError("expected_matches_per_team must be positive")
    ordered = validate_match_collection(matches)
    if not ordered:
        raise ValueError("completed season cannot be empty")
    competitions = {match.competition for match in ordered}
    seasons = {match.season for match in ordered}
    if len(competitions) != 1 or len(seasons) != 1:
        raise ValueError("completed season validation accepts one competition and season")

    appearances = Counter(team for match in ordered for team in (match.home_team, match.away_team))
    incomplete = {
        team: count for team, count in appearances.items() if count != expected_matches_per_team
    }
    if incomplete:
        raise ValueError(
            f"completed {next(iter(competitions))} {next(iter(seasons))} season expected "
            f"{expected_matches_per_team} matches per team; got {incomplete}"
        )
    if len(appearances) % 2:
        raise ValueError("a completed league season must have an even number of teams")
    return ordered
