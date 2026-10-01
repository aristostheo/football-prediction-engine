"""Optional current-fixture adapters for Goal API and API-Football."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from football_predictor.domain import Competition

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_FOOTBALL_LEAGUE_IDS = {
    Competition.PREMIER_LEAGUE: 39,
    Competition.SUPER_LEAGUE_GREECE: 197,
}
GOAL_API_BASE_URL = "https://api.goal-api.com/v1"
GOAL_API_USER_AGENT = "football-prediction-engine/0.1"
GOAL_API_LEAGUE_IDS = {
    # Fixtures' leagueId filter expects Goal API's internal `id`, not `apiId`.
    Competition.PREMIER_LEAGUE: "cmr77dvkr005nrx06lp7rvp49",
    Competition.SUPER_LEAGUE_GREECE: "cmr77dwfb00jmrx06oapyzogf",
}


@dataclass(frozen=True)
class LiveFixture:
    fixture_id: str
    competition: Competition
    kickoff_at: datetime
    home_team: str
    away_team: str


class FixtureProvider(Protocol):
    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]: ...


class FixtureProviderError(RuntimeError):
    """Raised when a live-fixture provider cannot return a valid response."""


class GoalApiFixtureProvider:
    """Read current fixtures from Goal API using a server-side API key."""

    def __init__(self, api_key: str, *, base_url: str = GOAL_API_BASE_URL) -> None:
        if not api_key:
            raise ValueError("Goal API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_environment(cls) -> GoalApiFixtureProvider:
        api_key = os.environ.get("GOAL_API_KEY")
        if not api_key:
            raise FixtureProviderError("GOAL_API_KEY is not configured")
        return cls(api_key)

    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
        league_id = str(GOAL_API_LEAGUE_IDS[competition])
        raw_fixtures: list[dict[str, object]] = []
        offset = 0
        page_count = 0
        seen_pages: set[str] = set()

        while True:
            query = urlencode(
                {
                    "leagueId": league_id,
                    "limit": 100,
                    "offset": offset,
                }
            )
            request = Request(
                f"{self._base_url}/fixtures/date/{fixture_date.isoformat()}?{query}",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": GOAL_API_USER_AGENT,
                },
            )
            payload = self._request_json(request)
            page_fixtures = _goal_api_fixture_items(payload)
            page_fingerprint = json.dumps(page_fixtures, sort_keys=True, default=str)
            if page_fingerprint in seen_pages:
                break
            seen_pages.add(page_fingerprint)
            raw_fixtures.extend(page_fixtures)

            pagination = payload.get("pagination")
            if not isinstance(pagination, dict) or pagination.get("hasMore") is not True:
                break
            page_count += 1
            if page_count >= 20:
                raise FixtureProviderError("Goal API returned too many fixture pages")
            try:
                page_limit = int(pagination.get("limit", 100))
            except (TypeError, ValueError) as error:
                raise FixtureProviderError("Goal API returned invalid pagination") from error
            if page_limit <= 0:
                raise FixtureProviderError("Goal API returned invalid pagination")
            offset += page_limit

        try:
            fixtures = [_goal_api_fixture(item, competition) for item in raw_fixtures]
        except (KeyError, TypeError, ValueError) as error:
            raise FixtureProviderError("Goal API returned an unexpected fixture payload") from error

        return [fixture for fixture in fixtures if fixture.kickoff_at.date() == fixture_date]

    def _request_json(self, request: Request) -> dict[str, object]:
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed provider URL
                payload = json.load(response)
        except HTTPError as error:
            detail = _goal_api_http_error_detail(error)
            raise FixtureProviderError(f"Goal API returned HTTP {error.code}: {detail}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise FixtureProviderError("Goal API request failed") from error

        if not isinstance(payload, dict):
            raise FixtureProviderError("Goal API returned an unexpected response")
        if payload.get("success") is False:
            detail = payload.get("error") or payload.get("message") or "unknown error"
            raise FixtureProviderError(f"Goal API returned an error: {detail}")
        return payload


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
                    fixture_id=str(item["fixture"]["id"]),
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


class FallbackFixtureProvider:
    """Try configured providers in order when an upstream provider fails."""

    def __init__(self, *providers: FixtureProvider) -> None:
        if not providers:
            raise ValueError("At least one fixture provider is required")
        self._providers = providers

    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
        errors: list[str] = []
        for provider in self._providers:
            try:
                return provider.list_fixtures(competition, fixture_date)
            except FixtureProviderError as error:
                errors.append(str(error))
        raise FixtureProviderError("; fallback also failed: ".join(errors))


def fixture_provider_from_environment() -> FixtureProvider:
    """Build the available provider chain, preferring Goal API."""
    providers: list[FixtureProvider] = []
    goal_api_key = os.environ.get("GOAL_API_KEY")
    api_football_key = os.environ.get("API_FOOTBALL_KEY")
    if goal_api_key:
        providers.append(GoalApiFixtureProvider(goal_api_key))
    if api_football_key:
        providers.append(ApiFootballFixtureProvider(api_football_key))
    if not providers:
        raise FixtureProviderError(
            "GOAL_API_KEY or API_FOOTBALL_KEY must be configured for live fixtures"
        )
    if len(providers) == 1:
        return providers[0]
    return FallbackFixtureProvider(*providers)


def _goal_api_fixture_items(payload: dict[str, object]) -> list[dict[str, object]]:
    raw_fixtures = payload.get("data")
    if isinstance(raw_fixtures, dict):
        raw_fixtures = raw_fixtures.get("fixtures") or raw_fixtures.get("matches")
    if not isinstance(raw_fixtures, list):
        raise FixtureProviderError("Goal API returned an unexpected fixture payload")
    return [item for item in raw_fixtures if isinstance(item, dict)]


def _goal_api_http_error_detail(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return error.reason or "request failed"
    if not isinstance(payload, dict):
        return error.reason or "request failed"
    detail = payload.get("error") or payload.get("message")
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("code")
    return str(detail or error.reason or "request failed")


def _goal_api_fixture(item: dict[str, object], competition: Competition) -> LiveFixture:
    fixture_id = item.get("id") or item.get("fixtureId") or item.get("fixture_id")
    if fixture_id is None:
        raise KeyError("fixture id")
    return LiveFixture(
        fixture_id=str(fixture_id),
        competition=competition,
        kickoff_at=_goal_api_kickoff(item),
        home_team=_goal_api_team_name(item, "home"),
        away_team=_goal_api_team_name(item, "away"),
    )


def _goal_api_kickoff(item: dict[str, object]) -> datetime:
    raw_kickoff = item.get("kickoffUtc") or item.get("kickoff_utc") or item.get("kickoffAt")
    if isinstance(raw_kickoff, str):
        parsed = datetime.fromisoformat(raw_kickoff.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    raw_date = item.get("matchDate") or item.get("match_date") or item.get("date")
    raw_time = item.get("matchTime") or item.get("match_time") or item.get("time")
    if not isinstance(raw_date, str) or not isinstance(raw_time, str):
        raise KeyError("kickoff")
    parsed = datetime.fromisoformat(f"{raw_date}T{raw_time.replace('Z', '+00:00')}")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _goal_api_team_name(item: dict[str, object], side: str) -> str:
    camel_key = f"{side}Team"
    snake_key = f"{side}_team"
    team = item.get(camel_key) or item.get(snake_key) or item.get(side)
    if isinstance(team, dict) and isinstance(team.get("name"), str):
        return team["name"]
    if isinstance(team, str):
        return team
    raise KeyError(f"{side} team")


def _season_start_year(fixture_date: date) -> int:
    """Return API-Football's starting year for a European league season."""
    return fixture_date.year if fixture_date.month >= 7 else fixture_date.year - 1
