import io
from datetime import date

import football_predictor.live_fixtures as live_fixtures
from football_predictor.domain import Competition
from football_predictor.live_fixtures import ApiFootballFixtureProvider


def test_api_football_provider_parses_fixture_payload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    payload = b'''{
      "errors": {},
      "response": [{
        "fixture": {"id": 123, "date": "2026-10-04T15:00:00+00:00"},
        "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}}
      }]
    }'''
    requested_urls = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        requested_urls.append(request.full_url)
        return io.BytesIO(payload)

    monkeypatch.setattr(live_fixtures, "urlopen", fake_urlopen)

    fixtures = ApiFootballFixtureProvider("test-key").list_fixtures(
        Competition.PREMIER_LEAGUE, date(2026, 10, 4)
    )

    assert fixtures[0].fixture_id == 123
    assert fixtures[0].home_team == "Arsenal"
    assert fixtures[0].competition is Competition.PREMIER_LEAGUE
    assert "league=39" in requested_urls[0]
    assert "season=2026" in requested_urls[0]
    assert "date=2026-10-04" in requested_urls[0]


def test_api_football_season_uses_previous_year_before_july() -> None:
    assert live_fixtures._season_start_year(date(2026, 5, 1)) == 2025
