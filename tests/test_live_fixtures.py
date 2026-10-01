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
    monkeypatch.setattr(live_fixtures, "urlopen", lambda request, timeout: io.BytesIO(payload))

    fixtures = ApiFootballFixtureProvider("test-key").list_fixtures(
        Competition.PREMIER_LEAGUE, date(2026, 10, 4)
    )

    assert fixtures[0].fixture_id == 123
    assert fixtures[0].home_team == "Arsenal"
    assert fixtures[0].competition is Competition.PREMIER_LEAGUE
