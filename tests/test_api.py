from datetime import date, datetime

from fastapi.testclient import TestClient

from football_predictor.api import create_app
from football_predictor.domain import Competition
from football_predictor.live_fixtures import LiveFixture
from football_predictor.prediction import FixtureToPredict, MatchPrediction


class StubEngine:
    def predict(self, fixture: FixtureToPredict) -> MatchPrediction:
        return MatchPrediction(
            fixture=fixture,
            home_win_probability=0.5,
            draw_probability=0.25,
            away_win_probability=0.25,
            model_policy="elo",
            history_through=date(2025, 5, 25),
            history_age_days=7,
        )


class StubFixtureProvider:
    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
        return [
            LiveFixture(
                fixture_id=123,
                competition=competition,
                kickoff_at=datetime(2025, 6, 1, 15, 0),
                home_team="Arsenal FC",
                away_team="Chelsea FC",
            )
        ]


def test_api_exposes_health_fixtures_and_predictions() -> None:
    client = TestClient(create_app(engine=StubEngine(), fixture_provider=StubFixtureProvider()))

    assert client.get("/health").json() == {"status": "ok"}
    fixtures = client.get("/fixtures?competition=premier_league&date=2025-06-01")
    assert fixtures.status_code == 200
    assert fixtures.json()[0]["fixture_id"] == 123

    response = client.post(
        "/predict",
        json={
            "competition": "premier_league",
            "kickoff_date": "2025-06-01",
            "home_team": "Arsenal FC",
            "away_team": "Chelsea FC",
        },
    )
    assert response.status_code == 200
    assert response.json()["home_win_probability"] == 0.5
