"""Offline expanding-season evaluation for proposed goal-derived markets.

No API calls, random splits, production imports of this module, or deployment.
The estimators are frozen for a test season; pre-match team states still update
after each earlier day, as in the existing seasonal research benchmarks.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from football_predictor.betting import ScoreDistribution, Selection, initial_selections
from football_predictor.evaluation import add_elo_probabilities, evaluate_probabilities
from football_predictor.features import FeatureConfig, build_pre_match_features
from football_predictor.models import FEATURE_COLUMNS, _complete_season_order, _fit_poisson_model
from football_predictor.policy import (
    PROMOTED_TEAM_MODEL_WEIGHT,
    PROMOTED_TEAM_START_ELO,
    smoothed_outcome_prior,
)

RESULT_COLUMNS = ("p_home_win", "p_draw", "p_away_win")


def prepare_serving_features(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[pd.DataFrame, pd.Series]:
    """Replay the serving prior for a club's first recorded appearance only."""
    prepared = test.copy()
    known = set(train.home_team) | set(train.away_team)
    unseen = pd.Series(False, index=test.index)
    for side in ("home", "away"):
        first_appearance = (
            ~prepared[f"{side}_team"].isin(known)
            & prepared[f"{side}_days_since_last_match"].isna()
            & prepared[f"{side}_matches_played"].eq(0)
        )
        prepared.loc[first_appearance, f"{side}_elo"] = PROMOTED_TEAM_START_ELO
        unseen |= first_appearance
    prepared["elo_difference"] = (
        prepared.home_elo + FeatureConfig().elo_home_advantage - prepared.away_elo
    )
    return prepared, unseen


def season_folds(features: pd.DataFrame, *, count: int = 5):
    """Latest complete seasons, with at least 150 strictly earlier training rows."""
    if count < 1:
        raise ValueError("season count must be positive")
    for competition, league in features.groupby("competition", sort=True):
        league = league.sort_values("match_date", kind="stable").reset_index(drop=True)
        # Exclude interrupted pandemic seasons from *testing*. Keep the bundled
        # training input identical to serving, and report its date limitation.
        seasons = [s for s in _complete_season_order(league) if s >= "2020-21"][-count:]
        for season in seasons:
            test = league[league.season == season].copy()
            train = league[league.match_date < test.match_date.min()].copy()
            if len(train) >= 150:
                assert train.match_date.max() < test.match_date.min()
                yield str(competition), season, train, test


def _settlement_masks(selections: dict[str, Selection]):
    return {
        name: {
            state: np.array(
                [selection.settle(home, away) == state for home in range(13) for away in range(13)]
            )
            for state in ("win", "loss", "push")
        }
        for name, selection in selections.items()
    }


