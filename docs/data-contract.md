# Canonical historical match contract

Each row represents one completed domestic-league match. This intentionally small contract is the stable interface between data collection and every later feature/model step.

| Field | Type | Rule |
| --- | --- | --- |
| `match_date` | ISO date | Local match date; must be known and parseable. |
| `competition` | enum | `premier_league` or `super_league_greece`. |
| `season` | string | Start-year format, e.g. `2024-25`. |
| `home_team` / `away_team` | string | Canonical team names; cannot be equal. |
| `home_goals` / `away_goals` | non-negative integer | Final regulation/recorded score. |
| `result` | enum | Derived only: `H`, `D`, or `A`. |
| `source_name` | string | Human-readable source identifier. |
| `source_url` | URL | Exact source page/file URL. |
| `retrieved_at` | UTC timestamp | When the source was acquired. |

## Excluded for now

Cup matches, European competitions, abandoned fixtures, and play-off stages are excluded until we define a competition-stage policy. This prevents silently mixing fundamentally different fixtures into the first model.

## Validation rules

- No duplicate `(competition, match_date, home_team, away_team)` rows.
- A team cannot play itself.
- Scores cannot be negative.
- `result` must agree with the recorded score.
- Team names must be normalized before validation.
- Rows must be sorted chronologically before feature generation.

