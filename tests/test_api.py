import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from football_predictor.api import PredictionRequest, ScorecardResultsRequest, create_app
from football_predictor.domain import Competition
from football_predictor.live_fixtures import LiveFixture
from football_predictor.prediction import FixtureToPredict, MatchPrediction, PredictionEngine


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
            forecasted_at=datetime(2025, 5, 25, tzinfo=UTC),
            model_probabilities=(0.5, 0.25, 0.25),
            market_probabilities=None,
        )

    def find_results(self, fixtures):  # type: ignore[no-untyped-def]
        return {fixture[0]: "H" for fixture in fixtures}


class StubFixtureProvider:
    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
        return [
            LiveFixture(
                fixture_id="123",
                competition=competition,
                kickoff_at=datetime(2025, 6, 1, 15, 0),
                home_team="Arsenal FC",
                away_team="Chelsea FC",
            )
        ]


@pytest.mark.parametrize("custom_path", [None, "custom/history.csv"])
def test_api_loads_bundled_history_by_default_and_honors_override(
    monkeypatch: pytest.MonkeyPatch, custom_path: str | None
) -> None:
    monkeypatch.delenv("HISTORICAL_MATCHES_PATH", raising=False)
    if custom_path:
        monkeypatch.setenv("HISTORICAL_MATCHES_PATH", custom_path)
    loaded_paths: list[Path] = []

    def load_history(path: Path) -> StubEngine:
        loaded_paths.append(path)
        if not custom_path:
            assert path.is_file(), "default prediction data must ship with the repository"
        return StubEngine()

    monkeypatch.setattr(PredictionEngine, "from_csv", load_history)

    app = create_app()
    predict = next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/predict"
    )
    request = PredictionRequest(
        competition="premier_league",
        kickoff_date="2026-10-18",
        home_team="Arsenal FC",
        away_team="Chelsea FC",
    )
    for _ in range(2):
        response = predict(request)
        assert response.home_win_probability == 0.5
    assert loaded_paths == [Path(custom_path or "data/model/historical_matches.csv.gz")]


def test_api_exposes_health_fixtures_and_predictions() -> None:
    app = create_app(engine=StubEngine(), fixture_provider=StubFixtureProvider())
    routes = {getattr(route, "path", None): route.endpoint for route in app.routes}
    assert asyncio.run(routes["/health"]()) == {"status": "ok"}

    fixtures = routes["/fixtures"](Competition.PREMIER_LEAGUE, date(2025, 6, 1))
    assert fixtures[0].fixture_id == "123"

    prediction = routes["/predict"](
        PredictionRequest(
            competition=Competition.PREMIER_LEAGUE,
            kickoff_date=date(2025, 6, 1),
            home_team="Arsenal FC",
            away_team="Chelsea FC",
        )
    )
    assert prediction.home_win_probability == 0.5
    assert prediction.model_home_win_probability == 0.5

    results = routes["/scorecard/results"](
        ScorecardResultsRequest(
            fixtures=[
                {
                    "id": "forecast-1",
                    "competition": "premier_league",
                    "kickoff_date": "2025-06-01",
                    "home_team": "Arsenal FC",
                    "away_team": "Chelsea FC",
                }
            ]
        )
    )
    assert results[0].id == "forecast-1"
    assert results[0].result == "H"


def test_api_rejects_partial_market_odds() -> None:
    async def exercise() -> None:
        app = create_app(engine=StubEngine())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/predict",
                json={
                    "competition": "premier_league",
                    "kickoff_date": "2025-06-01",
                    "home_team": "Arsenal FC",
                    "away_team": "Chelsea FC",
                    "odds_home": 2.0,
                },
            )
            assert response.status_code == 422
            assert "all three decimal odds" in response.text

    asyncio.run(exercise())


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
