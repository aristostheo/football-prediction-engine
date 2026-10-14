from pathlib import Path

import pandas as pd
import pytest

from football_predictor.domain import Competition
from football_predictor.team_names import (
    TEAM_ALIASES,
    canonical_team_name,
    is_registered_team,
    resolve_team_name,
)


@pytest.fixture(scope="module")
def historical_teams() -> dict[Competition, set[str]]:
    history = pd.read_csv(Path(__file__).parents[1] / "data/model/historical_matches.csv.gz")
    return {
        Competition(competition): set(rows.home_team) | set(rows.away_team)
        for competition, rows in history.groupby("competition")
    }


@pytest.mark.parametrize("competition", list(Competition))
def test_every_registered_historical_club_and_alias_resolves(
    historical_teams: dict[Competition, set[str]], competition: Competition
) -> None:
    known = historical_teams[competition]
    for canonical, aliases in TEAM_ALIASES[competition].items():
        if canonical not in known:
            # These recognized clubs use a conservative prior until results arrive.
            assert canonical in {"Iraklis", "Kalamata"}
            assert is_registered_team(canonical, competition)
            continue
        for name in (canonical, *aliases):
            assert resolve_team_name(name, competition, known) == canonical, name
            assert resolve_team_name(f"  {name.upper()} F.C.  ", competition, known) == canonical


@pytest.mark.parametrize("competition", list(Competition))
def test_registry_covers_all_real_clubs_in_bundled_history(
    historical_teams: dict[Competition, set[str]], competition: Competition
) -> None:
    # Two awarded-result rows contain parser artifacts, not extra clubs. They
    # are deliberately not registered as valid aliases or prediction choices.
    artifacts = {"[awarded]", "AE Kifisias v Volos NFC", "Panathinaikos v Olympiakos Piraeus"}
    for name in historical_teams[competition] - artifacts:
        assert canonical_team_name(name, competition) in TEAM_ALIASES[competition], name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Bournemouth", "AFC Bournemouth"),
        ("Brighton", "Brighton & Hove Albion FC"),
        ("Brighton and Hove Albion", "Brighton & Hove Albion FC"),
        ("Man Utd", "Manchester United FC"),
        ("Aston Villa", "Aston Villa FC"),
        ("Tottenham", "Tottenham Hotspur FC"),
        ("Wolves", "Wolverhampton Wanderers FC"),
        ("Nottingham", "Nottingham Forest FC"),
    ],
)
def test_english_provider_examples_use_recent_historical_labels(
    historical_teams: dict[Competition, set[str]], name: str, expected: str
) -> None:
    league = Competition.PREMIER_LEAGUE
    assert resolve_team_name(name, league, historical_teams[league]) == expected


@pytest.mark.parametrize(
    ("competition", "name", "expected"),
    [
        (Competition.LA_LIGA, "Barcelona", "FC Barcelona"),
        (Competition.LA_LIGA, "Alaves", "Deportivo Alavés"),
        (Competition.BUNDESLIGA, "Bayern", "FC Bayern München"),
        (Competition.BUNDESLIGA, "Cologne", "1. FC Köln"),
        (Competition.SERIE_A, "Inter", "FC Internazionale Milano"),
        (Competition.SERIE_A, "Roma", "AS Roma"),
        (Competition.LIGUE_1, "PSG", "Paris Saint-Germain FC"),
        (Competition.LIGUE_1, "Marseille", "Olympique de Marseille"),
        (Competition.PRIMEIRA_LIGA, "Benfica", "Sport Lisboa e Benfica"),
        (Competition.PRIMEIRA_LIGA, "Sporting CP", "Sporting Clube de Portugal"),
    ],
)
def test_new_league_provider_names_resolve_to_historical_clubs(
    historical_teams: dict[Competition, set[str]],
    competition: Competition,
    name: str,
    expected: str,
) -> None:
    assert resolve_team_name(name, competition, historical_teams[competition]) == expected


def test_aliases_do_not_cross_leagues_or_guess_unrelated_clubs() -> None:
    greek_teams = {"Olympiakos Piraeus", "PAOK Saloniki"}
    assert resolve_team_name("Olympiacos", Competition.PREMIER_LEAGUE, greek_teams) == "Olympiacos"
    assert resolve_team_name("Olympiacos", Competition.SUPER_LEAGUE_GREECE, greek_teams) == (
        "Olympiakos Piraeus"
    )
    assert (
        resolve_team_name(
            "Manchester", Competition.PREMIER_LEAGUE, {"Manchester City FC", "Manchester United FC"}
        )
        == "Manchester"
    )
    assert resolve_team_name("Arsenal U21", Competition.PREMIER_LEAGUE, {"Arsenal FC"}) == (
        "Arsenal U21"
    )
    assert is_registered_team("Kalamata FC", Competition.SUPER_LEAGUE_GREECE)
    assert not is_registered_team("Made Up FC", Competition.PREMIER_LEAGUE)


def test_resolver_supports_old_only_history_and_refuses_ambiguous_fallback() -> None:
    league = Competition.PREMIER_LEAGUE
    assert resolve_team_name("Man Utd", league, {"Manchester United"}) == "Manchester United"
    assert resolve_team_name("Example", league, {"Example FC", "Example AFC"}) == "Example"


@pytest.mark.parametrize(
    ("competition", "old", "current"),
    [
        (Competition.BUNDESLIGA, "Bayern München", "FC Bayern München"),
        (Competition.BUNDESLIGA, "Bor. Mönchengladbach", "Borussia Mönchengladbach"),
        (Competition.BUNDESLIGA, "1899 Hoffenheim", "TSG 1899 Hoffenheim"),
        (Competition.BUNDESLIGA, "Werder Bremen", "SV Werder Bremen"),
        (Competition.LA_LIGA, "RC Celta", "RC Celta de Vigo"),
        (Competition.LA_LIGA, "CD Alavés", "Deportivo Alavés"),
        (Competition.LIGUE_1, "RC Lens", "Racing Club de Lens"),
        (Competition.PRIMEIRA_LIGA, "SL Benfica", "Sport Lisboa e Benfica"),
        (Competition.SERIE_A, "Lazio Roma", "SS Lazio"),
    ],
)
def test_archive_and_current_labels_share_one_club_identity(competition, old, current) -> None:
    assert canonical_team_name(old, competition) == current
    assert canonical_team_name(current, competition) == current
