"""Supplementary chronological ablations: rolling window and calibrated tree model.

Run from the repository root:
    PYTHONPATH=src python experiments/feature_ablation.py --data data/model/historical_matches.csv.gz
"""

import argparse
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from threadpoolctl import threadpool_limits

from football_predictor.features import FeatureConfig, build_pre_match_features
from football_predictor.market import _deployed_model_probabilities
from football_predictor.models import FEATURE_COLUMNS, _complete_season_order, _score


def split_seasons(competition, seasons):
    if competition == "premier_league":
        return seasons[16:21], seasons[21:26]
    if competition == "super_league_greece":
        return ["2019-20", "2020-21"], ["2023-24", "2024-25"]
    return [], []


def run(data_path):
    matches = pd.read_csv(data_path)
    features_by_window = {
        window: build_pre_match_features(
            matches, config=FeatureConfig(form_window=window)
        )
        for window in (5, 8, 10)
    }

    for competition in sorted(matches.competition.unique()):
        ordered5 = features_by_window[5]
        ordered5 = ordered5[ordered5.competition == competition]
        seasons = _complete_season_order(
            ordered5.sort_values("match_date").reset_index(drop=True)
        )
        validation, test_seasons = split_seasons(competition, seasons)
        if not validation or not test_seasons:
            continue
        validation_predictions = {window: [] for window in (5, 8, 10)}
        test_predictions = {window: [] for window in (5, 8, 10)}
        for phase, season_list, destination in (
            ("validation", validation, validation_predictions),
            ("test", test_seasons, test_predictions),
        ):
            for season in season_list:
                for window, all_features in features_by_window.items():
                    league = all_features[all_features.competition == competition]
                    league = league.sort_values("match_date").reset_index(drop=True)
                    heldout = league[league.season == season].copy()
                    cutoff = pd.to_datetime(heldout.match_date).min()
                    train = league[pd.to_datetime(league.match_date) < cutoff].copy()
                    destination[window].append(
                        _deployed_model_probabilities(train, heldout, competition)
                    )
        selected = min(
            validation_predictions,
            key=lambda window: _score(
                pd.concat(validation_predictions[window], ignore_index=True)
            ).metrics.log_loss,
        )
        print({
            "competition": competition,
            "validation_seasons": validation,
            "test_seasons": test_seasons,
            "selected_form_window": selected,
            "validation": {
                window: _score(pd.concat(rows, ignore_index=True)).metrics
                for window, rows in validation_predictions.items()
            },
            "test_selected": _score(
                pd.concat(test_predictions[selected], ignore_index=True)
            ).metrics,
        })

    features = features_by_window[5]
    for competition, league in features.groupby("competition", sort=True):
        ordered = league.sort_values("match_date").reset_index(drop=True)
        seasons = _complete_season_order(ordered)
        _, test_seasons = split_seasons(competition, seasons)
        predictions = []
        for season in test_seasons:
            heldout = ordered[ordered.season == season].copy()
            cutoff = pd.to_datetime(heldout.match_date).min()
            train = ordered[pd.to_datetime(ordered.match_date) < cutoff].copy()
            base = HistGradientBoostingClassifier(
                max_iter=150, learning_rate=0.06, max_leaf_nodes=15,
                min_samples_leaf=25, l2_regularization=2.0, random_state=42,
            )
            model = CalibratedClassifierCV(
                estimator=base, method="sigmoid", cv=TimeSeriesSplit(n_splits=3)
            )
            with threadpool_limits(limits=1):
                model.fit(train[list(FEATURE_COLUMNS)], train.result)
            values = model.predict_proba(heldout[list(FEATURE_COLUMNS)])
            forecast = heldout[["result", "season"]].copy()
            for index, label in enumerate(model.classes_):
                column = {"H": "p_home_win", "D": "p_draw", "A": "p_away_win"}[label]
                forecast[column] = values[:, index]
            predictions.append(forecast)
        if predictions:
            score = _score(pd.concat(predictions, ignore_index=True))
            print({
                "competition": competition,
                "tree_model": "HistGradientBoostingClassifier with chronological sigmoid calibration",
                "test_seasons": test_seasons,
                "metrics": score.metrics,
                "classwise_ece": score.calibration_error,
            })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/model/historical_matches.csv.gz")
    run(parser.parse_args().data)
