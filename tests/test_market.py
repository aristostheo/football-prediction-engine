from __future__ import annotations

import pandas as pd
import pytest

from football_predictor.market import (
    compare_models_to_closing_market,
    load_market_odds_csv,
    prepare_market_odds,
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
