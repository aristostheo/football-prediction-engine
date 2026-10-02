import pytest

from football_predictor.validation import validate_completed_season, validate_match_collection
from tests.test_domain import make_match


def test_matches_are_chronologically_sorted() -> None:
    matches = validate_match_collection(
        [make_match(match_date="2025-08-24"), make_match(match_date="2025-08-16")]
    )
    assert [str(match.match_date) for match in matches] == ["2025-08-16", "2025-08-24"]


def test_duplicate_matches_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_match_collection([make_match(), make_match()])


@pytest.mark.parametrize("team", ["Panathinaikos v Olympiakos", "[awarded]"])
def test_malformed_source_annotations_cannot_become_team_names(team: str) -> None:
    with pytest.raises(ValueError, match="malformed team name"):
        validate_match_collection([make_match(home_team=team)])


def test_completed_season_validation_checks_every_club_schedule() -> None:
    fixtures = [
        ("2025-08-01", "A", "B"),
        ("2025-08-01", "C", "D"),
        ("2025-08-08", "A", "C"),
        ("2025-08-08", "D", "B"),
        ("2025-08-15", "A", "D"),
        ("2025-08-15", "B", "C"),
    ]
    matches = [
        make_match(match_date=match_date, home_team=home, away_team=away)
        for match_date, home, away in fixtures
    ]

    assert len(validate_completed_season(matches, expected_matches_per_team=3)) == 6
    with pytest.raises(ValueError, match="expected 4 matches per team"):
        validate_completed_season(matches, expected_matches_per_team=4)
