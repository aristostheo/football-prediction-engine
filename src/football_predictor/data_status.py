"""Read-only reporting of the actual results cutoff, independent of retrieval time."""

from datetime import UTC, date, datetime

import pandas as pd

from football_predictor.domain import Competition


def history_coverage(
    matches: pd.DataFrame, *, as_of: date | None = None, stale_after_days: int = 21
) -> list[dict[str, object]]:
    today = as_of or datetime.now(UTC).date()
    start_year = today.year if today.month >= 7 else today.year - 1
    current_season = f"{start_year}-{str(start_year + 1)[-2:]}"
    required = {"competition", "season", "match_date"}
    if missing := required.difference(matches.columns):
        raise ValueError(f"missing coverage columns: {sorted(missing)}")
    if stale_after_days < 0:
        raise ValueError("stale_after_days must be non-negative")
    rows = []
    for competition in Competition:
        league = matches[matches["competition"] == competition.value]
        latest = (
            pd.to_datetime(league["match_date"], format="ISO8601").max().date()
            if not league.empty
            else None
        )
        age = (today - latest).days if latest else None
        rows.append(
            {
                "competition": competition.value,
                "matches": len(league),
                "history_through": latest.isoformat() if latest else None,
                "age_days": age,
                "current_season": current_season,
                "current_season_matches": int((league["season"] == current_season).sum()),
                "status": "missing"
                if latest is None
                else "dated"
                if age > stale_after_days
                else "recent",
            }
        )
    return rows


def format_coverage(rows: list[dict[str, object]]) -> str:
    lines = [
        "## Actual historical results coverage",
        "",
        "A successful download does not necessarily contain newer match results.",
        "",
        "| League | Latest result | Age (days) | Matches | Current-season matches | Status |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['competition']} | {row['history_through'] or '—'} | "
            f"{row['age_days'] if row['age_days'] is not None else '—'} | "
            f"{row['matches']} | {row['current_season_matches']} | {row['status']} |"
        )
    if any(row["status"] != "recent" for row in rows):
        lines.extend(
            [
                "",
                "**Coverage warning:** some inputs are missing or exceed the age threshold. "
                "Check the source coverage and match schedule before relying on forecasts.",
            ]
        )
    return "\n".join(lines)
