from __future__ import annotations

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
        identity = (
            match.competition.value,
            match.match_date,
            match.home_team,
            match.away_team,
        )
        if identity in seen:
            raise ValueError(f"duplicate match: {identity}")
        seen.add(identity)
    return ordered

