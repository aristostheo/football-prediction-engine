"""Optional current-fixture adapter for API-Football."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from football_predictor.domain import Competition

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_FOOTBALL_LEAGUE_IDS = {
    Competition.PREMIER_LEAGUE: 39,
    Competition.SUPER_LEAGUE_GREECE: 197,
}


@dataclass(frozen=True)
class LiveFixture:
    fixture_id: int
    competition: Competition
    kickoff_at: datetime
    home_team: str
    away_team: str


class FixtureProvider(Protocol):
    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]: ...


class FixtureProviderError(RuntimeError):
    """Raised when a live-fixture provider cannot return a valid response."""


class ApiFootballFixtureProvider:
    """Read upcoming fixtures from API-Football with an API key supplied at runtime."""

    def __init__(self, api_key: str, *, base_url: str = API_FOOTBALL_BASE_URL) -> None:
        if not api_key:
            raise ValueError("API-Football API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_environment(cls) -> ApiFootballFixtureProvider:
        api_key = os.environ.get("API_FOOTBALL_KEY")
        if not api_key:
            raise FixtureProviderError("API_FOOTBALL_KEY is not configured")
        return cls(api_key)

    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
        query = urlencode(
            {
                "league": API_FOOTBALL_LEAGUE_IDS[competition],
                "season": _season_start_year(fixture_date),
                "date": fixture_date.isoformat(),
            }
        )
        request = Request(
            f"{self._base_url}/fixtures?{query}",
            headers={"x-apisports-key": self._api_key},
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed provider URL
                payload = json.load(response)
        except OSError as error:
            raise FixtureProviderError("API-Football request failed") from error
        if payload.get("errors"):
            raise FixtureProviderError(f"API-Football returned errors: {payload['errors']}")
        try:
            return [
                LiveFixture(
                    fixture_id=int(item["fixture"]["id"]),
                    competition=competition,
                    kickoff_at=datetime.fromisoformat(item["fixture"]["date"]),
                    home_team=item["teams"]["home"]["name"],
                    away_team=item["teams"]["away"]["name"],
                )
                for item in payload["response"]
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise FixtureProviderError(
                "API-Football returned an unexpected fixture payload"
            ) from error


def _season_start_year(fixture_date: date) -> int:
    """Return API-Football's starting year for a European league season."""
    return fixture_date.year if fixture_date.month >= 7 else fixture_date.year - 1
