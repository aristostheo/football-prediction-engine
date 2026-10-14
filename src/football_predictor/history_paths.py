"""Choose a local synced snapshot without modifying Git-tracked historical data."""

import os
from pathlib import Path

BUNDLED_HISTORY = Path("data/model/historical_matches.csv.gz")
LOCAL_HISTORY = Path("data/local/historical_matches.csv.gz")
LOCAL_MANIFEST = Path("data/local/historical_matches.manifest.json")


def runtime_history_path() -> Path:
    override = os.environ.get("HISTORICAL_MATCHES_PATH")
    if override:
        return Path(override)
    return LOCAL_HISTORY if LOCAL_HISTORY.is_file() else BUNDLED_HISTORY
