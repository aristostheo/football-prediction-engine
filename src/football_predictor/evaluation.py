"""Chronological evaluation for the project's initial Elo probability baseline."""

from __future__ import annotations

from dataclasses import dataclass
from math import log

import pandas as pd

from football_predictor.domain import MatchResult


@dataclass(frozen=True)
class EvaluationMetrics:
    matches: int
    log_loss: float
    brier_score: float
    accuracy: float


def add_elo_probabilities(
    matches: pd.DataFrame, *, draw_factor: float = 0.75, home_advantage: float = 60.0
) -> pd.DataFrame:
    """Convert pre-match Elo into normalized home/draw/away probabilities."""
    if draw_factor <= 0:
        raise ValueError("draw_factor must be positive")
    required = {"home_elo", "away_elo"}
    missing = required.difference(matches.columns)
    if missing:
        raise ValueError(f"missing Elo columns: {sorted(missing)}")

    probabilities = matches.copy()
    home_strength = 10 ** ((probabilities["home_elo"] + home_advantage) / 400.0)
    away_strength = 10 ** (probabilities["away_elo"] / 400.0)
    draw_strength = draw_factor * (home_strength * away_strength) ** 0.5
    normalizer = home_strength + draw_strength + away_strength
    probabilities["p_home_win"] = home_strength / normalizer
    probabilities["p_draw"] = draw_strength / normalizer
    probabilities["p_away_win"] = away_strength / normalizer
    return probabilities


def chronological_holdout(matches: pd.DataFrame, *, test_fraction: float = 0.2) -> pd.DataFrame:
    """Return the most recent fraction from each competition without shuffling."""
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between zero and one")
    required = {"competition", "match_date"}
    missing = required.difference(matches.columns)
    if missing:
        raise ValueError(f"missing chronological columns: {sorted(missing)}")

    ordered = matches.sort_values(["competition", "match_date"], kind="stable")
    holdout_parts = []
    for _, competition_matches in ordered.groupby("competition", sort=False):
        split_at = int(len(competition_matches) * (1 - test_fraction))
        holdout_parts.append(competition_matches.iloc[split_at:])
    return pd.concat(holdout_parts, ignore_index=True)


def evaluate_probabilities(matches: pd.DataFrame) -> EvaluationMetrics:
    """Evaluate three-outcome forecasts with log loss, Brier score, and accuracy."""
    required = {"result", "p_home_win", "p_draw", "p_away_win"}
    missing = required.difference(matches.columns)
    if missing:
        raise ValueError(f"missing evaluation columns: {sorted(missing)}")
    if matches.empty:
        raise ValueError("cannot evaluate an empty match collection")

    probability_columns = {
        MatchResult.HOME_WIN.value: "p_home_win",
        MatchResult.DRAW.value: "p_draw",
        MatchResult.AWAY_WIN.value: "p_away_win",
    }
    labels = (MatchResult.HOME_WIN.value, MatchResult.DRAW.value, MatchResult.AWAY_WIN.value)
    log_losses: list[float] = []
    brier_scores: list[float] = []
    correct = 0
    for match in matches.itertuples(index=False):
        probabilities = {
            label: float(getattr(match, probability_columns[label])) for label in labels
        }
        if any(probability <= 0 or probability >= 1 for probability in probabilities.values()):
            raise ValueError("all probabilities must be strictly between zero and one")
        if abs(sum(probabilities.values()) - 1.0) > 1e-9:
            raise ValueError("probabilities must sum to one")
        actual = match.result
        if actual not in probability_columns:
            raise ValueError(f"unsupported result: {actual}")
        log_losses.append(-log(probabilities[actual]))
        brier_scores.append(
            sum((probabilities[label] - float(label == actual)) ** 2 for label in labels)
        )
        predicted = max(labels, key=probabilities.__getitem__)
        correct += int(predicted == actual)

    return EvaluationMetrics(
        matches=len(matches),
        log_loss=sum(log_losses) / len(log_losses),
        brier_score=sum(brier_scores) / len(brier_scores),
        accuracy=correct / len(matches),
    )
