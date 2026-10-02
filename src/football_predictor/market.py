"""Prepare and compare external closing-market probabilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log
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
    blend_probabilities,
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


@dataclass(frozen=True)
class MarketAssistFoldScore:
    """A test-season score with the odds weight selected from earlier OOF rows."""

    season: str
    test_matches: int
    tuning_matches: int
    tuning_seasons: tuple[str, ...]
    market_weight: float
    model_score: ModelScore
    closing_market_score: ModelScore
    market_assisted_score: ModelScore


@dataclass(frozen=True)
class MarketAssistComparison:
    """Sequential test folds for a probability blend selected from past OOF data."""

    folds: tuple[MarketAssistFoldScore, ...]
    pooled_model_score: ModelScore
    pooled_closing_market_score: ModelScore
    pooled_market_assisted_score: ModelScore


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


def market_probabilities_from_decimal_odds(
    odds_home: float, odds_draw: float, odds_away: float
) -> tuple[float, float, float]:
    """Remove the bookmaker margin from three decimal 1X2 prices."""
    prices = (float(odds_home), float(odds_draw), float(odds_away))
    if any(not isfinite(price) or price <= 1.0 for price in prices):
        raise ValueError("all decimal odds must be greater than 1.0")
    inverse = tuple(1.0 / price for price in prices)
    total = sum(inverse)
    return tuple(price / total for price in inverse)


def blend_market_probabilities(
    model_probabilities: tuple[float, float, float],
    market_probabilities: tuple[float, float, float],
    *,
    market_weight: float,
) -> tuple[float, float, float]:
    """Blend home/draw/away probabilities with a specified market share."""
    if not 0.0 <= market_weight <= 1.0:
        raise ValueError("market_weight must be between zero and one")
    if len(model_probabilities) != 3 or len(market_probabilities) != 3:
        raise ValueError("model and market probabilities must each contain three outcomes")
    if any(value <= 0.0 or value >= 1.0 for value in (*model_probabilities, *market_probabilities)):
        raise ValueError("all probabilities must be strictly between zero and one")
    if abs(sum(model_probabilities) - 1.0) > 1e-9 or abs(sum(market_probabilities) - 1.0) > 1e-9:
        raise ValueError("model and market probabilities must each sum to one")
    return tuple(
        (1.0 - market_weight) * model + market_weight * market
        for model, market in zip(model_probabilities, market_probabilities, strict=True)
    )


def select_market_weight(
    prior_predictions: pd.DataFrame, *, step: float = 0.01
) -> float:
    """Select a market share from prior out-of-fold forecasts using log loss."""
    required = {
        "result",
        *(f"model_p_{outcome}" for outcome in ("home_win", "draw", "away_win")),
        *(f"market_p_{outcome}" for outcome in ("home_win", "draw", "away_win")),
    }
    missing = required.difference(prior_predictions.columns)
    if missing:
        raise ValueError(f"missing prior forecast columns: {sorted(missing)}")
    if prior_predictions.empty or not 0.0 < step <= 1.0:
        raise ValueError("prior forecasts must be non-empty and step must be in (0, 1]")

    labels = prior_predictions["result"].map({"H": 0, "D": 1, "A": 2})
    if labels.isna().any():
        raise ValueError("prior forecasts contain unsupported result labels")
    actual_indices = labels.to_numpy(dtype=int)
    model = prior_predictions[
        [f"model_p_{outcome}" for outcome in ("home_win", "draw", "away_win")]
    ].to_numpy(dtype=float)
    market = prior_predictions[
        [f"market_p_{outcome}" for outcome in ("home_win", "draw", "away_win")]
    ].to_numpy(dtype=float)
    if (
        not pd.notna(model).all()
        or not pd.notna(market).all()
        or (model <= 0.0).any()
        or (model >= 1.0).any()
        or (market <= 0.0).any()
        or (market >= 1.0).any()
    ):
        raise ValueError("prior forecasts must contain probabilities strictly between zero and one")

    candidate_count = int(round(1.0 / step))
    weights = [index / candidate_count for index in range(candidate_count + 1)]
    scores = []
    for weight in weights:
        blended = (1.0 - weight) * model + weight * market
        losses = -blended[range(len(actual_indices)), actual_indices]
        scores.append(float(losses.mean()))
    return weights[min(range(len(scores)), key=scores.__getitem__)]


def compare_market_assisted_walk_forward(
    features: pd.DataFrame,
    odds: pd.DataFrame,
    *,
    max_test_seasons: int = 5,
    minimum_training_matches: int = 200,
    minimum_tuning_matches: int = 400,
    minimum_tuning_seasons: int = 2,
) -> dict[str, MarketAssistComparison]:
    """Test a model/market blend with its weight fit only on earlier OOF matches.

    A single market share is selected across the two leagues using earlier
    out-of-fold forecasts. Every historical row used to select a test-fold
    weight predates that fold's first fixture. Folds without enough prior
    matches and season blocks are omitted from the assisted comparison.
    """
    if (
        max_test_seasons < 1
        or minimum_training_matches < 1
        or minimum_tuning_matches < 1
        or minimum_tuning_seasons < 1
    ):
        raise ValueError("walk-forward limits and minimum sample sizes must be positive")
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

    test_seasons: dict[str, tuple[str, ...]] = {}
    out_of_fold: list[pd.DataFrame] = []
    for competition, league in prepared_features.groupby("competition", sort=True):
        ordered = league.sort_values("match_date", kind="stable").reset_index(drop=True)
        complete_seasons = _complete_season_order(ordered)
        test_seasons[str(competition)] = tuple(complete_seasons[-max_test_seasons:])
        for season in complete_seasons:
            test = ordered[ordered["season"] == season].copy()
            first_date = test["match_date"].min()
            train = ordered[ordered["match_date"] < first_date].copy()
            if len(train) < minimum_training_matches:
                continue
            joined = test.merge(
                market,
                on=list(MARKET_KEY_COLUMNS),
                how="inner",
                validate="one_to_one",
            )
            if joined.empty:
                continue
            with threadpool_limits(limits=1):
                model = _deployed_model_probabilities(train, joined, str(competition))
            predictions = joined[["competition", "season", "match_date", "result"]].copy()
            for outcome in ("home_win", "draw", "away_win"):
                model_column = f"p_{outcome}"
                market_column = f"market_p_{outcome}"
                predictions[f"model_{model_column}"] = model[model_column].to_numpy()
                predictions[market_column] = joined[market_column].to_numpy()
            out_of_fold.append(predictions)

    if not out_of_fold:
        raise ValueError("no historical out-of-fold forecasts matched the supplied odds")
    oof = pd.concat(out_of_fold, ignore_index=True)
    results: dict[str, MarketAssistComparison] = {}
    for competition, seasons in test_seasons.items():
        comp_features = prepared_features[prepared_features["competition"] == competition]
        scored_folds: list[MarketAssistFoldScore] = []
        fold_predictions: dict[str, list[pd.DataFrame]] = {
            "model": [],
            "closing_market": [],
            "market_assisted": [],
        }
        for season in seasons:
            test_oof = oof[(oof["competition"] == competition) & (oof["season"] == season)]
            if test_oof.empty:
                continue
            cutoff = comp_features.loc[
                comp_features["season"] == season, "match_date"
            ].min()
            prior = oof[oof["match_date"] < cutoff].copy()
            prior_seasons = tuple(
                f"{row.competition}:{row.season}"
                for row in prior[["competition", "season"]]
                .drop_duplicates()
                .itertuples(index=False)
            )
            if (
                len(prior) < minimum_tuning_matches
                or len(prior_seasons) < minimum_tuning_seasons
            ):
                continue
            weight = select_market_weight(prior)
            model_frame = _forecast_frame(test_oof, "model_")
            market_frame = _forecast_frame(test_oof, "market_")
            assist_frame = model_frame.copy()
            for column in PROBABILITY_COLUMNS:
                assist_frame[column] = (
                    (1.0 - weight) * model_frame[column].to_numpy()
                    + weight * market_frame[column].to_numpy()
                )
            scored_folds.append(
                MarketAssistFoldScore(
                    season=season,
                    test_matches=len(test_oof),
                    tuning_matches=len(prior),
                    tuning_seasons=prior_seasons,
                    market_weight=weight,
                    model_score=_score(model_frame),
                    closing_market_score=_score(market_frame),
                    market_assisted_score=_score(assist_frame),
                )
            )
            for name, frame in (
                ("model", model_frame),
                ("closing_market", market_frame),
                ("market_assisted", assist_frame),
            ):
                fold_predictions[name].append(frame.assign(season=season))
        if not scored_folds:
            continue
        pooled = {
            name: _score(pd.concat(frames, ignore_index=True))
            for name, frames in fold_predictions.items()
        }
        results[competition] = MarketAssistComparison(
            folds=tuple(scored_folds),
            pooled_model_score=pooled["model"],
            pooled_closing_market_score=pooled["closing_market"],
            pooled_market_assisted_score=pooled["market_assisted"],
        )
    if not results:
        raise ValueError(
            "no test fold had enough earlier out-of-fold data to tune the market blend"
        )
    return results


def _deployed_model_probabilities(
    train: pd.DataFrame, test: pd.DataFrame, competition: str
) -> pd.DataFrame:
    elo = add_elo_probabilities(test)
    if competition != "premier_league":
        return elo
    poisson = _fit_predict_poisson(train, test)
    return blend_probabilities(elo, poisson, elo_weight=0.25)


def _forecast_frame(source: pd.DataFrame, prefix: str) -> pd.DataFrame:
    frame = source[["result"]].copy()
    for outcome, column in zip(
        PROBABILITY_COLUMNS, ("home_win", "draw", "away_win"), strict=True
    ):
        frame[outcome] = source[f"{prefix}p_{column}"].to_numpy()
    return frame.rename(
        columns={
            "home_win": "p_home_win",
            "draw": "p_draw",
            "away_win": "p_away_win",
        }
    )


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
