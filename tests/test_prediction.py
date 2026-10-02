from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import pytest

from football_predictor.api import PredictionRequest, create_app
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
            kickoff_date=prediction_engine.latest_result_date(Competition.PREMIER_LEAGUE)
            + timedelta(days=1),
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


def test_market_odds_use_margin_removed_probabilities(
    prediction_engine: PredictionEngine,
) -> None:
    prediction = prediction_engine.predict(
        FixtureToPredict(
            competition=Competition.PREMIER_LEAGUE,
            kickoff_date=prediction_engine.latest_result_date(Competition.PREMIER_LEAGUE)
            + timedelta(days=1),
            home_team="Arsenal",
            away_team="Chelsea",
            odds_home=2.0,
            odds_draw=3.0,
            odds_away=4.0,
        )
    )

    assert prediction.model_policy == "market_implied_odds"
    assert prediction.home_win_probability == pytest.approx(6 / 13)
    assert prediction.draw_probability == pytest.approx(4 / 13)
    assert prediction.away_win_probability == pytest.approx(3 / 13)
    assert prediction.market_probabilities == pytest.approx((6 / 13, 4 / 13, 3 / 13))
    assert sum(prediction.model_probabilities) == pytest.approx(1.0)


def test_prediction_rejects_a_kickoff_that_has_already_passed(
    prediction_engine: PredictionEngine,
) -> None:
    with pytest.raises(ValueError, match="after kickoff"):
        prediction_engine.predict(
            FixtureToPredict(
                competition=Competition.PREMIER_LEAGUE,
                kickoff_date=prediction_engine.latest_result_date(Competition.PREMIER_LEAGUE)
                + timedelta(days=1),
                kickoff_at=datetime.now(UTC) - timedelta(minutes=1),
                home_team="Arsenal",
                away_team="Chelsea",
            )
        )


def test_result_lookup_returns_only_exact_completed_fixture_keys(
    prediction_engine: PredictionEngine,
) -> None:
    history = pd.read_csv(Path(__file__).parents[1] / "data/model/historical_matches.csv.gz")
    row = history.iloc[0]
    match_date = date.fromisoformat(str(row["match_date"]))

    results = prediction_engine.find_results(
        [
            (
                "known",
                str(row["competition"]),
                match_date,
                str(row["home_team"]),
                str(row["away_team"]),
            ),
            (
                "wrong-venue-order",
                str(row["competition"]),
                match_date,
                str(row["away_team"]),
                str(row["home_team"]),
            ),
        ]
    )

    assert results["known"] == row["result"]
    assert results["wrong-venue-order"] is None


def test_market_odds_require_all_three_prices(prediction_engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="all three decimal odds"):
        prediction_engine.predict(
            FixtureToPredict(
                competition=Competition.PREMIER_LEAGUE,
                kickoff_date=prediction_engine.latest_result_date(Competition.PREMIER_LEAGUE)
                + timedelta(days=1),
                home_team="Arsenal",
                away_team="Chelsea",
                odds_home=2.0,
            )
        )


@pytest.mark.parametrize(
    ("home_team", "away_team", "expected_home", "expected_away"),
    [
        ("AEK Athens", "Olympiacos", "AEK Athen", "Olympiakos Piraeus"),
        ("PAOK", "Aris", "PAOK Saloniki", "Aris Saloniki"),
        ("OFI", "Asteras Aktor", "OFI Heraklion", "Asteras Tripolis"),
        ("Kalamata FC", "Iraklis 1908", "Kalamata", "Iraklis"),
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
            kickoff_date=prediction_engine.latest_result_date(Competition.SUPER_LEAGUE_GREECE)
            + timedelta(days=1),
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


def test_predict_supports_promoted_club_after_its_first_recorded_matches(
    prediction_engine: PredictionEngine,
) -> None:
    prediction = prediction_engine.predict(
        FixtureToPredict(
            competition=Competition.SUPER_LEAGUE_GREECE,
            kickoff_date=prediction_engine.latest_result_date(Competition.SUPER_LEAGUE_GREECE)
            + timedelta(days=1),
            home_team="Kalamata FC",
            away_team="Olympiacos",
        )
    )
    assert prediction.fixture.home_team == "Kalamata"


def test_recognized_team_without_history_uses_a_conservative_prior() -> None:
    teams = ["AEK Athen", "Olympiakos Piraeus", "PAOK Saloniki", "Aris Saloniki"]
    rows = []
    for index in range(120):
        home_goals, away_goals = ((2, 0), (1, 1), (0, 2))[index % 3]
        rows.append(
            {
                "match_date": date(2020, 1, 1) + timedelta(days=index),
                "competition": Competition.SUPER_LEAGUE_GREECE.value,
                "season": "2019-20",
                "home_team": teams[index % len(teams)],
                "away_team": teams[(index + 1) % len(teams)],
                "home_goals": home_goals,
                "away_goals": away_goals,
                "result": ("H", "D", "A")[index % 3],
            }
        )
    engine = PredictionEngine(pd.DataFrame(rows))
    fixture = FixtureToPredict(
        competition=Competition.SUPER_LEAGUE_GREECE,
        kickoff_date=date(2020, 5, 1),
        home_team="Kalamata FC",
        away_team="Olympiacos",
    )

    prediction = engine.predict(fixture)

    assert prediction.model_policy == "elo_promoted_prior"
    assert prediction.fixture.home_team == "Kalamata"
    assert sum(
        (
            prediction.home_win_probability,
            prediction.draw_probability,
            prediction.away_win_probability,
        )
    ) == pytest.approx(1.0)


def test_prediction_still_rejects_unregistered_club_names() -> None:
    history = pd.read_csv(Path(__file__).parents[1] / "data/model/historical_matches.csv.gz")
    engine = PredictionEngine(history)
    with pytest.raises(ValueError, match="Unrecognized teams"):
        engine.predict(
            FixtureToPredict(
                competition=Competition.PREMIER_LEAGUE,
                kickoff_date=engine.latest_result_date(Competition.PREMIER_LEAGUE)
                + timedelta(days=1),
                home_team="Made Up FC",
                away_team="Arsenal",
            )
        )


def test_predict_rejects_two_aliases_of_the_same_club(prediction_engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="different clubs"):
        prediction_engine.predict(
            FixtureToPredict(
                competition=Competition.PREMIER_LEAGUE,
                kickoff_date=prediction_engine.latest_result_date(Competition.PREMIER_LEAGUE)
                + timedelta(days=1),
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
def test_selected_live_fixture_can_be_normalized_by_prediction_endpoint(
    prediction_engine: PredictionEngine,
    competition: Competition,
    home: str,
    away: str,
    expected_home: str,
) -> None:
    fixture_date = prediction_engine.latest_result_date(competition) + timedelta(days=1)

    class Provider:
        def list_fixtures(self, competition: Competition, fixture_date: date) -> list[LiveFixture]:
            return [
                LiveFixture(
                    fixture_id="example",
                    competition=competition,
                    kickoff_at=datetime.combine(fixture_date, time(15)),
                    home_team=home,
                    away_team=away,
                )
            ]

    app = create_app(engine=prediction_engine, fixture_provider=Provider())
    endpoints = {
        getattr(route, "path", None): route.endpoint for route in app.routes
    }
    fixture = endpoints["/fixtures"](competition, fixture_date)[0]
    result = endpoints["/predict"](
        PredictionRequest(
            competition=fixture.competition,
            kickoff_date=date.fromisoformat(fixture.kickoff_at[:10]),
            home_team=fixture.home_team,
            away_team=fixture.away_team,
        )
    )
    assert result.home_team == expected_home
