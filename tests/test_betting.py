from math import exp, nan

import pytest

from football_predictor.betting import (
    MarketEstimate,
    ScoreDistribution,
    Selection,
    initial_selections,
    margin_free_pair,
)
from football_predictor.models import _outcome_probabilities_from_goal_rates
from football_predictor.prediction import _top_scorelines_from_goal_rates


@pytest.mark.parametrize(
    "selection,score,expected",
    [
        (Selection("result", "home"), (2, 1), "win"),
        (Selection("result", "draw"), (1, 1), "win"),
        (Selection("result", "away"), (2, 1), "loss"),
        (Selection("total_goals", "over", line=2.5), (2, 1), "win"),
        (Selection("total_goals", "under", line=2.5), (2, 1), "loss"),
        (Selection("total_goals", "over", line=3), (2, 1), "push"),
        (Selection("total_goals", "under", line=3), (2, 1), "push"),
        (Selection("team_goals", "over", line=1.5, team="away"), (3, 1), "loss"),
        (Selection("team_goals", "under", line=1, team="away"), (3, 1), "push"),
        (Selection("btts", "yes"), (0, 2), "loss"),
        (Selection("btts", "no"), (0, 0), "win"),
        (Selection("correct_score", "score", score=(2, 1)), (2, 1), "win"),
        (Selection("correct_score", "score", score=(2, 1)), (1, 2), "loss"),
        (Selection("double_chance", "home_draw"), (1, 1), "win"),
        (Selection("double_chance", "home_away"), (1, 1), "loss"),
        (Selection("double_chance", "away_draw"), (0, 1), "win"),
        (Selection("draw_no_bet", "home"), (1, 1), "push"),
        (Selection("draw_no_bet", "away"), (0, 1), "win"),
        (Selection("draw_no_bet", "away"), (1, 0), "loss"),
    ],
)
def test_regulation_settlement(selection, score, expected):
    assert selection.settle(*score) == expected


@pytest.mark.parametrize("line", [-1, 2.25, 2.75, nan, float("inf"), True])
def test_invalid_and_quarter_lines_are_rejected(line):
    with pytest.raises(ValueError):
        Selection("total_goals", "over", line=line)


def test_invalid_selections_and_scores_are_rejected():
    for args in (
        {"market": "corners", "outcome": "over"},
        {"market": "team_goals", "outcome": "over", "line": 1.5},
        {"market": "result", "outcome": "home", "line": 2.5},
        {"market": "result", "outcome": "home", "team": "home"},
        {"market": "correct_score", "outcome": "score", "score": (-1, 2)},
        {"market": "result", "outcome": "home", "score": (1, 0)},
    ):
        with pytest.raises(ValueError):
            Selection(**args)
    for score in ((-1, 0), (1.5, 0), (True, 1)):
        with pytest.raises(ValueError):
            Selection("result", "home").settle(*score)


@pytest.mark.parametrize("rates", [(1.6, 0.9), (0.01, 6), (20, 11)])
def test_grid_reproduces_existing_goal_model_and_scorelines(rates):
    grid = ScoreDistribution.poisson(*rates)
    existing = _outcome_probabilities_from_goal_rates(*rates)
    assert grid.result_probabilities == pytest.approx(tuple(existing.values()), abs=1e-12)
    for score in _top_scorelines_from_goal_rates(*rates):
        estimate = grid.estimate(
            Selection("correct_score", "score", score=(score.home_goals, score.away_goals))
        )
        assert estimate.win == pytest.approx(score.probability, abs=1e-12)
    assert grid.rates_capped == (max(rates) > 8)
    assert 0 < grid.captured_mass <= 1


def test_independent_goal_market_probabilities_match_analytic_formulas():
    home, away = 1.7, 0.8
    grid = ScoreDistribution.poisson(home, away)
    assert grid.estimate(Selection("total_goals", "over", line=0.5)).win == pytest.approx(
        1 - exp(-home - away), abs=1e-7
    )
    assert grid.estimate(Selection("btts", "yes")).win == pytest.approx(
        (1 - exp(-home)) * (1 - exp(-away)), abs=1e-7
    )
    assert grid.estimate(
        Selection("team_goals", "over", line=0.5, team="home")
    ).win == pytest.approx(1 - exp(-home), abs=1e-7)


