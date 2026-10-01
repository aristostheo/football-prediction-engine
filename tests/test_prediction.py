import asyncio
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from football_predictor.api import create_app
from football_predictor.domain import Competition
from football_predictor.live_fixtures import LiveFixture
from football_predictor.prediction import FixtureToPredict, PredictionEngine


@pytest.fixture(scope="module")
def prediction_engine() -> PredictionEngine:
    data_path = Path(__file__).parents[1] / "data/model/historical_matches.csv.gz"
    return PredictionEngine.from_csv(data_path)


@pytest.mark.parametrize("home_team", ["Nottingham Forest", "Nottingham Forrest"])
def test_predict_resolves_provider_team_names_to_historical_labels(
    prediction_engine: PredictionEngine, home_team: str
) -> None:
    prediction = prediction_engine.predict(
        FixtureToPredict(
            competition=Competition.PREMIER_LEAGUE,
            kickoff_date=date(2026, 10, 18),
            home_team=home_team,
            away_team="Arsenal",
        )
    )

    assert prediction.fixture.home_team == "Nottingham Forest FC"
    assert prediction.fixture.away_team == "Arsenal FC"
    assert (
        prediction.home_win_probability
        + prediction.draw_probability
        + prediction.away_win_probability
    ) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("home_team", "away_team", "expected_home", "expected_away"),
    [
        ("AEK Athens", "Olympiacos", "AEK Athen", "Olympiakos Piraeus"),
        ("PAOK", "Aris", "PAOK Saloniki", "Aris Saloniki"),
        ("OFI", "Asteras Aktor", "OFI Heraklion", "Asteras Tripolis"),
    ],
)
def test_predict_resolves_greek_provider_names(
    prediction_engine: PredictionEngine,
    home_team: str,
    away_team: str,
    expected_home: str,
    expected_away: str,
) -> None:
    prediction = prediction_engine.predict(
        FixtureToPredict(
            competition=Competition.SUPER_LEAGUE_GREECE,
            kickoff_date=date(2026, 10, 18),
            home_team=home_team,
            away_team=away_team,
        )
    )
    assert prediction.fixture.home_team == expected_home
    assert prediction.fixture.away_team == expected_away
    assert sum(
        (
            prediction.home_win_probability,
            prediction.draw_probability,
            prediction.away_win_probability,
        )
    ) == pytest.approx(1.0)


def test_predict_explains_missing_history_for_a_recognized_club(
    prediction_engine: PredictionEngine,
) -> None:
    with pytest.raises(ValueError, match="No historical results available.*Kalamata"):
        prediction_engine.predict(
            FixtureToPredict(
                competition=Competition.SUPER_LEAGUE_GREECE,
                kickoff_date=date(2026, 10, 18),
                home_team="Kalamata FC",
                away_team="Olympiacos",
            )
        )


def test_predict_rejects_two_aliases_of_the_same_club(prediction_engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="different clubs"):
        prediction_engine.predict(
            FixtureToPredict(
                competition=Competition.PREMIER_LEAGUE,
                kickoff_date=date(2026, 10, 18),
                home_team="Manchester United",
                away_team="Man Utd",
            )
        )


@pytest.mark.parametrize(
    ("competition", "home", "away", "expected_home"),
    [
        (Competition.PREMIER_LEAGUE, "Nottingham Forest", "Arsenal", "Nottingham Forest FC"),
        (Competition.SUPER_LEAGUE_GREECE, "AEK Athens", "Olympiacos", "AEK Athen"),
    ],
)
def test_selected_live_fixture_can_be_submitted_to_prediction_api(
    prediction_engine: PredictionEngine,
    competition: Competition,
    home: str,
    away: str,
    expected_home: str,
) -> None:
    class Provider:
        def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
            return [
                LiveFixture(
                    fixture_id="example",
                    competition=competition,
                    kickoff_at=datetime(2026, 10, 18, 15),
                    home_team=home,
                    away_team=away,
                )
            ]

    async def exercise() -> None:
        app = create_app(engine=prediction_engine, fixture_provider=Provider())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/fixtures", params={"competition": competition.value, "date": "2026-10-18"}
            )
            assert response.status_code == 200
            fixture = response.json()[0]
            result = await client.post(
                "/predict",
                json={
                    "competition": fixture["competition"],
                    "kickoff_date": fixture["kickoff_at"][:10],
                    "home_team": fixture["home_team"],
                    "away_team": fixture["away_team"],
                },
            )
            assert result.status_code == 200, result.text
            assert result.json()["home_team"] == expected_home

    asyncio.run(exercise())
