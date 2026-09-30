from __future__ import annotations

import re


def normalize_team_name(name: str) -> str:
    """Apply conservative whitespace normalization before source-specific aliases."""
    normalized = re.sub(r"\s+", " ", name).strip()
    if not normalized:
        raise ValueError("team name cannot be blank")
    return normalized

