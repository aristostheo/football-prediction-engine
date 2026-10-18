import asyncio
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from football_predictor.api import create_app
from football_predictor.betting_views import build_betting_forecast
from football_predictor.domain import Competition
from football_predictor.prediction import PredictionEngine, _top_scorelines_from_goal_rates


def test_result_derivatives_use_final_headline_probabilities_and_handle_refunds():
    betting = build_betting_forecast((0.5, 0.3, 0.2), 1.8, 0.9)
    markets = {market.key: market for market in betting.markets}
    assert [outcome.probability for outcome in markets["double_chance"].outcomes] == pytest.approx(
        [0.8, 0.5, 0.7]
    )
    dnb = markets["draw_no_bet"].outcomes
    assert [outcome.probability for outcome in dnb] == pytest.approx([5 / 7, 2 / 7])
    assert [outcome.fair_odds for outcome in dnb] == pytest.approx([1.4, 3.5])
    assert [outcome.push_probability for outcome in dnb] == [0.3, 0.3]
    assert [outcome.win_probability for outcome in dnb] == [0.5, 0.2]
    assert all(
        markets[key].source == "result_forecast"
        for key in ["result", "double_chance", "draw_no_bet"]
    )


def test_goal_markets_retain_original_scoreline_distribution_not_result_alignment():
    first = build_betting_forecast((0.5, 0.3, 0.2), 1.8, 0.9)
    second = build_betting_forecast((0.2, 0.2, 0.6), 1.8, 0.9)
    assert first.goal_status == "experimental"
    assert first.period == "regulation"
    assert [m for m in first.markets if m.source == "goal_model"] == [
        m for m in second.markets if m.source == "goal_model"
    ]
    scores = next(m for m in first.markets if m.key == "correct_score")
    assert len(scores.outcomes) == 9
    assert sum(o.probability for o in scores.outcomes) < 1
    for existing, outcome in zip(
        _top_scorelines_from_goal_rates(1.8, 0.9), scores.outcomes, strict=False
    ):
        assert outcome.key == f"{existing.home_goals}-{existing.away_goals}"
        assert outcome.probability == pytest.approx(existing.probability)
    for market in first.markets:
        if market.group in {"goals", "teams"}:
            assert sum(o.probability for o in market.outcomes) == pytest.approx(1)
            assert all(o.push_probability == 0 for o in market.outcomes)
            assert all(o.fair_odds == pytest.approx(1 / o.probability) for o in market.outcomes)


@pytest.mark.parametrize("rates", [(None, None), (float("nan"), 1), (0, 1), (8, 8), (9, 1)])
def test_unavailable_or_extreme_goal_rates_do_not_produce_misleading_prices(rates):
    forecast = build_betting_forecast((0.5, 0.3, 0.2), *rates)
    assert forecast.goal_status == "unavailable"
    assert len(forecast.markets) == 3
    assert all(m.group == "result" for m in forecast.markets)


def test_api_includes_betting_estimates_without_changing_existing_predictions():
    engine = PredictionEngine.from_csv(
        Path(__file__).parents[1] / "data/model/historical_matches.csv.gz"
    )
    app = create_app(engine=engine)
    request = {
        "competition": "premier_league",
        "kickoff_date": (
            engine.latest_result_date(Competition.PREMIER_LEAGUE) + timedelta(days=1)
        ).isoformat(),
        "home_team": "Arsenal",
        "away_team": "Fulham",
    }

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            original = (await client.post("/predict", json=request)).json()
            compared = (
                await client.post(
                    "/predict", json={**request, "odds_home": 2, "odds_draw": 3, "odds_away": 4}
                )
            ).json()
            return original, compared

    original, compared = asyncio.run(exercise())
    assert original["betting"] == compared["betting"]
    assert original["model_home_win_probability"] == compared["model_home_win_probability"]
    result = original["betting"]["markets"][0]
    assert result["outcomes"][0]["probability"] == original["model_home_win_probability"]
    assert original["betting"]["period"] == "regulation"
    assert original["components"]["top_scorelines"][0]["probability"] == pytest.approx(
        next(m for m in original["betting"]["markets"] if m["key"] == "correct_score")["outcomes"][
            0
        ]["probability"]
    )


def test_output_contains_plain_json_serializable_finite_prices():
    import json

    forecast = build_betting_forecast((0.5, 0.3, 0.2), 1.8, 0.9)
    assert (
        json.loads(json.dumps(asdict(forecast), allow_nan=False))["goal_status"] == "experimental"
    )
