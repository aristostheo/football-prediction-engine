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
            market_probabilities=(0.6, 0.25, 0.15) if fixture.odds_home is not None else None,
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

    def find_scores(self, fixtures):  # type: ignore[no-untyped-def]
        return {fixture[0]: (2, 1) for fixture in fixtures}


class StubFixtureProvider:
    def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
        return [
            LiveFixture(
                fixture_id="123",
                competition=competition,
                kickoff_at=datetime(2025, 6, 1, 15, 0),
                home_team="Arsenal FC",
                away_team="Chelsea FC",
                home_badge_url="https://media.goal-api.com/badges/arsenal.png",
                away_badge_url="https://media.goal-api.com/badges/chelsea.png",
            )
        ]

    def list_team_badges(self, competition: Competition) -> dict[str, str]:
        return {"Arsenal": "https://media.goal-api.com/badges/arsenal.png"}


class MissingResultsEngine(StubEngine):
    def find_results(self, fixtures):
        return {fixture[0]: None for fixture in fixtures}


def journal_request(days):
    return ScorecardResultsRequest(fixtures=[
        {"id": str(index), "competition": "premier_league", "kickoff_date": day,
         "home_team": "Arsenal", "away_team": "Chelsea"}
        for index, day in enumerate(days)
    ])


def app_routes(app):
    return {getattr(route, "path", None): route.endpoint for route in app.routes}


def test_old_journal_backfills_in_bounded_batches_and_reuses_fixture_discovery():
    calls = []

    class Provider(StubFixtureProvider):
        def list_fixtures(self, competition, fixture_date):
            calls.append(fixture_date)
            return [LiveFixture(
                fixture_id=fixture_date.isoformat(), competition=competition,
                kickoff_at=datetime.combine(fixture_date, datetime.min.time(), UTC),
                home_team="Arsenal FC", away_team="Chelsea FC",
                result="D", home_goals=0, away_goals=0, status="FINISHED",
            )]

    routes = app_routes(create_app(engine=MissingResultsEngine(), fixture_provider=Provider()))
    days = [datetime.now(UTC).date() - timedelta(days=40 + index) for index in range(12)]
    routes["/fixtures"](Competition.PREMIER_LEAGUE, days[0])
    request = journal_request(days)
    first = routes["/scorecard/results"](request)
    assert len(calls) == 9  # One discovery call, plus at most eight new journal lookups.
    assert sum(item.check_status == "confirmed" for item in first) == 9
    assert sum(item.check_status == "deferred" for item in first) == 3
    assert all((item.home_goals, item.away_goals) == (0, 0)
               for item in first if item.result == "D")
    second = routes["/scorecard/results"](request)
    assert len(calls) == 12
    assert all(item.check_status == "confirmed" for item in second)
    assert all(item.source == "live_provider" for item in second)
    routes["/scorecard/results"](request)
    assert len(calls) == 12


def test_journal_checks_local_results_before_provider_and_skips_future():
    class NeverProvider:
        def list_fixtures(self, *_):
            pytest.fail("local or future results must not trigger an HTTP lookup")

    days = [datetime.now(UTC).date() - timedelta(days=60)]
    routes = app_routes(create_app(engine=StubEngine(), fixture_provider=NeverProvider()))
    result = routes["/scorecard/results"](journal_request(days))[0]
    assert result.check_status == "confirmed"
    assert result.source == "bundled_history"
    routes = app_routes(create_app(engine=MissingResultsEngine(), fixture_provider=NeverProvider()))
    result = routes["/scorecard/results"](
        journal_request([datetime.now(UTC).date() + timedelta(days=2)])
    )[0]
    assert result.check_status == "pending"


def test_journal_failures_are_reported_and_not_retried_immediately():
    from football_predictor.live_fixtures import FixtureProviderError

    calls = []

    class FailingProvider:
        def list_fixtures(self, competition, day):
            calls.append(day)
            raise FixtureProviderError("provider unavailable")

    routes = app_routes(create_app(
        engine=MissingResultsEngine(), fixture_provider=FailingProvider()
    ))
    request = journal_request([datetime.now(UTC).date() - timedelta(days=60)])
    for _ in range(2):
        result = routes["/scorecard/results"](request)[0]
        assert result.check_status == "unavailable"
        assert result.result is result.home_goals is result.away_goals is None
    assert len(calls) == 1


