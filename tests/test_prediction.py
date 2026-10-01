from datetime import date
from pathlib import Path

import pytest

from football_predictor.domain import Competition
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
