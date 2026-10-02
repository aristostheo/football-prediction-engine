from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Final

from football_predictor.domain import Competition, HistoricalMatch
from football_predictor.normalization import normalize_season, normalize_team_name
from football_predictor.team_names import canonical_team_name

_DATE_LINE: Final = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})(?:\s+(?P<year>\d{4}))?\s*$"
)
_MATCH_LINE: Final = re.compile(
    r"^\s*(?:\d{1,2}:\d{2}\s+)?"
    r"(?P<home>.+?)\s+v\s+(?P<away>.+?)\s+"
    r"(?P<home_goals>\d+)-(?P<away_goals>\d+)(?:\s+\([^)]*\))?"
    r"(?:\s+\[awarded\])?\s*$"
)
_MATCH_LINE_HOME_SCORE_AWAY: Final = re.compile(
    r"^\s*(?:\d{1,2}:\d{2}\s+)?"
    r"(?P<home>.+?)\s+(?P<home_goals>\d+)-(?P<away_goals>\d+)"
    r"(?:\s+\([^)]*\))?\s+(?P<away>.+?)\s*$"
)
_REGULAR_MATCHDAY: Final = re.compile(r"^\s*[▪»]\s*Matchday\s+\d+\s*$")
_ANY_MATCHDAY: Final = re.compile(r"^\s*[▪»].*Matchday\s+\d+\s*$")


def parse_openfootball_results(
    text: str,
    *,
    competition: Competition,
    season: str,
    source_url: str,
    retrieved_at: datetime | None = None,
) -> list[HistoricalMatch]:
    """Parse one OpenFootball results file into completed regular-season matches.

    OpenFootball files use date headers followed by compact fixture lines. A date
    may omit its year, so the season boundary supplies it. Later-stage fixtures
    are deliberately excluded until the project adopts an explicit stage policy.
    """
    normalized_season = normalize_season(season)
    start_year = int(normalized_season[:4])
    retrieved_at = retrieved_at or datetime.now(UTC)
    current_date: date | None = None
    is_regular_stage = True
    matches: list[HistoricalMatch] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if _REGULAR_MATCHDAY.match(line):
            is_regular_stage = True
            continue
        if _ANY_MATCHDAY.match(line):
            is_regular_stage = False
            continue

        date_match = _DATE_LINE.match(line)
        if date_match:
            month = datetime.strptime(date_match.group("month"), "%b").month
            year = int(date_match.group("year") or _infer_year(month, start_year))
            current_date = date(year, month, int(date_match.group("day")))
            continue

        result_match = _MATCH_LINE.match(line) or _MATCH_LINE_HOME_SCORE_AWAY.match(line)
        if not result_match or not is_regular_stage:
            continue
        if current_date is None:
            raise ValueError("encountered a match before its date header")

        matches.append(
            HistoricalMatch(
                match_date=current_date,
                competition=competition,
                season=normalized_season,
                home_team=canonical_team_name(
                    normalize_team_name(result_match.group("home")), competition
                ),
                away_team=canonical_team_name(
                    normalize_team_name(result_match.group("away")), competition
                ),
                home_goals=int(result_match.group("home_goals")),
                away_goals=int(result_match.group("away_goals")),
                source_name="OpenFootball",
                source_url=source_url,
                retrieved_at=retrieved_at,
            )
        )
    return matches


def _infer_year(month: int, season_start_year: int) -> int:
    """European domestic seasons normally turn over between June and July."""
    return season_start_year if month >= 7 else season_start_year + 1
