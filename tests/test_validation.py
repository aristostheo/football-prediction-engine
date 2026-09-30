import pytest

from football_predictor.validation import validate_match_collection
from tests.test_domain import make_match


def test_matches_are_chronologically_sorted() -> None:
    matches = validate_match_collection(
        [make_match(match_date="2025-08-24"), make_match(match_date="2025-08-16")]
    )
    assert [str(match.match_date) for match in matches] == ["2025-08-16", "2025-08-24"]


def test_duplicate_matches_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_match_collection([make_match(), make_match()])
