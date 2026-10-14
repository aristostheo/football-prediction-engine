import sys
from datetime import date

import pandas as pd

from football_predictor.__main__ import main
from football_predictor.data_status import history_coverage


def test_coverage_uses_match_dates_and_reports_missing_leagues() -> None:
    matches = pd.DataFrame(
        [
            {
                "competition": "premier_league",
                "season": "2026-27",
                "match_date": "2026-09-20",
                "retrieved_at": "2026-10-14T00:00:00Z",
            }
        ]
    )
    rows = history_coverage(matches, as_of=date(2026, 10, 14))
    assert len(rows) == 7
    pl = next(r for r in rows if r["competition"] == "premier_league")
    assert pl["history_through"] == "2026-09-20"
    assert pl["age_days"] == 24
    assert pl["status"] == "dated"
    assert pl["current_season_matches"] == 1
    assert next(r for r in rows if r["competition"] == "serie_a")["status"] == "missing"


def test_check_data_cli_does_not_change_snapshot(tmp_path, monkeypatch, capsys) -> None:
    path = tmp_path / "matches.csv"
    pd.DataFrame(
        [
            {
                "competition": "premier_league",
                "season": "2026-27",
                "match_date": "2026-09-20",
            }
        ]
    ).to_csv(path, index=False)
    original = path.read_bytes()
    monkeypatch.setattr(sys, "argv", ["football_predictor", "--check-data", "--output", str(path)])
    main()
    assert "2026-09-20" in capsys.readouterr().out
    assert path.read_bytes() == original
