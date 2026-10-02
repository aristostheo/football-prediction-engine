# Pre-match feature contract

Every feature row is generated before its match result is revealed. The V1
engine processes each `(competition, match_date)` batch in two phases:

1. Create every feature row from results strictly before that date.
2. Commit all of that date's results to team histories and Elo ratings.

This means a late same-day fixture cannot see an early same-day result.

## V1 features

- Overall recent form: matches played, points per match, goals for and against
  over the prior five league matches.
- Venue-specific form: home-team home points per match and away-team away
  points per match over the prior five such fixtures.
- Rest: calendar days since each team's previous league match; the first
  recorded match is missing rather than assigned an invented rest value.
  Rest is capped at 97 days, the 99th-percentile training range.
- Long gaps: after more than 180 days without a recorded result, recent-form
  windows reset and Elo regresses toward 1500 with a 365-day half-life. This
  avoids carrying stale Greek team form across missing seasons.
- Elo: each competition has independent 1500-point starting ratings, a 60-point
  home adjustment, and K=20 updates. Ratings are stored before the match.

The initial Elo probability baseline turns pre-match home and away Elo into
three normalized probabilities. Its chronological holdout takes the most recent
20% of each competition; it never shuffles rows.
