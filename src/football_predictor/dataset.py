from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from football_predictor.domain import HistoricalMatch
from football_predictor.validation import validate_match_collection


def build_match_dataframe(matches: Iterable[HistoricalMatch]) -> pd.DataFrame:
    """Produce a deterministic canonical table for later feature engineering."""
    ordered = validate_match_collection(matches)
    rows = [
        {
            "match_date": match.match_date.isoformat(),
            "competition": match.competition.value,
            "season": match.season,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "home_goals": match.home_goals,
            "away_goals": match.away_goals,
            "result": match.result.value,
            "source_name": match.source_name,
            "source_url": str(match.source_url),
            "retrieved_at": match.retrieved_at.isoformat(),
        }
        for match in ordered
    ]
    return pd.DataFrame(rows)
