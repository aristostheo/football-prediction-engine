import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from football_predictor.domain import Competition
from football_predictor.ingestion import (
    OpenFootballFile,
    initial_openfootball_files,
    parse_openfootball_files,
    refresh_openfootball_dataset,
)


def test_parse_openfootball_files_keeps_per_file_provenance(tmp_path: Path) -> None:
    source_path = tmp_path / "results.txt"
    source_path.write_text(
        """▪ Matchday 1
  Sat Aug 17 2024
    Team A v Team B 1-0
""",
        encoding="utf-8",
    )

    matches = parse_openfootball_files(
        [
            OpenFootballFile(
                competition=Competition.PREMIER_LEAGUE,
                season="2024-25",
                path=source_path,
                source_url="https://example.com/results.txt",
            )
        ],
        retrieved_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert len(matches) == 1
    assert str(matches[0].source_url) == "https://example.com/results.txt"


def test_openfootball_sources_follow_the_current_season() -> None:
    files = initial_openfootball_files(
        england_root=Path("england"),
        europe_root=Path("europe"),
        as_of=date(2027, 2, 10),
    )

    premier_league_current = [
        item for item in files if item.competition is Competition.PREMIER_LEAGUE
    ][-1]
    greek_current = [
        item for item in files if item.competition is Competition.SUPER_LEAGUE_GREECE
    ][-1]
    assert premier_league_current.season == "2026-27"
    assert greek_current.season == "2026-27"


def test_refresh_writes_a_checksummed_dataset_and_reports_changes(tmp_path: Path) -> None:
    output_path = tmp_path / "matches.csv.gz"
    manifest_path = tmp_path / "manifest.json"
    source = OpenFootballFile(
        competition=Competition.PREMIER_LEAGUE,
        season="2026-27",
        path=tmp_path / "not-read.txt",
        source_url="https://example.com/results.txt",
    )
    source_text = """▪ Matchday 1
  Sat Sep 19 2026
    Team A v Team B 2-0
"""

    report = refresh_openfootball_dataset(
        output_path=output_path,
        manifest_path=manifest_path,
        source_files=[source],
        fetch_text=lambda _: source_text,
    )

    written = pd.read_csv(output_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(written) == 1
    assert report["added_matches"] == 1
    assert report["corrected_scores"] == 0
    assert manifest["dataset_sha256"] == hashlib.sha256(output_path.read_bytes()).hexdigest()
    assert manifest["sources"][0]["source_sha256"] == hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()


def test_refresh_keeps_dataset_bytes_when_only_provenance_changes(tmp_path: Path) -> None:
    output_path = tmp_path / "matches.csv.gz"
    manifest_path = tmp_path / "manifest.json"
    previous = pd.DataFrame(
        [
            {
                "match_date": "2026-09-19",
                "competition": Competition.PREMIER_LEAGUE.value,
                "season": "2026-27",
                "home_team": "Team A",
                "away_team": "Team B",
                "home_goals": 2,
                "away_goals": 0,
                "result": "H",
                "source_name": "OpenFootball",
                "source_url": "https://old.example/results.txt",
                "retrieved_at": "2026-09-20T00:00:00+00:00",
            }
        ]
    )
    previous.to_csv(output_path, index=False, compression="gzip")
    original_bytes = output_path.read_bytes()
    source = OpenFootballFile(
        competition=Competition.PREMIER_LEAGUE,
        season="2026-27",
        path=tmp_path / "not-read.txt",
        source_url="https://new.example/results.txt",
    )

    report = refresh_openfootball_dataset(
        output_path=output_path,
        manifest_path=manifest_path,
        source_files=[source],
        fetch_text=lambda _: """▪ Matchday 1
  Sat Sep 19 2026
    Team A v Team B 2-0
""",
    )

    assert report["added_matches"] == 0
    assert output_path.read_bytes() == original_bytes
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dataset_sha256"] == hashlib.sha256(original_bytes).hexdigest()


def test_refresh_refuses_to_remove_existing_matches_without_replacing_files(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "matches.csv.gz"
    manifest_path = tmp_path / "manifest.json"
    previous = pd.DataFrame(
        [
            {
                "match_date": "2026-09-19",
                "competition": Competition.PREMIER_LEAGUE.value,
                "season": "2026-27",
                "home_team": "Team A",
                "away_team": "Team B",
                "home_goals": 1,
                "away_goals": 0,
                "result": "H",
                "source_name": "OpenFootball",
                "source_url": "https://example.com/results.txt",
                "retrieved_at": "2026-09-20T00:00:00+00:00",
            },
            {
                "match_date": "2026-09-20",
                "competition": Competition.PREMIER_LEAGUE.value,
                "season": "2026-27",
                "home_team": "Team C",
                "away_team": "Team D",
                "home_goals": 0,
                "away_goals": 0,
                "result": "D",
                "source_name": "OpenFootball",
                "source_url": "https://example.com/results.txt",
                "retrieved_at": "2026-09-20T00:00:00+00:00",
            },
        ]
    )
    previous.to_csv(output_path, index=False, compression="gzip")
    before = output_path.read_bytes()
    source = OpenFootballFile(
        competition=Competition.PREMIER_LEAGUE,
        season="2026-27",
        path=tmp_path / "not-read.txt",
        source_url="https://example.com/results.txt",
    )

    with pytest.raises(ValueError, match="would remove 1 existing matches"):
        refresh_openfootball_dataset(
            output_path=output_path,
            manifest_path=manifest_path,
            source_files=[source],
            fetch_text=lambda _: """▪ Matchday 1
  Sat Sep 19 2026
    Team A v Team B 1-0
""",
        )

    assert output_path.read_bytes() == before
    assert not manifest_path.exists()
