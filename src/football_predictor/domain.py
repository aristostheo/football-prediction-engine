from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Competition(StrEnum):
    PREMIER_LEAGUE = "premier_league"
    SUPER_LEAGUE_GREECE = "super_league_greece"


class MatchResult(StrEnum):
    HOME_WIN = "H"
    DRAW = "D"
    AWAY_WIN = "A"


class HistoricalMatch(BaseModel):
    """A completed match, normalized into the project's canonical contract."""

    match_date: date
    competition: Competition
    season: str = Field(pattern=r"^\d{4}-\d{2}$")
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    source_name: str = Field(min_length=1)
    source_url: HttpUrl
    retrieved_at: datetime

    @model_validator(mode="after")
    def teams_must_differ(self) -> HistoricalMatch:
        if self.home_team == self.away_team:
            raise ValueError("home_team and away_team must differ")
        return self

    @property
    def result(self) -> MatchResult:
        if self.home_goals > self.away_goals:
            return MatchResult.HOME_WIN
        if self.home_goals < self.away_goals:
            return MatchResult.AWAY_WIN
        return MatchResult.DRAW

