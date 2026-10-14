import json
from datetime import UTC, date, datetime

import pandas as pd
import pytest

from football_predictor.domain import Competition
from football_predictor.results_sync import sync_plan
from football_predictor.sync_checkpoint import checked_dates, read_checkpoint, write_checkpoint

PL = Competition.PREMIER_LEAGUE


def history():
    return pd.DataFrame(
        [{"competition": PL.value, "match_date": "2026-09-20", "season": "2026-27"}]
    )


def report(*, pending=False):
    return {
        "coverage": [{"competition": PL.value, "history_through": "2026-09-20", "matches": 1}],
        "date_queries": [
            {"competition": PL.value, "date": "2026-09-18", "pending": pending},
            {"competition": PL.value, "date": "2026-10-13", "pending": False},
        ],
    }


def test_empty_success_advances_checked_dates_without_claiming_new_results(tmp_path):
    path = tmp_path / "state.json"
    write_checkpoint(path, read_checkpoint(path), report())
    checkpoint = read_checkpoint(path)
    assert checkpoint["leagues"][PL.value]["history_through"] == "2026-09-20"
    cursors, pending = checked_dates(checkpoint, history(), date(2026, 10, 13))
    plan = sync_plan(
        history(),
        [PL],
        through=date(2026, 10, 13),
        as_of=datetime(2026, 10, 23, tzinfo=UTC),
        checked_through=cursors,
        pending_dates=pending,
    )
    assert plan == [(PL, date(2026, 10, 12)), (PL, date(2026, 10, 13))]


def test_weeklong_pause_does_not_repeat_full_backfill(tmp_path):
    path = tmp_path / "state.json"
    write_checkpoint(path, {}, report())
    checkpoint = read_checkpoint(path)
    for day in range(14, 22):
        through = date(2026, 10, day)
        cursors, pending = checked_dates(checkpoint, history(), through)
        plan = sync_plan(
            history(),
            [PL],
            through=through,
            as_of=datetime(2026, 10, 23, tzinfo=UTC),
            checked_through=cursors,
            pending_dates=pending,
        )
        assert len(plan) == 3
        assert all(date(2026, 10, day - 2) <= d <= through for _, d in plan)
        new_report = {
            **report(),
            "date_queries": [
                {"competition": PL.value, "date": d.isoformat(), "pending": False} for _, d in plan
            ],
        }
        write_checkpoint(path, checkpoint, new_report)
        checkpoint = read_checkpoint(path)
    assert checkpoint["leagues"][PL.value]["history_through"] == "2026-09-20"


def test_unfinished_dates_are_rechecked_until_terminal_response(tmp_path):
    path = tmp_path / "state.json"
    write_checkpoint(path, {}, report(pending=True))
    saved = read_checkpoint(path)
    cursors, pending = checked_dates(saved, history(), date(2026, 10, 13))
    plan = sync_plan(
        history(),
        [PL],
        through=date(2026, 10, 13),
        as_of=datetime(2026, 10, 23, tzinfo=UTC),
        checked_through=cursors,
        pending_dates=pending,
    )
    assert (PL, date(2026, 9, 18)) in plan
    write_checkpoint(path, saved, report(pending=False))
    _, pending = checked_dates(read_checkpoint(path), history(), date(2026, 10, 13))
    assert pending[PL] == set()


@pytest.mark.parametrize(
    "change",
    [
        {"history_through": "2026-09-19"},
        {"matches": 5},
        {"checked_through": "2027-01-01"},
        {"checked_from": "2026-10-10"},
        {"pending_dates": ["not-a-date"]},
        {"pending_dates": ["2026-12-01"]},
    ],
)
def test_invalid_or_different_history_checkpoint_cannot_skip_dates(tmp_path, change):
    path = tmp_path / "state.json"
    write_checkpoint(path, {}, report())
    saved = read_checkpoint(path)
    saved["leagues"][PL.value].update(change)
    cursors, pending = checked_dates(saved, history(), date(2026, 10, 13))
    assert not cursors and not pending


def test_corrupt_checkpoint_falls_back_to_full_plan(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json")
    assert read_checkpoint(path) == {"version": 1, "leagues": {}}
    path.write_text(json.dumps({"version": 999, "leagues": {}}))
    assert read_checkpoint(path) == {"version": 1, "leagues": {}}


def test_explicit_since_keeps_requested_backfill_range(tmp_path):
    path = tmp_path / "state.json"
    write_checkpoint(path, {}, report())
    cursors, pending = checked_dates(read_checkpoint(path), history(), date(2026, 10, 13))
    plan = sync_plan(
        history(),
        [PL],
        through=date(2026, 10, 13),
        since=date(2026, 9, 18),
        as_of=datetime(2026, 10, 23, tzinfo=UTC),
        checked_through=cursors,
        pending_dates=pending,
    )
    assert len(plan) == 26
