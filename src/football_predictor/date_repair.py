"""Offline, explicit migration of reviewed historical date corrections.

The bundled correction map identifies fixtures and expected scores exactly.
Newer local Goal API results, API checkpoints and keys are never replaced.
Run without --apply to inspect the plan; applying saves checksum-named backups.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from football_predictor.dataset import canonicalize_match_labels
from football_predictor.domain import HistoricalMatch
from football_predictor.history_paths import LOCAL_HISTORY, LOCAL_MANIFEST
from football_predictor.ingestion import write_dataset_snapshot
from football_predictor.validation import validate_match_collection

CORRECTIONS = Path("data/model/date_corrections.json")


def repair_dates(history: pd.DataFrame, corrections: dict) -> tuple[pd.DataFrame, dict]:
    if corrections.get("schema_version") != 1 or not isinstance(corrections.get("fixtures"), list):
        raise ValueError("unsupported date-correction map")
    fixed = canonicalize_match_labels(history).reset_index(drop=True)
    fixed["match_date"] = pd.to_datetime(fixed.match_date).dt.strftime("%Y-%m-%d")
    changed, already, absent = [], 0, 0
    seen = set()
    for correction in corrections["fixtures"]:
        key = tuple(correction[k] for k in ("competition", "season", "home_team", "away_team"))
        if key in seen:
            raise ValueError("duplicate fixture in date-correction map")
        seen.add(key)
        old, new = correction["old_date"], correction["new_date"]
        if (
            pd.Timestamp(old).strftime("%Y-%m-%d") != old
            or pd.Timestamp(new).strftime("%Y-%m-%d") != new
            or old == new
        ):
            raise ValueError("correction dates must be distinct ISO dates")
        same_pair = pd.Series(True, index=fixed.index)
        for column, value in zip(
            ("competition", "season", "home_team", "away_team"), key, strict=True
        ):
            same_pair &= fixed[column].eq(value)
        rows = fixed[same_pair]
        if rows.empty:
            absent += 1
            continue
        if len(rows) != 1 or rows.iloc[0].match_date not in {old, new}:
            raise ValueError(f"ambiguous or unexpected date for corrected fixture: {key}")
        row = rows.iloc[0]
        if any(
            row[column] != correction[column] for column in ("home_goals", "away_goals", "result")
        ):
            raise ValueError(f"score conflict for corrected fixture: {key}")
        if row.match_date == new:
            already += 1
            continue
        if row.source_name != "OpenFootball" or row.source_url != correction["source_url"]:
            raise ValueError(f"source conflict for corrected fixture: {key}")
        fixed.loc[rows.index[0], "match_date"] = new
        changed.append(correction)
    records = []
    for row in fixed.to_dict("records"):
        match = HistoricalMatch.model_validate(row)
        if row["result"] != match.result.value:
            raise ValueError("recorded result disagrees with goals")
        records.append(match)
    validate_match_collection(records)
    # A date repair must not introduce a same-day team collision.
    appearances = pd.concat(
        [
            fixed[["competition", "match_date", side]].rename(columns={side: "team"})
            for side in ("home_team", "away_team")
        ]
    )
    if appearances.duplicated(["competition", "match_date", "team"]).any():
        raise ValueError("date repair would leave a same-day team collision")
    return fixed.sort_values(
        ["competition", "match_date", "home_team", "away_team"], kind="stable"
    ).reset_index(drop=True), {
        "corrected_dates": len(changed),
        "already_correct": already,
        "fixtures_absent": absent,
        "corrections": changed,
    }


def repair_snapshot(
    history_path: Path, manifest_path: Path, correction_path: Path, *, apply: bool = False
) -> dict:
    if history_path.resolve() == manifest_path.resolve():
        raise ValueError("history and manifest paths must differ")
    original = history_path.read_bytes()
    checksum = hashlib.sha256(original).hexdigest()
    manifest_bytes = manifest_path.read_bytes() if manifest_path.exists() else None
    manifest = json.loads(manifest_bytes) if manifest_bytes is not None else {}
    if manifest.get("dataset_sha256", checksum) != checksum:
        raise ValueError("history checksum differs from its manifest; review local changes first")
    corrections = json.loads(correction_path.read_text())
    fixed, report = repair_dates(pd.read_csv(history_path), corrections)
    report["written"] = False
    if not apply or not report["corrected_dates"]:
        return report
    backup_dir = history_path.parent / "date-repair-backups" / checksum
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name, content in ((history_path.name, original), (manifest_path.name, manifest_bytes)):
        if content is None:
            continue
        backup = backup_dir / name
        if backup.exists() and backup.read_bytes() != content:
            raise ValueError("existing backup differs; no snapshot was updated")
        backup.write_bytes(content)
    if (
        history_path.read_bytes() != original
        or (manifest_path.read_bytes() if manifest_path.exists() else None) != manifest_bytes
    ):
        raise ValueError("snapshot changed during repair; do not run a results sync concurrently")
    source = {
        "source_name": "Reviewed OpenFootball date repair",
        "correction_map_sha256": hashlib.sha256(correction_path.read_bytes()).hexdigest(),
        "input_dataset_sha256": checksum,
        "corrected_dates": report["corrected_dates"],
    }
    write_dataset_snapshot(
        dataframe=fixed,
        output_path=history_path,
        manifest_path=manifest_path,
        generated_at=datetime.now(UTC),
        sources=[*manifest.get("sources", []), source],
    )
    return {**report, "written": True, "backup_directory": str(backup_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=LOCAL_HISTORY)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--corrections", type=Path, default=CORRECTIONS)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.input != LOCAL_HISTORY and args.manifest is None:
        parser.error("--manifest is required with a custom --input")
    manifest_path = args.manifest or LOCAL_MANIFEST
    if not args.input.is_file():
        parser.exit(
            message="No local synced snapshot found; the corrected bundled history will be used.\n"
        )
    report = repair_snapshot(args.input, manifest_path, args.corrections, apply=args.apply)
    print(
        f"Dates to correct: {report['corrected_dates']}; "
        f"already correct: {report['already_correct']}; absent: {report['fixtures_absent']}"
    )
    print("Snapshot repaired with backup." if report["written"] else "No files changed.")
    if report.get("backup_directory"):
        print(f"Backup: {report['backup_directory']}")
    elif report["corrected_dates"]:
        print("Run again with --apply to repair this snapshot offline.")


if __name__ == "__main__":
    main()
