"""Reproducible ingestion of the project's initial OpenFootball dataset."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from football_predictor.dataset import build_match_dataframe
from football_predictor.domain import Competition, HistoricalMatch
from football_predictor.sources.openfootball import parse_openfootball_results
from football_predictor.validation import validate_completed_season, validate_match_collection

OPENFOOTBALL_ENGLAND_RAW = "https://raw.githubusercontent.com/openfootball/england/master"
OPENFOOTBALL_EUROPE_RAW = "https://raw.githubusercontent.com/openfootball/europe/master"

PREMIER_LEAGUE_SEASONS = tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(2000, 2026))
PREMIER_LEAGUE_CURRENT_SEASON = "2026-27"
GREEK_SUPER_LEAGUE_SEASONS = (
    "2018-19",
    "2019-20",
    "2020-21",
    "2023-24",
    "2024-25",
    "2025-26",
    "2026-27",
)
GREEK_MATCHES_PER_TEAM = {
    "2018-19": 30,
    "2019-20": 26,
    "2020-21": 26,
    "2023-24": 26,
    "2024-25": 26,
}
GREEK_TEAMS_PER_SEASON = {
    "2018-19": 16,
    "2019-20": 14,
    "2020-21": 14,
    "2023-24": 14,
    "2024-25": 14,
}


@dataclass(frozen=True)
class OpenFootballFile:
    """One local OpenFootball result file and the provenance stored with its rows."""

    competition: Competition
    season: str
    path: Path
    source_url: str
    expected_matches_per_team: int | None = None
    expected_team_count: int | None = None


def initial_openfootball_files(
    *, england_root: Path, europe_root: Path
) -> tuple[OpenFootballFile, ...]:
    """Return the versioned complete and in-progress OpenFootball source set."""
    premier_league_completed = tuple(
        OpenFootballFile(
            competition=Competition.PREMIER_LEAGUE,
            season=season,
            path=england_root / season / "1-premierleague.txt",
            source_url=f"{OPENFOOTBALL_ENGLAND_RAW}/{season}/1-premierleague.txt",
            expected_matches_per_team=38,
            expected_team_count=20,
        )
        for season in PREMIER_LEAGUE_SEASONS
    )
    premier_league_current = OpenFootballFile(
        competition=Competition.PREMIER_LEAGUE,
        season=PREMIER_LEAGUE_CURRENT_SEASON,
        path=england_root / PREMIER_LEAGUE_CURRENT_SEASON / "1-premierleague.txt",
        source_url=(
            f"{OPENFOOTBALL_ENGLAND_RAW}/{PREMIER_LEAGUE_CURRENT_SEASON}/1-premierleague.txt"
        ),
    )
    super_league_greece = tuple(
        OpenFootballFile(
            competition=Competition.SUPER_LEAGUE_GREECE,
            season=season,
            path=europe_root / "greece" / f"{season}_gr1.txt",
            source_url=f"{OPENFOOTBALL_EUROPE_RAW}/greece/{season}_gr1.txt",
            expected_matches_per_team=GREEK_MATCHES_PER_TEAM.get(season),
            expected_team_count=GREEK_TEAMS_PER_SEASON.get(season),
        )
        for season in GREEK_SUPER_LEAGUE_SEASONS
    )
    return premier_league_completed + (premier_league_current,) + super_league_greece


def parse_openfootball_files(
    source_files: Iterable[OpenFootballFile], *, retrieved_at: datetime
) -> list[HistoricalMatch]:
    """Parse local source files with one consistent retrieval timestamp."""
    matches: list[HistoricalMatch] = []
    for source_file in source_files:
        if not source_file.path.is_file():
            raise FileNotFoundError(f"missing source file: {source_file.path}")
        parsed = parse_openfootball_results(
            source_file.path.read_text(encoding="utf-8"),
            competition=source_file.competition,
            season=source_file.season,
            source_url=source_file.source_url,
            retrieved_at=retrieved_at,
        )
        if source_file.expected_matches_per_team is not None:
            parsed = validate_completed_season(
                parsed,
                expected_matches_per_team=source_file.expected_matches_per_team,
                expected_team_count=source_file.expected_team_count,
            )
        else:
            parsed = validate_match_collection(parsed)
        matches.extend(parsed)
    return matches


def write_initial_dataset(
    *,
    england_root: Path,
    europe_root: Path,
    output_path: Path,
    manifest_path: Path,
    retrieved_at: datetime | None = None,
) -> dict[str, object]:
    """Build the first two-competition CSV plus a small, auditable manifest."""
    retrieved_at = retrieved_at or datetime.now(UTC)
    source_files = initial_openfootball_files(england_root=england_root, europe_root=europe_root)
    matches = parse_openfootball_files(source_files, retrieved_at=retrieved_at)
    dataframe = build_match_dataframe(matches)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False)

    counts = dataframe.groupby("competition").size().sort_index().to_dict()
    manifest = {
        "schema_version": 1,
        "generated_at": retrieved_at.isoformat(),
        "total_matches": len(dataframe),
        "matches_by_competition": counts,
        "sources": [
            {
                "competition": source_file.competition.value,
                "season": source_file.season,
                "source_url": source_file.source_url,
                "expected_matches_per_team": source_file.expected_matches_per_team,
                "expected_team_count": source_file.expected_team_count,
                "complete_season": source_file.expected_matches_per_team is not None,
            }
            for source_file in source_files
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
