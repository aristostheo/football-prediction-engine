from datetime import UTC, datetime
from pathlib import Path

from football_predictor.domain import Competition
from football_predictor.ingestion import OpenFootballFile, parse_openfootball_files


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
