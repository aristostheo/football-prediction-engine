"""Prepare and compare external closing-market probabilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from pathlib import Path
from random import Random
from statistics import mean

import pandas as pd
from threadpoolctl import threadpool_limits

from football_predictor.domain import Competition
from football_predictor.models import (
    FEATURE_COLUMNS,
    ModelScore,
    _climatology_probabilities,
    _complete_season_order,
    _fit_predict_ensemble,
    _fit_predict_logistic,
    _fit_predict_poisson,
    _quantile,
    _score,
    add_elo_probabilities,
)
from football_predictor.team_names import canonical_team_name

MARKET_KEY_COLUMNS = ("competition", "match_date", "home_team", "away_team")
ODDS_COLUMNS = ("odds_home", "odds_draw", "odds_away")
PROBABILITY_COLUMNS = ("p_home_win", "p_draw", "p_away_win")


@dataclass(frozen=True)
class MarketBenchmarkComparison:
    """Walk-forward scores on identical matches with usable closing prices."""

    tested_seasons: tuple[str, ...]
    total_test_matches: int
    matched_matches: int
    odds_coverage: float
    model_scores: dict[str, ModelScore]
    paired_log_loss_differences: dict[str, dict[str, float]]


def load_market_odds_csv(path: str | Path) -> pd.DataFrame:
    """Read canonical odds CSV or a filtered Footiqo 1X2 odds export.

    Footiqo exports use matchDate, Country, League, homeTeam, awayTeam, H, D,
    and A. Only the two project competitions are retained.
    """
    raw = pd.read_csv(path)
    canonical_columns = {*MARKET_KEY_COLUMNS, *ODDS_COLUMNS}
    if canonical_columns.issubset(raw.columns):
        return raw

    required = {"matchDate", "Country", "League", "homeTeam", "awayTeam", "H", "D", "A"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(
            "odds CSV must use canonical columns or the Footiqo 1X2 export columns; "
            f"missing: {sorted(missing)}"
        )
    rows: list[dict[str, object]] = []
    for row in raw.itertuples(index=False):
        country = str(getattr(row, "Country")).strip().casefold()
        league = str(getattr(row, "League")).strip().casefold()
        if country in {"england", "eng"} and "premier league" in league:
            competition = Competition.PREMIER_LEAGUE.value
        elif country in {"greece", "gre"} and (
            "super league" in league or "ethniki katigoria" in league
        ):
            competition = Competition.SUPER_LEAGUE_GREECE.value
        else:
            continue
        rows.append(
            {
                "competition": competition,
                "match_date": getattr(row, "matchDate"),
                "home_team": getattr(row, "homeTeam"),
                "away_team": getattr(row, "awayTeam"),
                "odds_home": getattr(row, "H"),
                "odds_draw": getattr(row, "D"),
                "odds_away": getattr(row, "A"),
            }
        )
    if not rows:
        raise ValueError(
            "the Footiqo export contains no Premier League or Greece Super League 1X2 rows"
        )
    return pd.DataFrame(rows)


def prepare_market_odds(odds: pd.DataFrame) -> pd.DataFrame:
    """Normalize canonical decimal odds and remove the bookmaker margin.

    Input columns: competition, match_date, home_team, away_team, and decimal
    odds_home/odds_draw/odds_away. Rows with missing or invalid prices are
    excluded; duplicate normalized match keys are rejected.
    """
    required = {*MARKET_KEY_COLUMNS, *ODDS_COLUMNS}
    missing = required.difference(odds.columns)
    if missing:
        raise ValueError(f"missing closing-odds columns: {sorted(missing)}")
    prepared = odds[list(MARKET_KEY_COLUMNS + ODDS_COLUMNS)].copy()
    prepared["competition"] = prepared["competition"].astype(str)
    supported = {competition.value for competition in Competition}
    unknown = set(prepared["competition"].dropna()) - supported
    if unknown:
        raise ValueError(f"unsupported competition values in odds: {sorted(unknown)}")
    prepared["match_date"] = pd.to_datetime(
        prepared["match_date"], errors="coerce", dayfirst=True, format="mixed"
    ).dt.normalize()
    prepared["home_team"] = [
        canonical_team_name(str(name), Competition(competition))
        for name, competition in zip(
            prepared["home_team"], prepared["competition"], strict=True
        )
    ]
    prepared["away_team"] = [
        canonical_team_name(str(name), Competition(competition))
        for name, competition in zip(
            prepared["away_team"], prepared["competition"], strict=True
        )
    ]
    for column in ODDS_COLUMNS:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    valid = prepared["match_date"].notna() & prepared[list(ODDS_COLUMNS)].gt(1.0).all(axis=1)
    prepared = prepared.loc[valid].copy()
    if prepared.empty:
        raise ValueError("no odds rows have a date and three valid decimal prices")
    duplicated = prepared.duplicated(list(MARKET_KEY_COLUMNS), keep=False)
    if duplicated.any():
        keys = prepared.loc[duplicated, list(MARKET_KEY_COLUMNS)].head(3).to_dict("records")
        raise ValueError(f"duplicate normalized match keys in odds input: {keys}")

    inverse = 1.0 / prepared[list(ODDS_COLUMNS)]
    denominator = inverse.sum(axis=1)
    prepared["p_home_win"] = inverse["odds_home"] / denominator
    prepared["p_draw"] = inverse["odds_draw"] / denominator
    prepared["p_away_win"] = inverse["odds_away"] / denominator
    return prepared.reset_index(drop=True)


def compare_models_to_closing_market(
    features: pd.DataFrame,
    odds: pd.DataFrame,
    *,
    max_test_seasons: int = 5,
    minimum_training_matches: int = 200,
    bootstrap_samples: int = 2000,
    random_seed: int = 42,
) -> dict[str, MarketBenchmarkComparison]:
    """Compare leakage-safe model forecasts with de-vigged closing odds.

    Models are refit using only matches before each complete test season.
    Every score and season-block bootstrap interval uses the same matched
    fixtures, so coverage is reported alongside the metrics.
    """
    if max_test_seasons < 1 or minimum_training_matches < 1 or bootstrap_samples < 1:
        raise ValueError("walk-forward limits and bootstrap sample count must be positive")
    required = {
        "competition",
        "match_date",
        "season",
        "result",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        *FEATURE_COLUMNS,
    }
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"missing model columns: {sorted(missing)}")
    prepared_features = features.copy()
    prepared_features["match_date"] = pd.to_datetime(
        prepared_features["match_date"], errors="raise"
    ).dt.normalize()
    market = prepare_market_odds(odds).rename(
        columns={
            "p_home_win": "market_p_home_win",
            "p_draw": "market_p_draw",
            "p_away_win": "market_p_away_win",
        }
    )

    comparisons: dict[str, MarketBenchmarkComparison] = {}
    for competition, league in prepared_features.groupby("competition", sort=True):
        ordered = league.sort_values("match_date", kind="stable").reset_index(drop=True)
        seasons = _complete_season_order(ordered)[-max_test_seasons:]
        by_season: dict[str, dict[str, pd.DataFrame]] = {}
        total_test_matches = 0
        for season in seasons:
            test = ordered[ordered["season"] == season].copy()
            first_date = test["match_date"].min()
            train = ordered[ordered["match_date"] < first_date].copy()
            if len(train) < minimum_training_matches:
                continue
            total_test_matches += len(test)
            joined = test.merge(
                market,
                on=list(MARKET_KEY_COLUMNS),
                how="inner",
                validate="one_to_one",
            )
            if joined.empty:
                continue
            market_predictions = joined.copy()
            for destination, source in zip(
                PROBABILITY_COLUMNS,
                ("market_p_home_win", "market_p_draw", "market_p_away_win"),
                strict=True,
            ):
                market_predictions[destination] = market_predictions[source]
            with threadpool_limits(limits=1):
                fold = {
                    "closing_market": market_predictions,
                    "climatology": _climatology_probabilities(train, joined),
                    "elo": _probability_view(add_elo_probabilities(joined)),
                    "logistic": _probability_view(_fit_predict_logistic(train, joined)),
                    "poisson": _probability_view(_fit_predict_poisson(train, joined)),
                }
                ensemble, _, _ = _fit_predict_ensemble(train, joined)
            fold["ensemble"] = _probability_view(ensemble)
            by_season[season] = {
                name: frame.assign(season=season) for name, frame in fold.items()
            }

        if not by_season:
            continue
        model_scores: dict[str, ModelScore] = {}
        for name in sorted(next(iter(by_season.values()))):
            matched = pd.concat(
                [fold[name] for fold in by_season.values()], ignore_index=True
            )
            model_scores[name] = _score(matched)
        intervals = _paired_market_intervals(
            by_season,
            bootstrap_samples=bootstrap_samples,
            random_seed=random_seed,
        )
        matched_matches = sum(
            len(fold["closing_market"]) for fold in by_season.values()
        )
        comparisons[str(competition)] = MarketBenchmarkComparison(
            tested_seasons=tuple(by_season),
            total_test_matches=total_test_matches,
            matched_matches=matched_matches,
            odds_coverage=matched_matches / total_test_matches if total_test_matches else 0.0,
            model_scores=model_scores,
            paired_log_loss_differences=intervals,
        )
    if not comparisons:
        raise ValueError("odds data did not match any eligible walk-forward test fixtures")
    return comparisons


def _probability_view(predictions: pd.DataFrame) -> pd.DataFrame:
    """Keep labels and three forecast columns for common scoring."""
    return predictions.copy()


def _paired_market_intervals(
    by_season: dict[str, dict[str, pd.DataFrame]], *, bootstrap_samples: int, random_seed: int
) -> dict[str, dict[str, float]]:
    names = sorted(next(iter(by_season.values())))
    losses = {
        season: {
            name: _log_losses(frame)
            for name, frame in predictions.items()
        }
        for season, predictions in by_season.items()
    }
    rng = Random(random_seed)
    intervals: dict[str, dict[str, float]] = {}
    for name in names:
        if name == "closing_market":
            continue
        differences = {
            season: mean(losses[season][name]) - mean(losses[season]["closing_market"])
            for season in by_season
        }
        values = list(differences.values())
        bootstrap = sorted(
            mean(rng.choice(values) for _ in values) for _ in range(bootstrap_samples)
        )
        intervals[f"{name} - closing_market"] = {
            "mean_difference": mean(values),
            "lower_95": _quantile(bootstrap, 0.025),
            "upper_95": _quantile(bootstrap, 0.975),
        }
    return intervals


def _log_losses(predictions: pd.DataFrame) -> list[float]:
    actual_to_column = {"H": "p_home_win", "D": "p_draw", "A": "p_away_win"}
    return [
        -log(float(getattr(row, actual_to_column[row.result])))
        for row in predictions.itertuples(index=False)
    ]