def test_alignment_is_coherent_and_preserves_conditional_score_ratios():
    grid = ScoreDistribution.poisson(2, 0.7)
    target = (0.45, 0.3, 0.25)
    aligned = grid.align_results(target)
    assert aligned.result_probabilities == pytest.approx(target, abs=1e-12)
    assert aligned.cells[2][0] / aligned.cells[1][0] == pytest.approx(
        grid.cells[2][0] / grid.cells[1][0]
    )
    for name, expected in (("home_draw", 0.75), ("away_draw", 0.55), ("home_away", 0.70)):
        assert aligned.estimate(Selection("double_chance", name)).win == pytest.approx(expected)
    home = aligned.estimate(Selection("draw_no_bet", "home"))
    assert (home.win, home.loss, home.push) == pytest.approx(
        target[0:1] + target[2:3] + target[1:2]
    )
    assert home.fair_odds == pytest.approx(0.7 / 0.45)


def test_goal_complements_monotonicity_and_score_matrix_orientation():
    grid = ScoreDistribution.poisson(2.2, 0.6).align_results((0.6, 0.25, 0.15))
    previous = 1.0
    for line in (0.5, 1, 1.5, 2, 2.5, 3.5, 4.5):
        over = grid.estimate(Selection("total_goals", "over", line=line))
        under = grid.estimate(Selection("total_goals", "under", line=line))
        assert over.win == pytest.approx(under.loss)
        assert over.push == pytest.approx(under.push)
        assert over.win <= previous
        previous = over.win
    swapped = ScoreDistribution(tuple(zip(*grid.cells, strict=True)))
    assert swapped.result_probabilities == pytest.approx(grid.result_probabilities[::-1])
    assert swapped.estimate(Selection("btts", "yes")).win == pytest.approx(
        grid.estimate(Selection("btts", "yes")).win
    )
    assert len(initial_selections()) == 20


def test_fair_prices_returns_and_market_probabilities_handle_refunds():
    estimate = MarketEstimate(0.45, 0.30, 0.25)
    assert estimate.fair_odds == pytest.approx(1.6666666667)
    assert estimate.conditional_win == pytest.approx(0.6)
    assert estimate.expected_net_return(estimate.fair_odds) == pytest.approx(0)
    assert estimate.expected_net_return(2.0) == pytest.approx(0.15)
    assert margin_free_pair(1.8, 2.2) == pytest.approx((0.55, 0.45))
    assert MarketEstimate(0, 0, 1).fair_odds is None
    assert MarketEstimate(0, 0, 1).conditional_win is None
    for price in (nan, 1, float("inf")):
        with pytest.raises(ValueError):
            estimate.expected_net_return(price)
        with pytest.raises(ValueError):
            margin_free_pair(price, 2)


def test_bad_grids_rates_and_outside_grid_score_requests_are_explicit():
    for rates in ((nan, 1), (float("inf"), 2), (0, 1), (-1, 2)):
        with pytest.raises(ValueError):
            ScoreDistribution.poisson(*rates)
    for cells in (((0.5,),), ((0.25, 0.25), (0.25, nan)), ((0.2, 0.2), (0.2, 0.2))):
        with pytest.raises(ValueError):
            ScoreDistribution(cells)
    grid = ScoreDistribution.poisson(8, 8)
    assert grid.captured_mass < 0.9  # Tail loss must not be silently presented as exact.
    with pytest.raises(ValueError):
        grid.estimate(Selection("correct_score", "score", score=(13, 0)))
    for target in ((0, 0.5, 0.5), (0.5, nan, 0.5), (0.3, 0.3, 0.3)):
        with pytest.raises(ValueError):
            grid.align_results(target)
    with pytest.raises(ValueError):
        MarketEstimate(0.8, 0.5, 0)
