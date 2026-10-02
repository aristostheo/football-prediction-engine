from __future__ import annotations

import pandas as pd
import pytest

from football_predictor.market import (
    blend_market_probabilities,
    compare_market_assisted_walk_forward,
    compare_models_to_closing_market,
    load_market_odds_csv,
    market_probabilities_from_decimal_odds,
    prepare_market_odds,
    select_market_weight,
)
from football_predictor.models import FEATURE_COLUMNS


def test_prepare_market_odds_removes_margin_and_canonicalizes_names() -> None:
    odds = pd.DataFrame(
        [
            {
                "competition": "premier_league",
                "match_date": "2024-10-05",
                "home_team": "Nottingham Forrest",
                "away_team": "Arsenal",
                "odds_home": 3.0,
                "odds_draw": 3.4,
                "odds_away": 2.4,
            }
        ]
    )

    prepared = prepare_market_odds(odds)

    assert prepared.loc[0, "home_team"] == "Nottingham Forest FC"
    assert prepared.loc[0, "away_team"] == "Arsenal FC"
    assert sum(prepared.loc[0, ["p_home_win", "p_draw", "p_away_win"]]) == pytest.approx(1)
    assert prepared.loc[0, "p_home_win"] == pytest.approx((1 / 3) / (1 / 3 + 1 / 3.4 + 1 / 2.4))


def test_market_probability_helpers_remove_margin_and_blend_valid_probabilities() -> None:
    market = market_probabilities_from_decimal_odds(2.0, 3.0, 4.0)
    blended = blend_market_probabilities((0.5, 0.3, 0.2), market, market_weight=0.25)

    assert sum(market) == pytest.approx(1.0)
    assert blended == pytest.approx(
        tuple(
            0.75 * model + 0.25 * implied
            for model, implied in zip((0.5, 0.3, 0.2), market, strict=True)
        )
    )


def test_market_weight_selection_uses_prior_outcomes_to_choose_market_when_better() -> None:
    prior = pd.DataFrame(
        {
            "result": ["H", "D", "A"],
            "model_p_home_win": [0.34, 0.34, 0.34],
            "model_p_draw": [0.33, 0.33, 0.33],
            "model_p_away_win": [0.33, 0.33, 0.33],
            "market_p_home_win": [0.8, 0.1, 0.1],
            "market_p_draw": [0.1, 0.8, 0.1],
            "market_p_away_win": [0.1, 0.1, 0.8],
        }
    )

    assert select_market_weight(prior) == 1.0


def test_prepare_market_odds_rejects_ambiguous_duplicate_fixtures() -> None:
    row = {
        "competition": "premier_league",
        "match_date": "2024-10-05",
        "home_team": "Nottingham Forrest",
        "away_team": "Arsenal",
        "odds_home": 3.0,
        "odds_draw": 3.4,
        "odds_away": 2.4,
    }
    with pytest.raises(ValueError, match="duplicate normalized match keys"):
        prepare_market_odds(pd.DataFrame([row, {**row, "home_team": "Nottingham Forest"}]))


def test_load_footiqo_export_maps_both_competitions(tmp_path) -> None:
    source = tmp_path / "odds.csv"
    pd.DataFrame(
        [
            {
                "matchDate": "16-09-18 17:15",
                "Country": "Greece",
                "League": "Super League",
                "homeTeam": "AEL Larissa",
                "awayTeam": "Panathinaikos",
                "H": 2.0,
                "D": 3.0,
                "A": 4.0,
            },
            {
                "matchDate": "15-09-18 15:00",
                "Country": "England",
                "League": "Premier League",
                "homeTeam": "Bournemouth",
                "awayTeam": "Arsenal",
                "H": 3.0,
                "D": 3.4,
                "A": 2.4,
            },
            {
                "matchDate": "15-09-18 15:00",
                "Country": "Spain",
                "League": "La Liga",
                "homeTeam": "Barcelona",
                "awayTeam": "Girona",
                "H": 1.2,
                "D": 5.0,
                "A": 9.0,
            },
        ]
    ).to_csv(source, index=False)

    loaded = load_market_odds_csv(source)

    assert loaded["competition"].tolist() == [
        "super_league_greece",
        "premier_league",
    ]
    prepared = prepare_market_odds(loaded)
    assert prepared.loc[0, "home_team"] == "AE Lárissa"


