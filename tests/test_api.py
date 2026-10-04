import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from football_predictor.api import PredictionRequest, ScorecardResultsRequest, create_app
from football_predictor.domain import Competition
from football_predictor.live_fixtures import LiveFixture
from football_predictor.prediction import (
    FixtureToPredict,
    MatchPrediction,
    PredictionComponents,
    PredictionContext,
    PredictionEngine,
)


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
            context=PredictionContext(
                home_elo=1500,
                away_elo=1500,
                home_form_matches=5,
                away_form_matches=5,
                home_form_points_per_match=1.5,
                away_form_points_per_match=1.2,
                home_form_goals_for_per_match=1.4,
                away_form_goals_for_per_match=1.1,
                home_form_goals_against_per_match=1.0,
                away_form_goals_against_per_match=1.3,
                home_venue_points_per_match=1.8,
                away_venue_points_per_match=1.0,
            ),
            components=PredictionComponents(
                elo_probabilities=(0.5, 0.25, 0.25),
                goal_probabilities=None,
                core_model_probabilities=(0.5, 0.25, 0.25),
                home_goal_rate=None,
                away_goal_rate=None,
                elo_weight=1.0,
                base_model_weight=1.0,
                league_prior_probabilities=None,
            ),
        )

    def available_teams(self, competition):  # type: ignore[no-untyped-def]
        return ["Arsenal FC", "Chelsea FC"]

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
    assert routes["/teams"](Competition.PREMIER_LEAGUE) == ["Arsenal FC", "Chelsea FC"]

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
    assert prediction.context.home_elo == 1500
    assert prediction.components.elo_probabilities == (0.5, 0.25, 0.25)

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


def test_next_fixture_scans_forward_and_returns_the_first_future_match() -> None:
    start = datetime.now(UTC).date() + timedelta(days=1)
    target_date = start + timedelta(days=2)
    scanned: list[date] = []

    class ScanningProvider:
        def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
            scanned.append(fixture_date)
            if fixture_date != target_date:
                return []
            return [
                LiveFixture(
                    fixture_id="next-1",
                    competition=competition,
                    kickoff_at=datetime.combine(fixture_date, datetime.min.time(), UTC)
                    + timedelta(hours=18),
                    home_team="Arsenal FC",
                    away_team="Chelsea FC",
                )
            ]

    app = create_app(engine=StubEngine(), fixture_provider=ScanningProvider())
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", None) == "/fixtures/next"
    )
    fixture = endpoint(Competition.PREMIER_LEAGUE, start, 5)

    assert fixture is not None
    assert fixture.fixture_id == "next-1"
    assert scanned == [start, start + timedelta(days=1), target_date]


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


def test_live_odds_endpoint_returns_quote_metadata() -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    class StubOddsProvider:
        def get_match_odds(
            self, competition, home_team, away_team, kickoff_at
        ):  # type: ignore[no-untyped-def]
            assert competition is Competition.PREMIER_LEAGUE
            assert home_team == "Arsenal"
            assert away_team == "Chelsea"
            return SimpleNamespace(
                home_fair_odds=1.85,
                draw_fair_odds=4.1,
                away_fair_odds=4.5,
                bookmaker_count=6,
                fetched_at=datetime.now(UTC),
            )

    app = create_app(
        engine=StubEngine(), market_odds_provider=StubOddsProvider()
    )  # type: ignore[arg-type]
    endpoint = next(
        route.endpoint for route in app.routes
        if getattr(route, "path", None) == "/odds"
    )
    response = endpoint(
        Competition.PREMIER_LEAGUE,
        "fixture-1",
        "Arsenal",
        "Chelsea",
        datetime.now(UTC) + timedelta(days=2),
    )

    assert response.home_fair_odds == 1.85
    assert response.bookmaker_count == 6
    assert response.source.startswith("The Odds API")


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
