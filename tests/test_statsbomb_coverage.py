import pandas as pd

from experiments.statsbomb_coverage import audit_overlap


def test_statsbomb_coverage_requires_same_date_teams_and_score_for_confirmed_overlap():
    statsbomb = pd.DataFrame(
        [
            {
                "competition": "premier_league",
                "season": "2015/2016",
                "match_date": "2015-08-08",
                "home_team": "Aston Villa",
                "away_team": "AFC Bournemouth",
                "home_goals": 0,
                "away_goals": 1,
                "statsbomb_match_id": 1,
            },
            {
                "competition": "premier_league",
                "season": "2015/2016",
                "match_date": "2015-08-09",
                "home_team": "Chelsea",
                "away_team": "Swansea City",
                "home_goals": 2,
                "away_goals": 2,
                "statsbomb_match_id": 2,
            },
        ]
    )
    history = pd.DataFrame(
        [
            {
                "competition": "premier_league",
                "season": "2015-16",
                "match_date": "2015-08-08",
                "home_team": "Aston Villa FC",
                "away_team": "Bournemouth",
                "home_goals": 0,
                "away_goals": 1,
            },
            {
                "competition": "premier_league",
                "season": "2015-16",
                "match_date": "2015-08-09",
                "home_team": "Chelsea FC",
                "away_team": "Swansea City",
                "home_goals": 0,
                "away_goals": 2,
            },
        ]
    )

    seasons, leagues = audit_overlap(statsbomb, history)

    assert seasons.loc[0, "statsbomb_matches"] == 2
    assert seasons.loc[0, "history_key_matches"] == 2
    assert seasons.loc[0, "score_matches"] == 1
    assert leagues.loc[0, "score_matches"] == 1
