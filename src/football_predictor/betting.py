"""Offline betting-market arithmetic; not connected to the production API yet.

All selections settle on regulation-time goals, including stoppage time. Extra
time, penalties, abandoned fixtures and quarter-goal Asian lines are excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, fsum, isfinite


def _goals(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("goals must be non-negative integers")


@dataclass(frozen=True)
class Selection:
    market: str
    outcome: str
    line: float | None = None
    team: str | None = None
    score: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        options = {
            "result": {"home", "draw", "away"},
            "total_goals": {"over", "under"},
            "team_goals": {"over", "under"},
            "btts": {"yes", "no"},
            "correct_score": {"score"},
            "double_chance": {"home_draw", "away_draw", "home_away"},
            "draw_no_bet": {"home", "away"},
        }
        if self.market not in options or self.outcome not in options[self.market]:
            raise ValueError("unsupported market or outcome")
        if self.market in {"total_goals", "team_goals"}:
            if (
                self.line is None
                or isinstance(self.line, bool)
                or not isfinite(self.line)
                or self.line < 0
                or (self.line * 2) % 1 != 0
            ):
                raise ValueError("goal lines must be finite non-negative whole or half goals")
        elif self.line is not None:
            raise ValueError("line is only supported for goal totals")
        if self.market == "team_goals":
            if self.team not in {"home", "away"}:
                raise ValueError("team totals require home or away")
        elif self.team is not None:
            raise ValueError("team is only supported for team totals")
        if self.market == "correct_score":
            if self.score is None or len(self.score) != 2:
                raise ValueError("correct score requires a home/away score pair")
            for value in self.score:
                _goals(value)
        elif self.score is not None:
            raise ValueError("score is only supported for correct score")

    def settle(self, home: int, away: int) -> str:
        """Return win/loss/push; callers must first establish a completed match."""
        _goals(home)
        _goals(away)
        result = "home" if home > away else "away" if away > home else "draw"
        if self.market == "draw_no_bet":
            return "push" if result == "draw" else "win" if result == self.outcome else "loss"
        if self.market in {"total_goals", "team_goals"}:
            goals = (
                home + away
                if self.market == "total_goals"
                else (home if self.team == "home" else away)
            )
            if goals == self.line:
                return "push"
            wins = goals > self.line if self.outcome == "over" else goals < self.line
        elif self.market == "result":
            wins = result == self.outcome
        elif self.market == "btts":
            wins = (home > 0 and away > 0) == (self.outcome == "yes")
        elif self.market == "correct_score":
            wins = (home, away) == self.score
        else:
            wins = result in self.outcome.split("_")
        return "win" if wins else "loss"


@dataclass(frozen=True)
class MarketEstimate:
    win: float
    loss: float
    push: float

    def __post_init__(self) -> None:
        values = (self.win, self.loss, self.push)
        if any(not isfinite(p) or p < 0 or p > 1 for p in values):
            raise ValueError("settlement probabilities must be finite and inside [0, 1]")
        if abs(fsum(values) - 1) > 1e-10:
            raise ValueError("settlement probabilities must sum to one")

    @property
    def conditional_win(self) -> float | None:
        """Win probability conditional on no refund; compare DNB quotes on this basis."""
        return self.win / (self.win + self.loss) if self.win + self.loss else None

    @property
    def fair_odds(self) -> float | None:
        # With pushes, 1 / unconditional win probability is NOT the fair price.
        return (self.win + self.loss) / self.win if self.win else None

    def expected_net_return(self, decimal_odds: float) -> float:
        if not isfinite(decimal_odds) or decimal_odds <= 1:
            raise ValueError("decimal odds must be finite and greater than one")
        return self.win * (decimal_odds - 1) - self.loss


@dataclass(frozen=True)
class ScoreDistribution:
    cells: tuple[tuple[float, ...], ...]
    captured_mass: float = 1.0
    rates_capped: bool = False
    source: str = "independent_poisson"

    def __post_init__(self) -> None:
        if len(self.cells) < 2 or any(len(row) != len(self.cells) for row in self.cells):
            raise ValueError("score matrix must be square with at least two goal levels")
        values = [p for row in self.cells for p in row]
        if any(not isfinite(p) or p < 0 for p in values) or abs(fsum(values) - 1) > 1e-10:
            raise ValueError("score probabilities must be finite, non-negative and sum to one")
        if not isfinite(self.captured_mass) or not 0 < self.captured_mass <= 1:
            raise ValueError("captured mass must be inside (0, 1]")

    @classmethod
    def poisson(cls, home_rate: float, away_rate: float) -> ScoreDistribution:
        """Replay the serving model's rate cap and normalized 0..12 grid explicitly."""
        if any(not isfinite(r) or r <= 0 for r in (home_rate, away_rate)):
            raise ValueError("goal rates must be finite and positive")

        def marginal(rate: float) -> list[float]:
            rate = min(rate, 8.0)
            values = [exp(-rate)]
            for goals in range(1, 13):
                values.append(values[-1] * rate / goals)
            return values

        home, away = marginal(home_rate), marginal(away_rate)
        mass = fsum(home) * fsum(away)
        return cls(
            tuple(tuple(h * a / mass for a in away) for h in home),
            captured_mass=min(mass, 1.0),
            rates_capped=home_rate > 8 or away_rate > 8,
        )

    def estimate(self, selection: Selection) -> MarketEstimate:
        if selection.score and max(selection.score) >= len(self.cells):
            raise ValueError("requested correct score is outside the represented goal grid")
        totals = {"win": [], "loss": [], "push": []}
        for home, row in enumerate(self.cells):
            for away, probability in enumerate(row):
                totals[selection.settle(home, away)].append(probability)
        return MarketEstimate(*(fsum(totals[key]) for key in ("win", "loss", "push")))

    @property
    def result_probabilities(self) -> tuple[float, float, float]:
        return tuple(
            self.estimate(Selection("result", side)).win for side in ("home", "draw", "away")
        )

    def align_results(self, target: tuple[float, float, float]) -> ScoreDistribution:
        """Experimental classwise scaling; preserves within-result score ratios.

        This enforces coherence, not improved calibration or predictive accuracy.
        It must be evaluated before replacing any existing scoreline output.
        """
        if (
            len(target) != 3
            or any(not isfinite(p) or p <= 0 or p >= 1 for p in target)
            or abs(fsum(target) - 1) > 1e-10
        ):
            raise ValueError("target requires three positive normalized result probabilities")
        current = self.result_probabilities
        if any(p <= 0 for p in current):
            raise ValueError("cannot align an outcome with zero score-matrix support")
        cells = tuple(
            tuple(
                p * target[index] / current[index]
                for away, p in enumerate(row)
                for index in [0 if home > away else 1 if home == away else 2]
            )
            for home, row in enumerate(self.cells)
        )
        return ScoreDistribution(cells, self.captured_mass, self.rates_capped, "result_aligned")


def initial_selections() -> dict[str, Selection]:
    """Fixed first-release evaluation family, not selected using test scores."""
    selections = {f"result_{side}": Selection("result", side) for side in ("home", "draw", "away")}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        selections[f"over_{line}"] = Selection("total_goals", "over", line=line)
    selections["btts_yes"] = Selection("btts", "yes")
    for team in ("home", "away"):
        for line in (0.5, 1.5, 2.5):
            selections[f"{team}_over_{line}"] = Selection(
                "team_goals", "over", line=line, team=team
            )
    for outcome in ("home_draw", "away_draw", "home_away"):
        selections[outcome] = Selection("double_chance", outcome)
    for team in ("home", "away"):
        selections[f"dnb_{team}"] = Selection("draw_no_bet", team)
    return selections


def margin_free_pair(first: float, second: float) -> tuple[float, float]:
    """Normalize a complete complementary pair from one bookmaker and line.

    Not valid for overlapping double-chance selections or a partial score list.
    With refunds these are conditional-on-no-push probabilities.
    """
    if any(not isfinite(price) or price <= 1 for price in (first, second)):
        raise ValueError("both decimal prices must be finite and greater than one")
    total = 1 / first + 1 / second
    return (1 / first) / total, (1 / second) / total
