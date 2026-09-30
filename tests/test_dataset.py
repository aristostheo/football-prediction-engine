from football_predictor.dataset import build_match_dataframe
from tests.test_domain import make_match


def test_dataset_includes_derived_result_and_provenance() -> None:
    dataset = build_match_dataframe([make_match(home_goals=0, away_goals=1)])

    assert dataset.loc[0, "result"] == "A"
    assert dataset.loc[0, "source_name"] == "Example source"
    assert dataset.loc[0, "source_url"] == "https://example.com/matches.csv"
