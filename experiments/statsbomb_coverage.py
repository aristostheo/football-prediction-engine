"""Audit the overlap between StatsBomb Open Data and bundled results.

This is a data-availability check, not a model benchmark. It never contacts an
API and never changes the production predictor.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from football_predictor.dataset import canonicalize_match_labels
from football_predictor.domain import Competition

STATSBOMB_LEAGUES = {
    ("England", "Premier League"): Competition.PREMIER_LEAGUE,
    ("Spain", "La Liga"): Competition.LA_LIGA,
    ("Germany", "1. Bundesliga"): Competition.BUNDESLIGA,
    ("Italy", "Serie A"): Competition.SERIE_A,
    ("France", "Ligue 1"): Competition.LIGUE_1,
    ("Greece", "Super League 1"): Competition.SUPER_LEAGUE_GREECE,
    ("Greece", "Super League"): Competition.SUPER_LEAGUE_GREECE,
    ("Portugal", "Primeira Liga"): Competition.PRIMEIRA_LIGA,
}
MATCH_KEY = ["competition", "match_date", "home_team", "away_team"]


def load_statsbomb_available_matches(root: Path) -> pd.DataFrame:
    """Read official competition/season match files, keeping event-available rows."""
    catalog_path = root / "data" / "competitions.json"
    if not catalog_path.exists():
        raise FileNotFoundError(f"missing StatsBomb catalog: {catalog_path}")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for item in catalog:
        competition = STATSBOMB_LEAGUES.get((item["country_name"], item["competition_name"]))
        if competition is None or (item["competition_id"], item["season_id"]) in seen:
            continue
        seen.add((item["competition_id"], item["season_id"]))
        path = root / "data" / "matches" / str(item["competition_id"]) / f"{item['season_id']}.json"
        if not path.exists():
            continue
        for match in json.loads(path.read_text(encoding="utf-8")):
            if match.get("match_status") != "available":
                continue
            rows.append(
                {
                    "competition": competition.value,
                    "season": item["season_name"],
                    "match_date": match["match_date"],
                    "home_team": match["home_team"]["home_team_name"],
                    "away_team": match["away_team"]["away_team_name"],
                    "home_goals": match["home_score"],
                    "away_goals": match["away_score"],
                    "statsbomb_match_id": match["match_id"],
                }
            )
    if not rows:
        raise ValueError("no supported StatsBomb matches marked available were found")
    matches = pd.DataFrame(rows)
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="raise").dt.strftime(
        "%Y-%m-%d"
    )
    matches = canonicalize_match_labels(matches)
    return matches


def audit_overlap(
    statsbomb: pd.DataFrame, historical: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return per-season and per-league exact-key/score overlap reports."""
    events = statsbomb.copy()
    events["match_date"] = pd.to_datetime(events["match_date"], errors="raise").dt.strftime(
        "%Y-%m-%d"
    )
    events = canonicalize_match_labels(events)
    source = historical.copy()
    source["match_date"] = pd.to_datetime(source["match_date"], errors="raise").dt.strftime(
        "%Y-%m-%d"
    )
    source = canonicalize_match_labels(source)
    duplicate_keys = source.duplicated(MATCH_KEY, keep=False)
    if duplicate_keys.any():
        raise ValueError("historical data contains duplicate match keys")
    joined = events.merge(
        source, on=MATCH_KEY, how="left", suffixes=("_statsbomb", "_history"), indicator=True
    )
    joined["overlap"] = joined["_merge"].eq("both")
    joined["score_match"] = (
        joined["overlap"]
        & joined["home_goals_statsbomb"].eq(joined["home_goals_history"])
        & joined["away_goals_statsbomb"].eq(joined["away_goals_history"])
    )
    season_report = (
        joined.groupby(["competition", "season_statsbomb"], as_index=False)
        .agg(
            statsbomb_matches=("statsbomb_match_id", "size"),
            history_key_matches=("overlap", "sum"),
            score_matches=("score_match", "sum"),
            first_match=("match_date", "min"),
            last_match=("match_date", "max"),
        )
        .sort_values(["competition", "season_statsbomb"])
        .reset_index(drop=True)
    )
    season_report = season_report.rename(columns={"season_statsbomb": "season"})
    league_report = (
        season_report.groupby("competition", as_index=False)
        .agg(
            statsbomb_matches=("statsbomb_matches", "sum"),
            history_key_matches=("history_key_matches", "sum"),
            score_matches=("score_matches", "sum"),
            available_seasons=("season", "nunique"),
            first_match=("first_match", "min"),
            last_match=("last_match", "max"),
        )
        .sort_values("competition")
        .reset_index(drop=True)
    )
    return season_report, league_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--statsbomb-root", type=Path, required=True, help="Local sparse checkout of hudl/open-data"
    )
    parser.add_argument(
        "--history", type=Path, default=Path("data/model/historical_matches.csv.gz")
    )
    parser.add_argument(
        "--output", type=Path, help="Optional CSV destination for the per-season report"
    )
    args = parser.parse_args()
    statsbomb = load_statsbomb_available_matches(args.statsbomb_root)
    season_report, league_report = audit_overlap(statsbomb, pd.read_csv(args.history))
    print(
        "StatsBomb available-match overlap with bundled history "
        "(exact date + canonical home/away teams)"
    )
    print(league_report.to_string(index=False))
    print("\nPer-season detail")
    print(season_report.to_string(index=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        season_report.to_csv(args.output, index=False)
        print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
