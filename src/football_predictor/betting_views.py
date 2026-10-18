"""API presentation of existing forecast probabilities and separate goal estimates."""

from dataclasses import dataclass
from math import isfinite

from football_predictor.betting import MarketEstimate, ScoreDistribution, Selection


@dataclass(frozen=True)
class BettingOutcome:
    key: str
    label: str
    probability: float
    win_probability: float
    push_probability: float
    fair_odds: float | None


@dataclass(frozen=True)
class BettingMarket:
    key: str
    title: str
    group: str
    source: str
    outcomes: tuple[BettingOutcome, ...]
    line: float | None = None
    team: str | None = None


@dataclass(frozen=True)
class BettingForecast:
    markets: tuple[BettingMarket, ...]
    goal_status: str
    goal_note: str
    captured_mass: float | None
    goal_result_probabilities: tuple[float, float, float] | None
    period: str = "regulation"


def _outcome(key: str, label: str, estimate: MarketEstimate) -> BettingOutcome:
    return BettingOutcome(
        key,
        label,
        estimate.conditional_win or 0.0,
        estimate.win,
        estimate.push,
        estimate.fair_odds,
    )


def build_betting_forecast(
    probabilities: tuple[float, float, float], home_rate: float | None, away_rate: float | None
) -> BettingForecast:
    """No fitting, requests or changes to headline/scoreline forecasting policies.

    Result derivatives use the final headline forecast, including promoted-team
    priors. Goal markets use the existing independent Poisson score distribution;
    the experimental classwise alignment was not selected for production.
    """
    if (
        any(not isfinite(p) or not 0 < p < 1 for p in probabilities)
        or abs(sum(probabilities) - 1) > 1e-9
    ):
        raise ValueError("expected three normalized positive result probabilities")
    home, draw, away = probabilities
    result = BettingMarket(
        "result",
        "Match result",
        "result",
        "result_forecast",
        tuple(
            _outcome(key, label, MarketEstimate(p, 1 - p, 0))
            for key, label, p in zip(
                ("home", "draw", "away"), ("Home", "Draw", "Away"), probabilities, strict=True
            )
        ),
    )
    double = BettingMarket(
        "double_chance",
        "Double chance",
        "result",
        "result_forecast",
        tuple(
            _outcome(key, label, MarketEstimate(p, 1 - p, 0))
            for key, label, p in (
                ("home_draw", "Home or draw", home + draw),
                ("away_draw", "Away or draw", away + draw),
                ("home_away", "Home or away", home + away),
            )
        ),
    )
    dnb = BettingMarket(
        "draw_no_bet",
        "Draw no bet",
        "result",
        "result_forecast",
        (
            _outcome("home", "Home", MarketEstimate(home, away, draw)),
            _outcome("away", "Away", MarketEstimate(away, home, draw)),
        ),
    )
    markets = [result, double, dnb]
    if home_rate is None or away_rate is None:
        return BettingForecast(
            tuple(markets),
            "unavailable",
            "Goal estimates are not available for this forecast.",
            None,
            None,
        )
    if any(not isfinite(r) or r <= 0 for r in (home_rate, away_rate)):
        return BettingForecast(
            tuple(markets),
            "unavailable",
            "Goal estimates could not be calculated reliably.",
            None,
            None,
        )
    grid = ScoreDistribution.poisson(home_rate, away_rate)
    if grid.rates_capped or grid.captured_mass < 0.999:
        return BettingForecast(
            tuple(markets),
            "unavailable",
            "Goal estimates are outside the supported score range.",
            grid.captured_mass,
            None,
        )
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        markets.append(
            BettingMarket(
                f"total_{line}",
                "Total match goals",
                "goals",
                "goal_model",
                tuple(
                    _outcome(
                        side, side.title(), grid.estimate(Selection("total_goals", side, line=line))
                    )
                    for side in ("over", "under")
                ),
                line=line,
            )
        )
    markets.append(
        BettingMarket(
            "btts",
            "Both teams to score",
            "goals",
            "goal_model",
            tuple(
                _outcome(side, side.title(), grid.estimate(Selection("btts", side)))
                for side in ("yes", "no")
            ),
        )
    )
    for team in ("home", "away"):
        for line in (0.5, 1.5, 2.5):
            markets.append(
                BettingMarket(
                    f"{team}_total_{line}",
                    f"{team.title()} team goals",
                    "teams",
                    "goal_model",
                    tuple(
                        _outcome(
                            side,
                            side.title(),
                            grid.estimate(Selection("team_goals", side, line=line, team=team)),
                        )
                        for side in ("over", "under")
                    ),
                    line=line,
                    team=team,
                )
            )
    scores = sorted(
        ((p, h, a) for h, row in enumerate(grid.cells) for a, p in enumerate(row)),
        key=lambda item: (-item[0], item[1], item[2]),
    )[:9]
    outcomes = tuple(
        _outcome(f"{h}-{a}", f"{h}–{a}", MarketEstimate(p, 1 - p, 0)) for p, h, a in scores
    )
    markets.append(
        BettingMarket("correct_score", "Correct score", "scores", "goal_model", outcomes)
    )
    return BettingForecast(
        tuple(markets),
        "experimental",
        (
            "Goal markets and scores use the separate goal model. They are experimental "
            "and can imply different result probabilities from the headline forecast."
        ),
        grid.captured_mass,
        grid.result_probabilities,
    )