@pytest.mark.parametrize("changes", [
    {"status": "LIVE"}, {"status": "POSTPONED"}, {"result": "A"},
    {"home_goals": -1}, {"home_goals": True}, {"away_goals": None},
    {"home_team": "Chelsea", "away_team": "Arsenal"},
    {"competition": Competition.LA_LIGA},
    {"kickoff_at": datetime.now(UTC) + timedelta(days=1)},
])
def test_journal_rejects_unfinished_inconsistent_or_wrong_fixture_results(changes):
    day = datetime.now(UTC).date() - timedelta(days=60)
    fixture = dict(
        fixture_id="finished", competition=Competition.PREMIER_LEAGUE,
        kickoff_at=datetime.combine(day, datetime.min.time(), UTC),
        home_team="Arsenal", away_team="Chelsea", status="FINISHED",
        result="H", home_goals=2, away_goals=1,
    )
    fixture.update(changes)

    class Provider:
        def list_fixtures(self, *_):
            return [LiveFixture(**fixture)]

    routes = app_routes(create_app(engine=MissingResultsEngine(), fixture_provider=Provider()))
    result = routes["/scorecard/results"](journal_request([day]))[0]
    assert result.check_status == "pending"
    assert result.result is result.home_goals is result.away_goals is None


def test_journal_goal_http_budget_is_shared_across_requests(monkeypatch):
    import io

    from football_predictor import live_fixtures

    calls = []

    def respond(request, timeout):
        calls.append(request.full_url)
        return io.BytesIO(b'{"success": true, "data": []}')

    monkeypatch.setattr(live_fixtures, "urlopen", respond)
    routes = app_routes(create_app(
        engine=MissingResultsEngine(),
        fixture_provider=live_fixtures.GoalApiFixtureProvider("test-only"),
        journal_goal_daily_limit=10,
    ))
    days = [datetime.now(UTC).date() - timedelta(days=40 + index) for index in range(20)]
    request = journal_request(days)
    first = routes["/scorecard/results"](request)
    assert len(calls) == 8
    assert sum(item.check_status == "deferred" for item in first) == 12
    second = routes["/scorecard/results"](request)
    assert len(calls) == 10
    assert sum(item.check_status == "deferred" for item in second) == 10
    routes["/scorecard/results"](request)
    assert len(calls) == 10


@pytest.mark.parametrize("custom_path", [None, "custom/history.csv"])
def test_api_loads_bundled_history_by_default_and_honors_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, custom_path: str | None
) -> None:
    from football_predictor import history_paths

    monkeypatch.setattr(history_paths, "LOCAL_HISTORY", tmp_path / "absent-local.csv.gz")
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
        route.endpoint for route in app.routes if getattr(route, "path", None) == "/predict"
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
    assert routes["/team-badges"](Competition.PREMIER_LEAGUE) == {
        "Arsenal FC": "https://media.goal-api.com/badges/arsenal.png"
    }

    fixtures = routes["/fixtures"](Competition.PREMIER_LEAGUE, date(2025, 6, 1))
    assert fixtures[0].fixture_id == "123"
    assert fixtures[0].home_badge_url == "https://media.goal-api.com/badges/arsenal.png"

    prediction = routes["/predict"](
        PredictionRequest(
            competition=Competition.PREMIER_LEAGUE,
            kickoff_date=date(2025, 6, 1),
            home_team="Arsenal FC",
            away_team="Chelsea FC",
            odds_home=1.7,
            odds_draw=3.5,
            odds_away=5.0,
        )
    )
    assert prediction.home_win_probability == 0.5
    assert prediction.model_home_win_probability == 0.5
    assert prediction.market_home_win_probability == 0.6
    assert prediction.market_away_win_probability == 0.15
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


def test_api_caches_fixture_dates_and_team_badges() -> None:
    class CountingProvider(StubFixtureProvider):
        fixture_calls = 0
        badge_calls = 0

        def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
            self.fixture_calls += 1
            return super().list_fixtures(competition, fixture_date)

        def list_team_badges(self, competition: Competition) -> dict[str, str]:
            self.badge_calls += 1
            return super().list_team_badges(competition)

    provider = CountingProvider()
    routes = {
        getattr(route, "path", None): route.endpoint
        for route in create_app(engine=StubEngine(), fixture_provider=provider).routes
    }

    for _ in range(2):
        routes["/fixtures"](Competition.PREMIER_LEAGUE, date(2025, 6, 1))
        routes["/team-badges"](Competition.PREMIER_LEAGUE)

    assert provider.fixture_calls == 1
    assert provider.badge_calls == 1


