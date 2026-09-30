from datetime import UTC, datetime

from football_predictor.domain import Competition
from football_predictor.sources.openfootball import parse_openfootball_results

SOURCE_URL = "https://raw.githubusercontent.com/openfootball/europe/master/greece/2024-25_gr1.txt"


def test_parser_handles_season_boundary_and_excludes_playoffs() -> None:
    text = """= Greek Super League 2024/25

▪ Matchday 1
  Sat Aug 17 2024
    20:00  Volos NFC               v Olympiakos Piraeus       0-2 (0-1)
  Sun Jan 5
    19:30  PAOK Saloniki           v AEK Athen                1-1

▪ Championship, Matchday 1
  Sun Mar 30
    19:00  AEK Athen               v PAOK Saloniki            2-3 (1-0)
"""
    matches = parse_openfootball_results(
        text,
        competition=Competition.SUPER_LEAGUE_GREECE,
        season="2024-25",
        source_url=SOURCE_URL,
        retrieved_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    actual = [
        (match.match_date.isoformat(), match.home_team, match.result.value)
        for match in matches
    ]
    assert actual == [
        ("2024-08-17", "Volos NFC", "A"),
        ("2025-01-05", "PAOK Saloniki", "D"),
    ]


def test_parser_rejects_a_match_without_a_date_header() -> None:
    text = """▪ Matchday 1
    Volos NFC v Olympiakos Piraeus 0-2
"""

    try:
        parse_openfootball_results(
            text,
            competition=Competition.SUPER_LEAGUE_GREECE,
            season="2024-25",
            source_url=SOURCE_URL,
        )
    except ValueError as error:
        assert "before its date" in str(error)
    else:
        raise AssertionError("expected a missing date header to fail")
