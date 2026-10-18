import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from football_predictor.date_repair import main, repair_dates, repair_snapshot

ROOT = Path(__file__).parents[1]


@pytest.fixture
def repair_case(tmp_path):
    corrections = json.loads((ROOT / "data/model/date_corrections.json").read_text())
    corrections["fixtures"] = corrections["fixtures"][:2]
    rows = [
        {
            **{k: v for k, v in item.items() if k not in {"old_date", "new_date"}},
            "match_date": item["old_date"],
            "source_name": "OpenFootball",
            "retrieved_at": "2026-10-14T05:05:06+00:00",
        }
        for item in corrections["fixtures"]
    ]
    rows.append(
        {
            "competition": "premier_league",
            "season": "2026-27",
            "match_date": "2026-10-10",
            "home_team": "Arsenal FC",
            "away_team": "Fulham FC",
            "home_goals": 2,
            "away_goals": 1,
            "result": "H",
            "source_name": "Goal API",
            "source_url": "https://api.goal-api.com/fixtures",
            "retrieved_at": "2026-10-11T00:00:00+00:00",
        }
    )
    history = tmp_path / "history.csv.gz"
    manifest = tmp_path / "history.manifest.json"
    mapping = tmp_path / "corrections.json"
    pd.DataFrame(rows).to_csv(history, index=False)
    manifest.write_text(
        json.dumps(
            {
                "dataset_sha256": hashlib.sha256(history.read_bytes()).hexdigest(),
                "sources": [{"source_name": "Goal API", "date_queries": ["preserved"]}],
            }
        )
    )
    mapping.write_text(json.dumps(corrections))
    return history, manifest, mapping


def test_offline_repair_dry_run_backup_new_results_and_idempotence(repair_case):
    history, manifest, mapping = repair_case
    before, before_manifest = history.read_bytes(), manifest.read_bytes()
    recent = pd.read_csv(history).query("source_name == 'Goal API'").reset_index(drop=True)
    plan = repair_snapshot(history, manifest, mapping)
    assert plan["corrected_dates"] == 2
    assert not plan["written"]
    assert history.read_bytes() == before and manifest.read_bytes() == before_manifest
    applied = repair_snapshot(history, manifest, mapping, apply=True)
    assert applied["written"]
    backup = Path(applied["backup_directory"])
    assert (backup / history.name).read_bytes() == before
    assert (backup / manifest.name).read_bytes() == before_manifest
    after = pd.read_csv(history)
    pd.testing.assert_frame_equal(
        recent, after.query("source_name == 'Goal API'").reset_index(drop=True)
    )
    assert len(after) == 3
    meta = json.loads(manifest.read_text())
    assert meta["dataset_sha256"] == hashlib.sha256(history.read_bytes()).hexdigest()
    assert meta["sources"][0]["date_queries"] == ["preserved"]
    written, written_manifest = history.read_bytes(), manifest.read_bytes()
    repeat = repair_snapshot(history, manifest, mapping, apply=True)
    assert repeat["already_correct"] == 2 and not repeat["written"]
    assert history.read_bytes() == written and manifest.read_bytes() == written_manifest


@pytest.mark.parametrize("conflict", ["score", "date", "source", "duplicate"])
def test_conflicts_fail_without_touching_local_files(repair_case, conflict):
    history, manifest, mapping = repair_case
    frame = pd.read_csv(history)
    if conflict == "score":
        frame.loc[0, "home_goals"] += 1
    elif conflict == "date":
        frame.loc[0, "match_date"] = "2019-07-02"
    elif conflict == "source":
        frame.loc[0, "source_name"] = "Other provider"
    else:
        frame = pd.concat([frame, frame.iloc[[0]].assign(match_date="2020-07-01")])
    frame.to_csv(history, index=False)
    meta = json.loads(manifest.read_text())
    meta["dataset_sha256"] = hashlib.sha256(history.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(meta))
    before, before_manifest = history.read_bytes(), manifest.read_bytes()
    with pytest.raises(ValueError):
        repair_snapshot(history, manifest, mapping, apply=True)
    assert history.read_bytes() == before and manifest.read_bytes() == before_manifest
    assert not (history.parent / "date-repair-backups").exists()


def test_checksum_conflict_and_same_output_paths_fail_closed(repair_case):
    history, manifest, mapping = repair_case
    manifest.write_text('{"dataset_sha256":"wrong"}')
    with pytest.raises(ValueError, match="checksum"):
        repair_snapshot(history, manifest, mapping, apply=True)
    with pytest.raises(ValueError, match="must differ"):
        repair_snapshot(history, history, mapping, apply=True)


def test_full_corrected_bundle_is_idempotent_and_all_mapped_dates_are_verified():
    corrections = json.loads((ROOT / "data/model/date_corrections.json").read_text())
    bundle = pd.read_csv(ROOT / "data/model/historical_matches.csv.gz")
    repaired, report = repair_dates(bundle, corrections)
    assert report["corrected_dates"] == 0
    assert report["already_correct"] == 268
    assert report["fixtures_absent"] == 0
    pd.testing.assert_frame_equal(repaired, bundle)


def test_missing_fixtures_are_counted_and_bad_maps_rejected(repair_case):
    history, _, mapping = repair_case
    frame = pd.read_csv(history).query("source_name == 'Goal API'")
    corrections = json.loads(mapping.read_text())
    _, report = repair_dates(frame, corrections)
    assert report["fixtures_absent"] == 2
    corrections["fixtures"].append(corrections["fixtures"][0])
    with pytest.raises(ValueError, match="duplicate fixture"):
        repair_dates(frame, corrections)


def test_cli_requires_corresponding_manifest_for_custom_input(repair_case, monkeypatch):
    history, _, _ = repair_case
    monkeypatch.setattr("sys.argv", ["date_repair", "--input", str(history), "--apply"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_cli_default_is_read_only_and_apply_is_explicit(repair_case, monkeypatch, capsys):
    history, manifest, mapping = repair_case
    args = [
        "date_repair",
        "--input",
        str(history),
        "--manifest",
        str(manifest),
        "--corrections",
        str(mapping),
    ]
    original = history.read_bytes()
    monkeypatch.setattr("sys.argv", args)
    main()
    assert "Dates to correct: 2" in capsys.readouterr().out
    assert history.read_bytes() == original
    monkeypatch.setattr("sys.argv", [*args, "--apply"])
    main()
    assert "Snapshot repaired with backup" in capsys.readouterr().out
