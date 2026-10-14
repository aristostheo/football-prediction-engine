"""Shared serving/replay policy for registered clubs without recorded results."""

import pandas as pd

PROMOTED_TEAM_START_ELO = 1400.0
PROMOTED_TEAM_MODEL_WEIGHT = 0.5


def smoothed_outcome_prior(results: pd.Series) -> dict[str, float]:
    counts = results.value_counts()
    denominator = len(results) + 3
    return {
        "p_home_win": float((counts.get("H", 0) + 1) / denominator),
        "p_draw": float((counts.get("D", 0) + 1) / denominator),
        "p_away_win": float((counts.get("A", 0) + 1) / denominator),
    }


def shrink_to_prior(
    probabilities: pd.DataFrame, prior: dict[str, float], *, model_weight: float
) -> pd.DataFrame:
    adjusted = probabilities.copy()
    for column, prior_probability in prior.items():
        adjusted[column] = (
            model_weight * adjusted[column].to_numpy() + (1 - model_weight) * prior_probability
        )
    return adjusted
