from __future__ import annotations

import re


def normalize_team_name(name: str) -> str:
    """Apply conservative whitespace normalization before source-specific aliases."""
    normalized = re.sub(r"\s+", " ", name).strip()
    if not normalized:
        raise ValueError("team name cannot be blank")
    return normalized


def normalize_season(value: str) -> str:
    """Normalize an OpenFootball-style season label to the canonical YYYY-YY form."""
    match = re.fullmatch(r"(\d{4})-(\d{2}|\d{4})", value.strip())
    if not match:
        raise ValueError(f"unsupported season format: {value!r}")

    start_year = int(match.group(1))
    end_value = match.group(2)
    end_year = int(end_value[-2:])
    if (start_year + 1) % 100 != end_year:
        raise ValueError(f"season must span consecutive years: {value!r}")
    return f"{start_year}-{end_year:02d}"