def test_scorecard_checks_live_provider_for_recent_results_missing_from_history() -> None:
    match_date = datetime.now(UTC).date() - timedelta(days=1)
    provider_calls: list[tuple[Competition, date]] = []

    class PendingResultsEngine(StubEngine):
        def find_results(self, fixtures):  # type: ignore[no-untyped-def]
            return {fixture[0]: None for fixture in fixtures}

    class FinishedFixtureProvider(StubFixtureProvider):
        def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
            provider_calls.append((competition, fixture_date))
            return [
                LiveFixture(
                    fixture_id="finished-123",
                    competition=competition,
                    kickoff_at=datetime.combine(fixture_date, datetime.min.time(), UTC),
                    home_team="Arsenal FC",
                    away_team="Chelsea FC",
                    result="H",
                    status="FINISHED",
                    home_goals=2,
                    away_goals=1,
                )
            ]

    app = create_app(engine=PendingResultsEngine(), fixture_provider=FinishedFixtureProvider())
    endpoint = next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/scorecard/results"
    )

    results = endpoint(
        ScorecardResultsRequest(
            fixtures=[
                {
                    "id": "forecast-recent",
                    "competition": "premier_league",
                    "kickoff_date": match_date,
                    "home_team": "Arsenal FC",
                    "away_team": "Chelsea FC",
                }
            ]
        )
    )

    assert results[0].result == "H"
    assert (results[0].home_goals, results[0].away_goals) == (2, 1)
    assert results[0].source == "live_provider"
    assert provider_calls == [(Competition.PREMIER_LEAGUE, match_date)]


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
        route.endpoint for route in app.routes if getattr(route, "path", None) == "/fixtures/next"
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
        def get_match_odds(self, competition, home_team, away_team, kickoff_at):  # type: ignore[no-untyped-def]
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

    app = create_app(engine=StubEngine(), market_odds_provider=StubOddsProvider())  # type: ignore[arg-type]
    endpoint = next(
        route.endpoint for route in app.routes if getattr(route, "path", None) == "/odds"
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


def test_journal_returns_final_score_and_source_without_changing_prediction() -> None:
    app = create_app(engine=StubEngine(), fixture_provider=StubFixtureProvider())
    routes = {getattr(route, "path", None): route.endpoint for route in app.routes}
    response = routes["/scorecard/results"](
        ScorecardResultsRequest(
            fixtures=[
                {
                    "id": "original-forecast",
                    "competition": "premier_league",
                    "kickoff_date": "2025-06-01",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                }
            ]
        )
    )[0]
    assert (response.result, response.home_goals, response.away_goals) == ("H", 2, 1)
    assert response.source == "bundled_history"


def test_journal_never_exposes_unconfirmed_scores() -> None:
    class PendingEngine(StubEngine):
        def find_results(self, fixtures):  # type: ignore[no-untyped-def]
            return {fixture[0]: None for fixture in fixtures}

    app = create_app(engine=PendingEngine(), fixture_provider=StubFixtureProvider())
    endpoint = next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/scorecard/results"
    )
    response = endpoint(
        ScorecardResultsRequest(
            fixtures=[
                {
                    "id": "pending",
                    "competition": "premier_league",
                    "kickoff_date": "2025-06-01",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                }
            ]
        )
    )[0]
    assert response.result is None
    assert response.home_goals is None
    assert response.away_goals is None
    assert response.source is None


def test_next_fixture_skips_postponed_and_cancelled_matches() -> None:
    match_day = datetime.now(UTC).date() + timedelta(days=1)

    class MixedProvider(StubFixtureProvider):
        def list_fixtures(self, competition, fixture_date):  # type: ignore[no-untyped-def]
            return [
                LiveFixture(
                    fixture_id=status,
                    competition=competition,
                    kickoff_at=datetime.combine(fixture_date, datetime.min.time(), UTC)
                    + timedelta(hours=index + 12),
                    home_team="Arsenal",
                    away_team="Chelsea",
                    status=status,
                )
                for index, status in enumerate(["POSTPONED", "CANC", "SCHEDULED"])
            ]

    app = create_app(engine=StubEngine(), fixture_provider=MixedProvider())
    endpoint = next(
        route.endpoint for route in app.routes if getattr(route, "path", None) == "/fixtures/next"
    )
    response = endpoint(Competition.PREMIER_LEAGUE, match_day, 21)
    assert response.fixture_id == "SCHEDULED"
    assert response.home_team == "Arsenal FC"
    assert response.away_team == "Chelsea FC"


def test_api_loads_synced_local_history_after_restart(monkeypatch, tmp_path):
    from football_predictor import history_paths

    local = tmp_path / "synced.csv.gz"
    local.write_bytes(b"complete local snapshot")
    monkeypatch.setattr(history_paths, "LOCAL_HISTORY", local)
    monkeypatch.delenv("HISTORICAL_MATCHES_PATH", raising=False)
    loaded = []

    def load_history(path):
        loaded.append(path)
        return StubEngine()

    monkeypatch.setattr(PredictionEngine, "from_csv", load_history)
    app = create_app()
    predict = next(
        route.endpoint for route in app.routes if getattr(route, "path", None) == "/predict"
    )
    predict(
        PredictionRequest(
            competition="premier_league",
            kickoff_date="2026-10-18",
            home_team="Arsenal FC",
            away_team="Chelsea FC",
        )
    )
    assert loaded == [local]