def forecast_fold(competition: str, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Fit the existing goal recipe on earlier rows and emit isolated candidates."""
    if train.empty or test.empty or train.match_date.max() >= test.match_date.min():
        raise ValueError("all fitted rows must strictly precede the held-out season")
    prepared, unseen = prepare_serving_features(train, test)
    with threadpool_limits(limits=1):
        home_model = _fit_poisson_model(train, "home_goals")
        away_model = _fit_poisson_model(train, "away_goals")
        home_rates = home_model.predict(prepared[list(FEATURE_COLUMNS)])
        away_rates = away_model.predict(prepared[list(FEATURE_COLUMNS)])
    elo = add_elo_probabilities(prepared)[list(RESULT_COLUMNS)].to_numpy()
    prior = np.array(list(smoothed_outcome_prior(train.result).values()))
    empirical = ScoreDistribution.poisson(
        float(train.home_goals.mean()), float(train.away_goals.mean())
    )
    distributions = {
        "goal_raw": [],
        "goal_aligned": [],
        "league_poisson": [],
    }
    targets, gaps, masses, capped = [], [], [], []
    for index, (home, away) in enumerate(zip(home_rates, away_rates, strict=True)):
        raw = ScoreDistribution.poisson(float(home), float(away))
        goal_result = np.array(raw.result_probabilities)
        target = (
            0.25 * elo[index] + 0.75 * goal_result
            if competition == "premier_league"
            else elo[index]
        )
        if unseen.iloc[index]:
            target = PROMOTED_TEAM_MODEL_WEIGHT * target + (1 - PROMOTED_TEAM_MODEL_WEIGHT) * prior
        aligned = raw.align_results(tuple(float(p) for p in target))
        targets.append(target)
        gaps.append(float(np.max(np.abs(goal_result - target))))
        masses.append(raw.captured_mass)
        capped.append(raw.rates_capped)
        for key, distribution in (
            ("goal_raw", raw),
            ("goal_aligned", aligned),
            ("league_poisson", empirical),
        ):
            distributions[key].append(np.array(distribution.cells).ravel())
    result = test[
        [
            "competition",
            "season",
            "match_date",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
            "result",
        ]
    ].reset_index(drop=True)
    result["home_rate"], result["away_rate"] = home_rates, away_rates
    result["max_result_gap"] = gaps
    result["captured_mass"], result["rates_capped"] = masses, capped
    for index, column in enumerate(RESULT_COLUMNS):
        result[f"production_{column}"] = np.array(targets)[:, index]
    selections = initial_selections()
    masks = _settlement_masks(selections)
    columns = {}
    matrices = {model: np.array(grids) for model, grids in distributions.items()}
    for name, selection in selections.items():
        actual = [
            selection.settle(int(h), int(a))
            for h, a in zip(test.home_goals, test.away_goals, strict=True)
        ]
        columns[f"{name}__actual"] = actual
        past = [
            selection.settle(int(h), int(a))
            for h, a in zip(train.home_goals, train.away_goals, strict=True)
        ]
        # Binary climatology is conditioned on non-push observations.
        columns[f"{name}__climatology"] = (past.count("win") + 1) / (
            len(past) - past.count("push") + 2
        )
        for model, matrix in matrices.items():
            win, loss = matrix @ masks[name]["win"], matrix @ masks[name]["loss"]
            columns[f"{name}__{model}"] = win / (win + loss)
            columns[f"{name}__{model}__push"] = matrix @ masks[name]["push"]
    actual_indices = result.home_goals.to_numpy() * 13 + result.away_goals.to_numpy()
    supported = result.home_goals.le(12) & result.away_goals.le(12)
    for model, matrix in matrices.items():
        columns[f"{model}__score_probability"] = [
            float(matrix[i, score]) if ok else np.nan
            for i, (score, ok) in enumerate(zip(actual_indices, supported, strict=True))
        ]
        best = np.argmax(matrix, axis=1)
        columns[f"{model}__exact_hit"] = (best // 13 == result.home_goals) & (
            best % 13 == result.away_goals
        )
        hg, ag = np.repeat(np.arange(13), 13), np.tile(np.arange(13), 13)
        columns[f"{model}__goal_mae"] = (
            np.abs(matrix @ hg - result.home_goals) + np.abs(matrix @ ag - result.away_goals)
        ) / 2
    result = pd.concat([result, pd.DataFrame(columns)], axis=1)
    result.attrs["fit"] = {
        "home_alpha": home_model.best_params_["model__alpha"],
        "away_alpha": away_model.best_params_["model__alpha"],
    }
    return result


def binary_metrics(probabilities: np.ndarray, actual: np.ndarray) -> dict:
    if (
        len(probabilities) != len(actual)
        or not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or (probabilities > 1).any()
        or not np.isin(actual, (0, 1)).all()
    ):
        raise ValueError("binary metrics require finite probabilities and matching binary labels")
    if len(probabilities) == 0:
        return {"matches": 0}
    p = np.clip(probabilities, 1e-15, 1 - 1e-15)
    buckets, ece = [], 0.0
    for bucket in range(10):
        lower, upper = bucket / 10, (bucket + 1) / 10
        mask = (probabilities >= lower) & (
            probabilities < upper if bucket < 9 else probabilities <= 1
        )
        if mask.any():
            predicted, observed = float(probabilities[mask].mean()), float(actual[mask].mean())
            ece += mask.mean() * abs(predicted - observed)
            buckets.append(
                {
                    "lower": round(float(lower), 1),
                    "n": int(mask.sum()),
                    "predicted": predicted,
                    "observed": observed,
                }
            )
    return {
        "matches": len(p),
        "log_loss": float(np.mean(-actual * np.log(p) - (1 - actual) * np.log(1 - p))),
        "brier": float(np.mean((p - actual) ** 2)),
        "accuracy": float(np.mean((p >= 0.5) == actual)),
        "ece": float(ece),
        "calibration": buckets,
    }


def paired_season_interval(frame: pd.DataFrame, differences: np.ndarray) -> dict:
    """Resample whole seasons; two Greek seasons cannot provide robust certainty."""
    if len(frame) != len(differences) or not np.isfinite(differences).all():
        raise ValueError("paired differences must be finite and match the fixture rows")
    if frame.empty:
        return {"delta": None, "lower_95": None, "upper_95": None, "season_blocks": 0}
    block = pd.DataFrame({"season": frame.season.to_numpy(), "difference": differences})
    stats = block.groupby("season").difference.agg(["sum", "count"]).to_numpy()
    rng = np.random.default_rng(42)
    indices = rng.integers(0, len(stats), size=(2000, len(stats)))
    samples = stats[indices, 0].sum(axis=1) / stats[indices, 1].sum(axis=1)
    return {
        "delta": float(differences.mean()),
        "lower_95": float(np.quantile(samples, 0.025)),
        "upper_95": float(np.quantile(samples, 0.975)),
        "season_blocks": len(stats),
    }


def summarize(frame: pd.DataFrame) -> dict:
    summary = {"matches": len(frame), "markets": {}, "scorelines": {}}
    for name in initial_selections():
        settled = frame[frame[f"{name}__actual"] != "push"]
        actual = (settled[f"{name}__actual"] == "win").to_numpy(dtype=float)
        metrics = {
            model: binary_metrics(settled[f"{name}__{model}"].to_numpy(), actual)
            for model in ("climatology", "goal_raw", "goal_aligned")
        }
        metrics["pushes"] = len(frame) - len(settled)
        losses = {}
        for model in ("climatology", "goal_raw", "goal_aligned"):
            p = np.clip(settled[f"{name}__{model}"].to_numpy(), 1e-15, 1 - 1e-15)
            losses[model] = -actual * np.log(p) - (1 - actual) * np.log(1 - p)
        metrics["comparisons"] = {
            "aligned_minus_raw": paired_season_interval(
                settled, losses["goal_aligned"] - losses["goal_raw"]
            ),
            "raw_minus_climatology": paired_season_interval(
                settled, losses["goal_raw"] - losses["climatology"]
            ),
            "aligned_minus_climatology": paired_season_interval(
                settled, losses["goal_aligned"] - losses["climatology"]
            ),
        }
        summary["markets"][name] = metrics
    for model in ("league_poisson", "goal_raw", "goal_aligned"):
        p = frame[f"{model}__score_probability"].dropna().to_numpy()
        summary["scorelines"][model] = {
            "scored_matches": len(p),
            "unsupported_scores": len(frame) - len(p),
            "score_nll": float(-np.log(np.clip(p, 1e-15, 1)).mean()),
            "exact_accuracy": float(frame[f"{model}__exact_hit"].mean()),
            "goal_mae": float(frame[f"{model}__goal_mae"].mean()),
        }
    supported = frame.dropna(
        subset=["goal_raw__score_probability", "goal_aligned__score_probability"]
    )
    summary["scorelines"]["aligned_minus_raw"] = paired_season_interval(
        supported,
        np.log(supported["goal_raw__score_probability"].to_numpy())
        - np.log(supported["goal_aligned__score_probability"].to_numpy()),
    )
    for model in ("production", "goal_raw", "goal_aligned"):
        source = frame[["result"]].copy()
        for column, name in zip(
            RESULT_COLUMNS, ("result_home", "result_draw", "result_away"), strict=True
        ):
            source[column] = (
                frame[f"production_{column}"]
                if model == "production"
                else frame[f"{name}__{model}"]
            )
        score = evaluate_probabilities(source)
        summary[f"{model}_1x2"] = {
            "log_loss": score.log_loss,
            "brier": score.brier_score,
            "rps": score.ranked_probability_score,
            "accuracy": score.accuracy,
        }
    summary["consistency"] = {
        "mean_max_result_gap_pp": float(frame.max_result_gap.mean() * 100),
        "p95_max_result_gap_pp": float(frame.max_result_gap.quantile(0.95) * 100),
        "minimum_captured_mass": float(frame.captured_mass.min()),
        "capped_rate_matches": int(frame.rates_capped.sum()),
    }
    return summary


def run(data: Path, *, count: int = 5) -> tuple[dict, pd.DataFrame]:
    raw = pd.read_csv(data)
    features = build_pre_match_features(raw)
    # Flag a concrete upstream parsing risk, without silently repairing or
    # altering the input used by the current production recipe.
    suspicious = features[
        features.season.eq("2019-20") & (features.match_date < pd.Timestamp("2019-08-01"))
    ]
    report = {
        "dataset_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "source_sha256": {
            name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in (
                "betting.py",
                "betting_benchmark.py",
                "prediction.py",
                "features.py",
                "models.py",
                "policy.py",
                "evaluation.py",
                "sources/openfootball.py",
            )
        },
        "package_versions": {
            name: importlib.metadata.version(name) for name in ("pandas", "numpy", "scikit-learn")
        },
        "source_rows": len(raw),
        "folds": [],
        "leagues": {},
        "protocol": (
            "Frozen-season goal fits; earlier-day rolling features; unchanged production recipe; "
            "no candidate/calibration fitting on test seasons; descriptive research, "
            "not a fresh untouched holdout."
        ),
        "validation": (
            "Existing alpha grid is selected by training-only TimeSeriesSplit; no new decay, "
            "blend or calibration parameters selected in this checkpoint."
        ),
        "date_quality_warning": {
            "2019_20_rows_before_august": len(suspicious),
            "by_league": suspicious.groupby("competition").size().to_dict(),
            "policy": (
                "Retained for serving-input parity; training chronology needs a separate "
                "source/parser audit. These rows are never final test rows."
            )
            if len(suspicious)
            else (
                "No rows triggered this pre-August 2019 check. "
                "This check alone is not a general audit of all match dates."
            ),
        },
    }
    predictions = []
    for competition, season, train, test in season_folds(features, count=count):
        print(f"{competition} {season}: train {len(train)}, test {len(test)}", flush=True)
        prediction = forecast_fold(competition, train, test)
        report["folds"].append(
            {
                "competition": competition,
                "season": season,
                "train_matches": len(train),
                "train_start": str(train.match_date.min().date()),
                "train_end": str(train.match_date.max().date()),
                "test_matches": len(test),
                "test_start": str(test.match_date.min().date()),
                "test_end": str(test.match_date.max().date()),
                "fit": prediction.attrs["fit"],
            }
        )
        predictions.append(prediction)
    if not predictions:
        raise ValueError("no eligible season folds")
    combined = pd.concat(predictions, ignore_index=True)
    for competition, frame in combined.groupby("competition", sort=True):
        report["leagues"][competition] = summarize(frame)
    return report, combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/model/historical_matches.csv.gz"))
    parser.add_argument("--seasons", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path("data/local/research/betting-markets.json")
    )
    parser.add_argument(
        "--predictions", type=Path, default=Path("data/local/research/betting-markets.csv.gz")
    )
    args = parser.parse_args()
    report, predictions = run(args.data, count=args.seasons)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    predictions.to_csv(args.predictions, index=False)
    print(f"Report: {args.output}; predictions: {args.predictions}", flush=True)


if __name__ == "__main__":
    main()
