"""Remember successful date queries without pretending they are new results."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd

from football_predictor.domain import Competition


def read_checkpoint(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        if (
            isinstance(value, dict)
            and value.get("version") == 1
            and isinstance(value.get("leagues"), dict)
        ):
            return value
    except (OSError, ValueError):
        pass
    return {"version": 1, "leagues": {}}


def checked_dates(checkpoint: dict, history: pd.DataFrame, through: date):
    cursors, pending = {}, {}
    for competition in Competition:
        rows = history[history["competition"] == competition.value]
        record = checkpoint.get("leagues", {}).get(competition.value)
        if rows.empty or not isinstance(record, dict):
            continue
        latest = pd.to_datetime(rows["match_date"]).max().date()
        try:
            checked = date.fromisoformat(record["checked_through"])
            start = date.fromisoformat(record["checked_from"])
            if (
                record["history_through"] != latest.isoformat()
                or record["matches"] != len(rows)
                or not latest <= checked <= through
                or start > latest + timedelta(days=1)
            ):
                continue
            outstanding = {date.fromisoformat(x) for x in record.get("pending_dates", [])}
            if any(x < start or x > checked for x in outstanding):
                continue
            cursors[competition] = checked
            pending[competition] = outstanding
        except (KeyError, TypeError, ValueError):
            continue
    return cursors, pending


def write_checkpoint(path: Path, previous: dict, report: dict) -> None:
    # This runs only after validation and snapshot publication succeeded.
    # A zero-new-result success can still advance checked dates.
    checkpoint = {"version": 1, "leagues": dict(previous.get("leagues", {}))}
    coverage = {x["competition"]: x for x in report["coverage"]}
    queries = report["date_queries"]
    for league in {x["competition"] for x in queries}:
        entries = [x for x in queries if x["competition"] == league]
        old = checkpoint["leagues"].get(league, {})
        if not isinstance(old, dict):
            old = {}
        oldest, newest = min(x["date"] for x in entries), max(x["date"] for x in entries)
        pending = set(old.get("pending_dates", []))
        for item in entries:
            pending.discard(item["date"])
            if item.get("pending"):
                pending.add(item["date"])
        checkpoint["leagues"][league] = {
            "checked_from": min(old.get("checked_from", oldest), oldest),
            "checked_through": max(old.get("checked_through", newest), newest),
            "history_through": coverage[league]["history_through"],
            "matches": coverage[league]["matches"],
            "pending_dates": sorted(pending),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as tmp:
        temporary = Path(tmp.name)
        json.dump(checkpoint, tmp, indent=2)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
