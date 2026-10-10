"""Read-only smoke check for Goal API fixture mappings across all leagues."""

from __future__ import annotations

import argparse
import os
from datetime import date

from football_predictor.domain import Competition
from football_predictor.live_fixtures import (
    FixtureProviderError,
    GoalApiFixtureProvider,
)

NEW_COMPETITIONS = (
    Competition.LA_LIGA,
    Competition.BUNDESLIGA,
    Competition.SERIE_A,
    Competition.LIGUE_1,
    Competition.PRIMEIRA_LIGA,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        help="fixture date to check in YYYY-MM-DD format (defaults to today)",
    )
    args = parser.parse_args()
    api_key = os.environ.get("GOAL_API_KEY")
    if not api_key:
        parser.error("GOAL_API_KEY is not set in this terminal")

    provider = GoalApiFixtureProvider(api_key)
    failed = False
    for competition in NEW_COMPETITIONS:
        try:
            fixtures = provider.list_fixtures(competition, args.date)
        except FixtureProviderError as error:
            failed = True
            print(f"FAIL | {competition.value} | {error}")
            continue
        print(f"OK   | {competition.value} | {len(fixtures)} fixture(s) on {args.date}")
        for fixture in fixtures:
            print(f"       {fixture.kickoff_at.isoformat()}  {fixture.home_team} vs {fixture.away_team}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
