import io
from datetime import date
from urllib.error import HTTPError

import football_predictor.live_fixtures as live_fixtures
from football_predictor.domain import Competition
from football_predictor.live_fixtures import (
    ApiFootballFixtureProvider,
    FallbackFixtureProvider,
    FixtureProviderError,
    GoalApiFixtureProvider,
    fixture_provider_from_environment,
)


def test_goal_api_provider_parses_and_filters_fixture_payload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    payload = b"""{
      "success": true,
      "data": [
        {
          "id": "fixture-123",
          "leagueId": "152",
          "kickoffUtc": "2026-10-04T15:00:00.000Z",
          "homeTeam": {"name": "Arsenal"},
          "awayTeam": {"name": "Chelsea"}
        },
        {
          "id": "fixture-456",
          "leagueId": "178",
          "kickoffUtc": "2026-10-04T19:00:00.000Z",
          "homeTeam": {"name": "Leeds United"},
          "awayTeam": {"name": "Everton"}
        }
      ],
      "pagination": {"total": 2, "limit": 50, "offset": 0, "hasMore": false}
    }"""
    requests = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        requests.append(request)
        return io.BytesIO(payload)

    monkeypatch.setattr(live_fixtures, "urlopen", fake_urlopen)

    fixtures = GoalApiFixtureProvider("test-key").list_fixtures(
        Competition.PREMIER_LEAGUE, date(2026, 10, 4)
    )

    assert [fixture.fixture_id for fixture in fixtures] == ["fixture-123"]
    assert fixtures[0].home_team == "Arsenal"
    assert fixtures[0].kickoff_at.isoformat() == "2026-10-04T15:00:00+00:00"
    assert "/fixtures/date/2026-10-04?" in requests[0].full_url
    assert "limit=50" in requests[0].full_url
    assert "offset=0" in requests[0].full_url
    assert requests[0].get_header("Authorization") == "Bearer test-key"
    assert requests[0].get_header("User-agent") == "football-prediction-engine/0.1"


def test_goal_api_provider_supports_greece_and_split_date_fields(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    payload = b"""{
      "success": true,
      "data": [{
        "id": 789,
        "league": {"apiId": 178},
        "matchDate": "2026-10-04",
        "matchTime": "17:30",
        "homeTeam": {"name": "Olympiacos"},
        "awayTeam": {"name": "Panathinaikos"}
      }],
      "pagination": {"total": 1, "limit": 50, "offset": 0, "hasMore": false}
    }"""
    requested_urls = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        requested_urls.append(request.full_url)
        return io.BytesIO(payload)

    monkeypatch.setattr(live_fixtures, "urlopen", fake_urlopen)

    fixtures = GoalApiFixtureProvider("test-key").list_fixtures(
        Competition.SUPER_LEAGUE_GREECE, date(2026, 10, 4)
    )

    assert fixtures[0].fixture_id == "789"
    assert fixtures[0].kickoff_at.isoformat() == "2026-10-04T17:30:00+00:00"
    assert "/fixtures/date/2026-10-04?" in requested_urls[0]


def test_goal_api_provider_follows_pagination_until_matching_league(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    first_page = b"""{
      "success": true,
      "data": [{"id": 1, "leagueId": 999}],
      "pagination": {"total": 2, "limit": 1, "offset": 0, "hasMore": true}
    }"""
    second_page = b"""{
      "success": true,
      "data": [{
        "id": 2,
        "leagueId": 152,
        "kickoffUtc": "2026-10-04T15:00:00Z",
        "homeTeam": {"name": "Arsenal"},
        "awayTeam": {"name": "Chelsea"}
      }],
      "pagination": {"total": 2, "limit": 1, "offset": 1, "hasMore": false}
    }"""
    requested_urls = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        requested_urls.append(request.full_url)
        return io.BytesIO(first_page if "offset=0" in request.full_url else second_page)

    monkeypatch.setattr(live_fixtures, "urlopen", fake_urlopen)

    fixtures = GoalApiFixtureProvider("test-key").list_fixtures(
        Competition.PREMIER_LEAGUE, date(2026, 10, 4)
    )

    assert [fixture.fixture_id for fixture in fixtures] == ["2"]
    assert len(requested_urls) == 2
    assert "offset=1" in requested_urls[1]


def test_goal_api_provider_exposes_safe_http_error_detail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"code":"BAD_LIMIT","message":"limit too high"}}'),
        )

    monkeypatch.setattr(live_fixtures, "urlopen", fake_urlopen)

    try:
        GoalApiFixtureProvider("test-key").list_fixtures(
            Competition.PREMIER_LEAGUE, date(2026, 10, 4)
        )
    except FixtureProviderError as error:
        assert str(error) == "Goal API returned HTTP 400: limit too high"
    else:
        raise AssertionError("Expected Goal API request to fail")


def test_api_football_provider_parses_fixture_payload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    payload = b"""{
      "errors": {},
      "response": [{
        "fixture": {"id": 123, "date": "2026-10-04T15:00:00+00:00"},
        "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}}
      }]
    }"""
    requested_urls = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        requested_urls.append(request.full_url)
        return io.BytesIO(payload)

    monkeypatch.setattr(live_fixtures, "urlopen", fake_urlopen)

    fixtures = ApiFootballFixtureProvider("test-key").list_fixtures(
        Competition.PREMIER_LEAGUE, date(2026, 10, 4)
    )

    assert fixtures[0].fixture_id == "123"
    assert fixtures[0].home_team == "Arsenal"
    assert fixtures[0].competition is Competition.PREMIER_LEAGUE
    assert "league=39" in requested_urls[0]
    assert "season=2026" in requested_urls[0]
    assert "date=2026-10-04" in requested_urls[0]


def test_api_football_season_uses_previous_year_before_july() -> None:
    assert live_fixtures._season_start_year(date(2026, 5, 1)) == 2025


def test_provider_chain_prefers_goal_api_from_environment(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GOAL_API_KEY", "goal-key")
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)

    assert isinstance(fixture_provider_from_environment(), GoalApiFixtureProvider)


def test_fallback_provider_uses_second_provider_after_error() -> None:
    class BrokenProvider:
        def list_fixtures(self, competition, fixture_date):  # type: ignore[no-untyped-def]
            raise FixtureProviderError("primary failed")

    class WorkingProvider:
        def list_fixtures(self, competition, fixture_date):  # type: ignore[no-untyped-def]
            return []

    provider = FallbackFixtureProvider(BrokenProvider(), WorkingProvider())

    assert provider.list_fixtures(Competition.PREMIER_LEAGUE, date(2026, 10, 4)) == []
