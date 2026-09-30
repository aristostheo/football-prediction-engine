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

OPENFOOTBALL_ENGLAND_RAW = "https://raw.githubusercontent.com/openfootball/eng-england/master"
OPENFOOTBALL_EUROPE_RAW = "https://raw.githubusercontent.com/openfootball/europe/master"

PREMIER_LEAGUE_SEASONS = tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(2000, 2025))
GREEK_SUPER_LEAGUE_SEASONS = ("2018-19", "2019-20", "2020-21", "2023-24", "2024-25")


@dataclass(frozen=True)
class OpenFootballFile:
    """One local OpenFootball result file and the provenance stored with its rows."""

    competition: Competition
    season: str
    path: Path
    source_url: str


def initial_openfootball_files(
    *, england_root: Path, europe_root: Path
) -> tuple[OpenFootballFile, ...]:
    """Return the deliberately fixed, completed-season input set for the first dataset."""
    premier_league = tuple(
        OpenFootballFile(
            competition=Competition.PREMIER_LEAGUE,
            season=season,
            path=england_root / season / "1-premierleague.txt",
            source_url=f"{OPENFOOTBALL_ENGLAND_RAW}/{season}/1-premierleague.txt",
        )
        for season in PREMIER_LEAGUE_SEASONS
    )
    super_league_greece = tuple(
        OpenFootballFile(
            competition=Competition.SUPER_LEAGUE_GREECE,
            season=season,
            path=europe_root / "greece" / f"{season}_gr1.txt",
            source_url=f"{OPENFOOTBALL_EUROPE_RAW}/greece/{season}_gr1.txt",
        )
        for season in GREEK_SUPER_LEAGUE_SEASONS
    )
    return premier_league + super_league_greece


def parse_openfootball_files(
    source_files: Iterable[OpenFootballFile], *, retrieved_at: datetime
) -> list[HistoricalMatch]:
    """Parse a fixed set of local source files with one consistent retrieval timestamp."""
    matches: list[HistoricalMatch] = []
    for source_file in source_files:
        if not source_file.path.is_file():
            raise FileNotFoundError(f"missing source file: {source_file.path}")
        matches.extend(
            parse_openfootball_results(
                source_file.path.read_text(encoding="utf-8"),
                competition=source_file.competition,
                season=source_file.season,
                source_url=source_file.source_url,
                retrieved_at=retrieved_at,
            )
        )
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
    source_files = initial_openfootball_files(
        england_root=england_root, europe_root=europe_root
    )
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
            }
            for source_file in source_files
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
