"""Leakage-safe H2H ablation on validation and later-season test data.

Run from repository root:
    PYTHONPATH=src python experiments/h2h_ablation.py --data data/model/historical_matches.csv.gz
"""

import argparse
import math
import numpy as np
import pandas as pd

from probability_benchmark import predict_dc
from football_predictor.models import _complete_season_order, _score


def score_probabilities(home_rate, away_rate, rho):
    grid = np.array([
        [
            math.exp(-home_rate + h * math.log(home_rate) - math.lgamma(h + 1))
            * math.exp(-away_rate + a * math.log(away_rate) - math.lgamma(a + 1))
            for a in range(13)
        ]
        for h in range(13)
    ])
    grid[0, 0] *= 1 - home_rate * away_rate * rho
    grid[0, 1] *= 1 + home_rate * rho
    grid[1, 0] *= 1 + away_rate * rho
    grid[1, 1] *= 1 - rho
    grid = np.maximum(grid, 1e-12)
    grid /= grid.sum()
    return [
        grid[np.tril_indices(13, -1)].sum(),
        np.trace(grid),
        grid[np.triu_indices(13, 1)].sum(),
    ]


def h2h_forecasts(pair_groups, fixtures, base, mode, alpha):
    rows = []
    for index, fixture in enumerate(fixtures.itertuples()):
        pair = tuple(sorted((fixture.home_team, fixture.away_team)))
        history = pair_groups.get(pair, pd.DataFrame())
        history = history[history.match_date < fixture.match_date].tail(5)
        if mode == "venue":
            history = history[
                (history.home_team == fixture.home_team)
                & (history.away_team == fixture.away_team)
            ]
        if history.empty:
            rows.append(base[index])
            continue
        days_old = (fixture.match_date - history.match_date).dt.days.to_numpy()
        time_weights = np.exp(-math.log(2) * days_old / 365)
        time_weights /= time_weights.sum()
        home_goals = np.where(
            history.home_team.to_numpy() == fixture.home_team,
            history.home_goals.to_numpy(),
            history.away_goals.to_numpy(),
        )
        away_goals = np.where(
            history.home_team.to_numpy() == fixture.home_team,
            history.away_goals.to_numpy(),
            history.home_goals.to_numpy(),
        )
        # Shrink small H2H samples toward the fitted goal model.
        blend = alpha * len(history) / (len(history) + 5)
        home_rate = (1 - blend) * fixture.dc_lh + blend * np.dot(time_weights, home_goals)
        away_rate = (1 - blend) * fixture.dc_la + blend * np.dot(time_weights, away_goals)
        rows.append(score_probabilities(max(0.05, home_rate), max(0.05, away_rate), fixture.dc_rho))
    forecast = fixtures[["result", "season"]].copy()
    forecast[["p_home_win", "p_draw", "p_away_win"]] = np.asarray(rows)
    return forecast


def season_splits(competition, seasons):
    if competition == "premier_league":
        return seasons[16:21], seasons[21:26], 365
    if competition == "super_league_greece":
        return ["2019-20", "2020-21"], ["2023-24", "2024-25"], 180
    return [], [], 365


def run(data_path):
    matches = pd.read_csv(data_path)
    matches["match_date"] = pd.to_datetime(matches.match_date)
    from football_predictor.features import build_pre_match_features
    features = build_pre_match_features(matches)
    settings = [("none", 0.0)] + [
        (mode, alpha)
        for mode in ("overall", "venue")
        for alpha in (0.05, 0.10, 0.20, 0.30)
    ]
    for competition, league in features.groupby("competition", sort=True):
        league = league.sort_values("match_date").reset_index(drop=True)
        seasons = _complete_season_order(league)
        validation, test_seasons, half_life = season_splits(competition, seasons)
        if not validation or not test_seasons:
            continue
        raw = matches[matches.competition == competition].copy()
        raw["_pair"] = [
            tuple(sorted((home, away)))
            for home, away in zip(raw.home_team, raw.away_team)
        ]
        pair_groups = {
            pair: group.sort_values("match_date")
            for pair, group in raw.groupby("_pair")
        }
        validation_predictions = {setting: [] for setting in settings}
        test_predictions = {setting: [] for setting in settings}
        for season in validation + test_seasons:
            fixtures = league[league.season == season].copy()
            cutoff = pd.to_datetime(fixtures.match_date).min()
            train = league[pd.to_datetime(league.match_date) < cutoff].copy()
            dc = predict_dc(train, fixtures, half_life, False)
            h2h_rows = fixtures[
                ["result", "season", "match_date", "home_team", "away_team"]
            ].copy()
            h2h_rows["dc_lh"] = dc.lambda_home.to_numpy()
            h2h_rows["dc_la"] = dc.lambda_away.to_numpy()
            h2h_rows["dc_rho"] = dc.rho.to_numpy()
            base = np.asarray([
                score_probabilities(row.dc_lh, row.dc_la, row.dc_rho)
                for row in h2h_rows.itertuples()
            ])
            destination = (
                validation_predictions if season in validation else test_predictions
            )
            for setting in settings:
                destination[setting].append(
                    h2h_forecasts(pair_groups, h2h_rows, base, *setting)
                )
        validation_scores = {
            setting: _score(pd.concat(rows, ignore_index=True)).metrics.log_loss
            for setting, rows in validation_predictions.items()
        }
        selected = min(validation_scores, key=validation_scores.get)
        print({
            "competition": competition,
            "validation_seasons": validation,
            "test_seasons": test_seasons,
            "selected_h2h_setting": selected,
            "validation_log_loss_no_h2h": validation_scores[("none", 0.0)],
            "validation_log_loss_selected": validation_scores[selected],
            "test_no_h2h": _score(pd.concat(
                test_predictions[("none", 0.0)], ignore_index=True
            )).metrics,
            "test_selected_h2h": _score(pd.concat(
                test_predictions[selected], ignore_index=True
            )).metrics,
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/model/historical_matches.csv.gz")
    run(parser.parse_args().data)
