import pytest

from football_predictor.normalization import normalize_team_name


def test_team_name_whitespace_is_normalized() -> None:
    assert normalize_team_name("  Olympiacos   FC ") == "Olympiacos FC"


def test_blank_team_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        normalize_team_name(" \t ")

