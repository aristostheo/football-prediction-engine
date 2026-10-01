import asyncio
from datetime import date, datetime
from pathlib import Path

import httpx

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
    async def exercise_api() -> None:
        app = create_app(engine=StubEngine(), fixture_provider=StubFixtureProvider())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get("/health")).json() == {"status": "ok"}
            fixtures = await client.get(
                "/fixtures?competition=premier_league&date=2025-06-01"
            )
            assert fixtures.status_code == 200
            assert fixtures.json()[0]["fixture_id"] == 123

            response = await client.post(
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

    asyncio.run(exercise_api())


def test_api_serves_built_dashboard(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<main>Match Forecast</main>")
    (tmp_path / "assets" / "app.js").write_text("console.log('ready')")

    async def exercise_dashboard() -> None:
        app = create_app(engine=StubEngine(), web_dist_path=tmp_path)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert "Match Forecast" in (await client.get("/")).text
            assert (await client.get("/assets/app.js")).status_code == 200
            assert "Match Forecast" in (await client.get("/performance")).text

    asyncio.run(exercise_dashboard())