def _season_rows(season: str, start_year: int, season_offset: int) -> list[dict[str, object]]:
    teams = [f"Club {index:02d}" for index in range(20)]
    rows: list[dict[str, object]] = []
    fixtures = [(home, away) for home in teams for away in teams if away != home]
    for index, (home, away) in enumerate(fixtures):
        date = pd.Timestamp(start_year, 8, 1) + pd.Timedelta(
            index + season_offset, unit="D"
        )
        result_code = ("H", "D", "A")[index % 3]
        home_goals, away_goals = {"H": (2, 0), "D": (1, 1), "A": (0, 2)}[result_code]
        row: dict[str, object] = {
            "competition": "premier_league",
            "match_date": date,
            "season": season,
            "home_team": home,
            "away_team": away,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "result": result_code,
        }
        row.update(
            {
                column: float(((index * (position + 3)) % 17) + 1)
                for position, column in enumerate(FEATURE_COLUMNS)
            }
        )
        row["home_elo"] = 1400.0 + (int(home[-2:]) * 7)
        row["away_elo"] = 1400.0 + (int(away[-2:]) * 7)
        row["elo_difference"] = row["home_elo"] - row["away_elo"]
        rows.append(row)
    return rows


def test_market_walk_forward_compares_only_matched_fixtures() -> None:
    features = pd.DataFrame(
        _season_rows("2022-23", 2022, 0) + _season_rows("2023-24", 2023, 500)
    )
    latest = features[features["season"] == "2023-24"]
    odds = pd.DataFrame(
        [
            {
                "competition": row.competition,
                "match_date": row.match_date,
                "home_team": row.home_team,
                "away_team": row.away_team,
                "odds_home": 2.2,
                "odds_draw": 3.2,
                "odds_away": 3.4,
            }
            for row in latest.iloc[::2].itertuples(index=False)
        ]
    )

    comparison = compare_models_to_closing_market(
        features,
        odds,
        max_test_seasons=1,
        minimum_training_matches=200,
        bootstrap_samples=100,
    )["premier_league"]

    assert comparison.tested_seasons == ("2023-24",)
    assert comparison.total_test_matches == 380
    assert comparison.matched_matches == 190
    assert comparison.odds_coverage == pytest.approx(0.5)
    assert set(comparison.model_scores) == {
        "closing_market",
        "climatology",
        "elo",
        "logistic",
        "poisson",
        "ensemble",
    }
    assert comparison.model_scores["closing_market"].metrics.matches == 190
    assert all(
        "closing_market" in pair
        for pair in comparison.paired_log_loss_differences
    )


def test_market_assist_selects_weight_from_earlier_oof_fixtures_only() -> None:
    features = pd.DataFrame(
        _season_rows("2022-23", 2022, 0)
        + _season_rows("2023-24", 2023, 400)
        + _season_rows("2024-25", 2024, 800)
        + _season_rows("2025-26", 2025, 1200)
    )
    odds_rows = []
    for row in features.itertuples(index=False):
        result_odds = {
            "H": (1.5, 4.5, 5.5),
            "D": (4.5, 1.5, 5.5),
            "A": (4.5, 5.5, 1.5),
        }[row.result]
        odds_rows.append(
            {
                "competition": row.competition,
                "match_date": row.match_date,
                "home_team": row.home_team,
                "away_team": row.away_team,
                "odds_home": result_odds[0],
                "odds_draw": result_odds[1],
                "odds_away": result_odds[2],
            }
        )

    comparison = compare_market_assisted_walk_forward(
        features,
        pd.DataFrame(odds_rows),
        max_test_seasons=1,
        minimum_training_matches=200,
        minimum_tuning_matches=400,
        minimum_tuning_seasons=2,
    )["premier_league"]

    assert len(comparison.folds) == 1
    fold = comparison.folds[0]
    assert fold.season == "2025-26"
    assert fold.test_matches == 380
    assert fold.tuning_matches == 760
    assert fold.tuning_seasons == (
        "premier_league:2023-24",
        "premier_league:2024-25",
    )
    assert fold.market_weight == 1.0
    assert comparison.pooled_market_assisted_score.metrics.log_loss == pytest.approx(
        comparison.pooled_closing_market_score.metrics.log_loss
    )
