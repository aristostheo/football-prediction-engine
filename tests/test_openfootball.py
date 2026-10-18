from datetime import UTC, datetime

import pytest

from football_predictor.domain import Competition
from football_predictor.sources.openfootball import parse_openfootball_results

SOURCE_URL = "https://raw.githubusercontent.com/openfootball/europe/master/greece/2024-25_gr1.txt"
ENGLAND_SOURCE_URL = (
    "https://raw.githubusercontent.com/openfootball/eng-england/master/2024-25/1-premierleague.txt"
)


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
        (match.match_date.isoformat(), match.home_team, match.result.value) for match in matches
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


def test_parser_handles_premier_league_format() -> None:
    text = """= English Premier League 2024/25

▪ Matchday 1
  Fri Aug 16 2024
    20:00  Manchester United FC    v Fulham FC                1-0 (0-0)
  Sat Aug 17
    12:30  Ipswich Town FC         v Liverpool FC             0-2 (0-0)
"""
    matches = parse_openfootball_results(
        text,
        competition=Competition.PREMIER_LEAGUE,
        season="2024-25",
        source_url=ENGLAND_SOURCE_URL,
        retrieved_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert [(match.home_team, match.away_team) for match in matches] == [
        ("Manchester United FC", "Fulham FC"),
        ("Ipswich Town FC", "Liverpool FC"),
    ]


def test_parser_handles_legacy_home_score_away_format() -> None:
    text = """▪ Matchday 1
Sat Aug 19
  15:00  Charlton Athletic        4-0 (2-0)  Manchester City
"""
    matches = parse_openfootball_results(
        text,
        competition=Competition.PREMIER_LEAGUE,
        season="2000-01",
        source_url=ENGLAND_SOURCE_URL,
        retrieved_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert [(match.home_team, match.away_team, match.result.value) for match in matches] == [
        ("Charlton Athletic", "Manchester City FC", "H")
    ]


def test_parser_strips_awarded_marker_after_away_team_in_legacy_format() -> None:
    text = """▪ Matchday 1
Sat Sep 19
  20:45  Hellas Verona FC         3-0  AS Roma                  [awarded]
"""
    matches = parse_openfootball_results(
        text,
        competition=Competition.SERIE_A,
        season="2020-21",
        source_url=SOURCE_URL,
    )

    assert len(matches) == 1
    assert (matches[0].home_team, matches[0].away_team, matches[0].home_goals) == (
        "Hellas Verona",
        "AS Roma",
        3,
    )


def test_parser_reads_awarded_greek_results_without_creating_phantom_teams() -> None:
    text = """Sun Mar 17 2019
  19:00  Panathinaikos v Olympiakos Piraeus 0-3 [awarded]
"""
    matches = parse_openfootball_results(
        text,
        competition=Competition.SUPER_LEAGUE_GREECE,
        season="2018-19",
        source_url=SOURCE_URL,
    )

    assert len(matches) == 1
    assert (matches[0].home_team, matches[0].away_team, matches[0].result.value) == (
        "Panathinaikos",
        "Olympiakos Piraeus",
        "A",
    )


def test_parser_canonicalizes_historical_english_club_labels() -> None:
    text = """▪ Matchday 1
  Sat Aug 17 2024
    20:00  Aston Villa v Ipswich Town 2-0
"""
    matches = parse_openfootball_results(
        text,
        competition=Competition.PREMIER_LEAGUE,
        season="2024-25",
        source_url=ENGLAND_SOURCE_URL,
    )

    assert [(match.home_team, match.away_team) for match in matches] == [
        ("Aston Villa FC", "Ipswich Town FC")
    ]


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Fri Aug 9", "2019-08-09"),
        ("Wed Jul 1", "2020-07-01"),
        ("Sat Aug 1", "2020-08-01"),
        ("Sat Feb 29", "2020-02-29"),
        ("Mon Jul 1", "2019-07-01"),  # A real first-year July date still works.
    ],
)
def test_omitted_year_uses_weekday_including_pandemic_finish(header, expected):
    matches = parse_openfootball_results(
        f"{header}\n  Arsenal v Fulham 2-1\n",
        competition=Competition.PREMIER_LEAGUE,
        season="2019-20",
        source_url=ENGLAND_SOURCE_URL,
    )
    assert matches[0].match_date.isoformat() == expected


def test_year_inference_does_not_assume_postponed_headers_are_chronological():
    matches = parse_openfootball_results(
        "Sun Aug 2\n  Arsenal v Fulham 1-0\n"
        "Fri Aug 9\n  Fulham v Arsenal 0-0\n"
        "Sat Feb 29\n  Liverpool v Chelsea 2-1\n",
        competition=Competition.PREMIER_LEAGUE,
        season="2019-20",
        source_url=ENGLAND_SOURCE_URL,
    )
    assert [m.match_date.isoformat() for m in matches] == [
        "2020-08-02",
        "2019-08-09",
        "2020-02-29",
    ]


def test_inconsistent_omitted_year_header_fails_closed():
    with pytest.raises(ValueError, match="cannot infer year"):
        parse_openfootball_results(
            "Thu Jul 1\n  Arsenal v Fulham 1-0\n",
            competition=Competition.PREMIER_LEAGUE,
            season="2019-20",
            source_url=ENGLAND_SOURCE_URL,
        )


def test_explicit_year_is_authoritative_even_with_a_weekday_typo():
    matches = parse_openfootball_results(
        "Thu Jul 1 2020\n  Arsenal v Fulham 1-0\n",
        competition=Competition.PREMIER_LEAGUE,
        season="2019-20",
        source_url=ENGLAND_SOURCE_URL,
    )
    assert matches[0].match_date.isoformat() == "2020-07-01"
