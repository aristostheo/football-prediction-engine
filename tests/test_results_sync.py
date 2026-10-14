import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from football_predictor import history_paths
from football_predictor.domain import Competition
from football_predictor.features import (
    build_future_fixture_features,
    build_pre_match_features,
    build_pre_match_features_and_states,
)
from football_predictor.live_fixtures import FixtureProviderError, GoalApiFixtureProvider
from football_predictor.results_sync import (
    BudgetedGoalProvider,
    ResultsSyncError,
    completed_match,
    merge_history,
    sync_plan,
    sync_results,
)

PL = Competition.PREMIER_LEAGUE
NOW = datetime(2026, 10, 14, 5, tzinfo=UTC)
DAY = date(2026, 10, 12)


def fixture(**changes):
    item = {
        "id": "real-provider-id",
        "leagueId": "cmr77dvkr005nrx06lp7rvp49",
        "leagueYear": "2026/2027",
        "kickoffUtc": "2026-10-12T15:00:00Z",
        "homeTeam": {"name": "Fulham"},
        "awayTeam": {"name": "Manchester Utd"},
        "homeTeamFtScore": "1",
        "awayTeamFtScore": "1",
        "homeTeamScore": "9",
        "awayTeamScore": "8",
        "matchStatus": "FINISHED",
        "stageName": "Current",
    }
    return {**item, **changes}


def baseline():
    return pd.DataFrame(
        [
            {
                "match_date": "2026-09-20",
                "competition": PL.value,
                "season": "2026-27",
                "home_team": "Arsenal FC",
                "away_team": "Chelsea FC",
                "home_goals": 2,
                "away_goals": 0,
                "result": "H",
                "source_name": "OpenFootball",
                "source_url": "https://example.com/source",
                "retrieved_at": NOW.isoformat(),
            }
        ]
    )


def fake_http(monkeypatch, payloads):
    calls = []

    def request(self, req):
        calls.append(req.full_url)
        payload = payloads[len(calls) - 1]
        if isinstance(payload, Exception):
            raise payload
        return payload

    monkeypatch.setattr(GoalApiFixtureProvider, "_request_json", request)
    return calls


def page(items, *, total=None, offset=0, limit=100, more=False):
    return {
        "success": True,
        "data": items,
        "pagination": {
            "total": len(items) if total is None else total,
            "limit": limit,
            "offset": offset,
            "hasMore": more,
        },
    }


def run_sync(tmp_path, monkeypatch, payloads, *, history=None, plan=None, budget=250):
    calls = fake_http(monkeypatch, payloads)
    provider = BudgetedGoalProvider("secret-do-not-persist", max_requests=budget)
    output, manifest = tmp_path / "matches.csv.gz", tmp_path / "manifest.json"
    report = sync_results(
        provider=provider,
        history=history if history is not None else baseline(),
        plan=plan or [(PL, DAY)],
        output_path=output,
        manifest_path=manifest,
        as_of=NOW,
    )
    return report, output, manifest, calls


def test_sync_adds_canonical_regulation_results_with_checksum_and_no_secrets(tmp_path, monkeypatch):
    report, output, manifest, calls = run_sync(tmp_path, monkeypatch, [page([fixture()])])
    written = pd.read_csv(output)
    imported = written[written["source_name"] == "Goal API"].iloc[0]
    assert report["added_matches"] == 1
    assert report["requests_used"] == 1
    assert imported["home_team"] == "Fulham FC"
    assert imported["away_team"] == "Manchester United FC"
    assert imported["home_goals"] == imported["away_goals"] == 1
    assert imported["result"] == "D"
    assert imported["source_url"].endswith("/fixtures/real-provider-id")
    provenance = json.loads(manifest.read_text())
    assert provenance["dataset_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert "secret-do-not-persist" not in manifest.read_text()
    assert report["coverage"][0]["history_through"] == "2026-10-12"
    query = parse_qs(urlparse(calls[0]).query)
    assert query["leagueId"] == ["cmr77dvkr005nrx06lp7rvp49"]


def test_sync_repeat_does_not_rewrite_data_or_manifest(tmp_path, monkeypatch):
    _, output, manifest, _ = run_sync(tmp_path, monkeypatch, [page([fixture()])])
    originals = output.read_bytes(), manifest.read_bytes()
    report, _, _, _ = run_sync(
        tmp_path, monkeypatch, [page([fixture()])], history=pd.read_csv(output)
    )
    assert not report["written"]
    assert report["added_matches"] == 0
    assert (output.read_bytes(), manifest.read_bytes()) == originals


def test_no_results_do_not_create_snapshot_or_claim_freshness(tmp_path, monkeypatch):
    report, output, manifest, _ = run_sync(tmp_path, monkeypatch, [page([])])
    assert not output.exists() and not manifest.exists()
    assert report["coverage"][0]["history_through"] == "2026-09-20"
    assert report["coverage"][0]["status"] == "dated"


@pytest.mark.parametrize(
    "changes",
    [
        {"homeTeamFtScore": "-1"},
        {"homeTeamFtScore": 1.5},
        {"homeTeamFtScore": True},
        {"homeTeamFtScore": None, "homeTeamScore": None},
        {"leagueYear": "2025/2026"},
        {"stageName": None},
        {"homeTeam": {"name": "Unknown Club"}},
        {"awayTeam": {"name": "Fulham"}},
        {"kickoffUtc": "2026-10-13T15:00:00Z"},
    ],
)
def test_invalid_finished_fixture_aborts_without_replacing_files(tmp_path, monkeypatch, changes):
    output, manifest = tmp_path / "matches.csv.gz", tmp_path / "manifest.json"
    output.write_bytes(b"original CSV")
    manifest.write_bytes(b"original manifest")
    originals = output.read_bytes(), manifest.read_bytes()
    with pytest.raises(ValueError):
        run_sync(tmp_path, monkeypatch, [page([fixture(**changes)])])
    assert (output.read_bytes(), manifest.read_bytes()) == originals


@pytest.mark.parametrize(
    "changes",
    [
        {"matchStatus": "POSTPONED"},
        {"matchStatus": "CANCELLED"},
        {"matchStatus": "LIVE"},
        {"matchStatus": "AET"},
        {"matchStatus": "PEN"},
        {"stageName": "Championship Playoffs"},
    ],
)
def test_nonfinal_or_nonregular_games_are_excluded(changes):
    match, reason = completed_match(fixture(**changes), PL, DAY, retrieved_at=NOW)
    assert match is None and reason != "accepted"


def test_future_finished_game_is_rejected():
    with pytest.raises(ResultsSyncError, match="future kickoff"):
        completed_match(
            fixture(kickoffUtc="2026-10-14T20:00:00Z"), PL, date(2026, 10, 14), retrieved_at=NOW
        )


def test_conflicting_scores_cannot_overwrite_the_baseline(tmp_path, monkeypatch):
    with pytest.raises(ResultsSyncError, match="conflicting"):
        run_sync(
            tmp_path,
            monkeypatch,
            [
                page(
                    [
                        fixture(
                            homeTeam={"name": "Arsenal"},
                            awayTeam={"name": "Chelsea"},
                            kickoffUtc="2026-09-20T15:00:00Z",
                        )
                    ]
                )
            ],
            plan=[(PL, date(2026, 9, 20))],
        )
    assert not (tmp_path / "matches.csv.gz").exists()


def test_partial_download_failure_keeps_prior_snapshot(tmp_path, monkeypatch):
    output, manifest = tmp_path / "matches.csv.gz", tmp_path / "manifest.json"
    baseline().to_csv(output, compression="gzip", index=False)
    manifest.write_text("existing provenance")
    originals = output.read_bytes(), manifest.read_bytes()
    with pytest.raises(FixtureProviderError):
        run_sync(
            tmp_path,
            monkeypatch,
            [page([fixture()]), FixtureProviderError("HTTP 403")],
            plan=[(PL, DAY), (PL, date(2026, 10, 13))],
        )
    assert (output.read_bytes(), manifest.read_bytes()) == originals


def test_budget_includes_pagination_and_stops_before_extra_request(tmp_path, monkeypatch):
    with pytest.raises(ResultsSyncError, match="budget exhausted"):
        run_sync(tmp_path, monkeypatch, [page([fixture()], total=2, limit=1, more=True)], budget=1)
    assert not (tmp_path / "matches.csv.gz").exists()


def test_catalogue_lookup_uses_same_request_budget(monkeypatch):
    calls = fake_http(
        monkeypatch,
        [
            {
                "success": True,
                "data": [
                    {
                        "id": "spanish-league",
                        "name": "La Liga",
                        "country": {"name": "Spain"},
                    }
                ],
            }
        ],
    )
    provider = BudgetedGoalProvider("key", max_requests=1)
    with pytest.raises(ResultsSyncError, match="budget exhausted"):
        provider.result_items(Competition.LA_LIGA, DAY)
    assert provider.requests_used == len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        page([fixture(leagueId="wrong-league")]),
        page([fixture()], total=2),
        {"success": True, "data": [fixture()]},
        page([fixture()], total=1, more=True),
        page([fixture()], offset=5),
        page(["malformed"]),
    ],
)
def test_invalid_or_incomplete_pages_are_rejected(tmp_path, monkeypatch, payload):
    with pytest.raises(ResultsSyncError):
        run_sync(tmp_path, monkeypatch, [payload])
    assert not (tmp_path / "matches.csv.gz").exists()


def test_repeated_page_is_rejected_instead_of_importing_partial_data(tmp_path, monkeypatch):
    with pytest.raises(ResultsSyncError, match="repeated fixture"):
        run_sync(
            tmp_path,
            monkeypatch,
            [
                page([fixture()], total=2, limit=1, more=True),
                page([fixture()], total=2, limit=1, offset=1),
            ],
        )
    assert not (tmp_path / "matches.csv.gz").exists()


def test_complete_pagination_uses_offsets(monkeypatch):
    calls = fake_http(
        monkeypatch,
        [
            page([fixture()], total=2, limit=1, more=True),
            page([fixture(id="second")], total=2, limit=1, offset=1),
        ],
    )
    provider = BudgetedGoalProvider("key")
    items = provider.result_items(PL, DAY)
    assert len(items) == 2 and provider.requests_used == 2
    assert parse_qs(urlparse(calls[1]).query)["offset"] == ["1"]


def test_plan_overlaps_previous_dates_and_excludes_today():
    plan = sync_plan(baseline(), [PL], through=date(2026, 10, 13), as_of=NOW)
    assert plan[0] == (PL, date(2026, 9, 18))
    assert plan[-1] == (PL, date(2026, 10, 13))
    assert len(plan) == 26
    for through, since in [(date(2026, 10, 14), None), (date(2026, 10, 13), date(2026, 10, 10))]:
        with pytest.raises(ResultsSyncError):
            sync_plan(baseline(), [PL], through=through, since=since, as_of=NOW)


def test_added_result_affects_only_later_feature_rows():
    earlier = baseline()
    item = fixture(
        homeTeam={"name": "Arsenal"},
        awayTeam={"name": "Fulham"},
        homeTeamFtScore="0",
        awayTeamFtScore="4",
    )
    match, _ = completed_match(item, PL, DAY, retrieved_at=NOW)
    from football_predictor.dataset import build_match_dataframe

    combined = merge_history(earlier, build_match_dataframe([match]))
    old, new = build_pre_match_features(earlier), build_pre_match_features(combined)
    columns = [x for x in old.columns if x not in earlier.columns]
    pd.testing.assert_frame_equal(old[columns], new.iloc[:1][columns])
    assert new.iloc[1]["home_form_goals_for_per_match"] == 2
    changed = combined.copy()
    changed.loc[1, ["home_goals", "away_goals", "result"]] = [4, 0, "H"]
    pd.testing.assert_frame_equal(new[columns], build_pre_match_features(changed)[columns])
    _, states = build_pre_match_features_and_states(combined)
    future = build_future_fixture_features(
        competition=PL.value,
        match_date=date(2026, 10, 15),
        home_team="Arsenal FC",
        away_team="Chelsea FC",
        final_states=states,
    ).iloc[0]
    assert future["home_matches_played"] == 2
    assert future["home_form_goals_for_per_match"] == 1
    assert future["home_form_goals_against_per_match"] == 2


def test_real_bundle_is_accepted_and_preserved():
    history = pd.read_csv(history_paths.BUNDLED_HISTORY)
    merged = merge_history(history, history.iloc[:0])
    assert len(merged) == len(history)
    assert set(history["match_date"]) == set(merged["match_date"])


def test_runtime_prefers_local_snapshot_and_respects_explicit_override(tmp_path, monkeypatch):
    local = tmp_path / "local.csv"
    monkeypatch.setattr(history_paths, "LOCAL_HISTORY", local)
    monkeypatch.delenv("HISTORICAL_MATCHES_PATH", raising=False)
    assert history_paths.runtime_history_path() == history_paths.BUNDLED_HISTORY
    local.write_text("local snapshot")
    assert history_paths.runtime_history_path() == local
    monkeypatch.setenv("HISTORICAL_MATCHES_PATH", "explicit.csv")
    assert history_paths.runtime_history_path() == Path("explicit.csv")


def test_manifest_publish_failure_rolls_back_existing_csv(tmp_path, monkeypatch):
    output, manifest = tmp_path / "matches.csv.gz", tmp_path / "manifest.json"
    baseline().to_csv(output, index=False, compression="gzip")
    manifest.write_text("original manifest")
    originals = output.read_bytes(), manifest.read_bytes()
    replace = Path.replace

    def fail_manifest(source, target):
        if target == manifest:
            raise OSError("disk failure publishing manifest")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_manifest)
    with pytest.raises(OSError, match="manifest"):
        run_sync(tmp_path, monkeypatch, [page([fixture()])])
    assert (output.read_bytes(), manifest.read_bytes()) == originals


def test_snapshot_cannot_overwrite_tracked_baseline(tmp_path):
    with pytest.raises(ResultsSyncError, match="Git-tracked"):
        sync_results(
            provider=BudgetedGoalProvider("key"),
            history=baseline(),
            plan=[(PL, DAY)],
            output_path=history_paths.BUNDLED_HISTORY,
            manifest_path=tmp_path / "manifest.json",
            as_of=NOW,
        )


def test_new_venue_pair_duplicate_is_rejected():
    old = baseline()
    incoming = old.assign(match_date="2026-10-12")
    with pytest.raises(ResultsSyncError, match="different dates"):
        merge_history(old, incoming)


def test_same_day_team_collision_is_rejected():
    incoming = baseline().assign(away_team="Fulham FC")
    with pytest.raises(ResultsSyncError, match="same league date"):
        merge_history(baseline(), incoming)


def test_cli_imports_to_local_output_with_environment_key(tmp_path, monkeypatch, capsys):
    import sys

    from football_predictor import results_sync

    bundled, output, manifest = (
        tmp_path / "bundle.csv",
        tmp_path / "local.csv.gz",
        tmp_path / "local.json",
    )
    baseline().to_csv(bundled, index=False)
    monkeypatch.setattr(results_sync, "BUNDLED_HISTORY", bundled)
    monkeypatch.setattr(results_sync, "LOCAL_HISTORY", output)
    monkeypatch.setattr(results_sync, "LOCAL_MANIFEST", manifest)
    monkeypatch.setenv("GOAL_API_KEY", "configured-test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "results_sync",
            "--league",
            "premier_league",
            "--since",
            "2026-09-20",
            "--through",
            "2026-09-21",
        ],
    )
    fake_http(monkeypatch, [page([]), page([fixture(kickoffUtc="2026-09-21T15:00:00Z")])])
    results_sync.main()
    assert len(pd.read_csv(output)) == 2
    assert manifest.is_file()
    text = capsys.readouterr().out
    assert "Added 1 results using 2 requests" in text
    assert "configured-test-key" not in text


def test_celta_de_vigo_payload_uses_existing_canonical_club():
    match, reason = completed_match(
        fixture(homeTeam={"name": "Celta de Vigo"}, awayTeam={"name": "Real Madrid"}),
        Competition.LA_LIGA,
        DAY,
        retrieved_at=NOW,
    )
    assert reason == "accepted"
    assert match.home_team == "RC Celta de Vigo"
    assert match.away_team == "Real Madrid CF"


def test_cache_reuses_raw_payload_after_alias_failure_and_keeps_fetch_timestamp(
    tmp_path, monkeypatch
):
    from football_predictor import results_sync
    from football_predictor.team_names import is_registered_team as registered

    calls = fake_http(monkeypatch, [page([fixture(homeTeam={"name": "New Alias"})])])
    cache = tmp_path / "cache"
    output, manifest = tmp_path / "matches.csv.gz", tmp_path / "manifest.json"
    first = BudgetedGoalProvider("not-in-cache", cache_dir=cache)
    with pytest.raises(ResultsSyncError, match="New Alias"):
        sync_results(
            provider=first,
            history=baseline(),
            plan=[(PL, DAY)],
            output_path=output,
            manifest_path=manifest,
            as_of=NOW,
        )
    assert not output.exists() and not manifest.exists()
    assert len(list(cache.glob("*.json"))) == 1
    record = json.loads(next(cache.glob("*.json")).read_text())
    assert "not-in-cache" not in json.dumps(record)

    original = results_sync.completed_match

    def newly_reviewed_alias(item, competition, day, *, retrieved_at):
        # Simulate a reviewed registry mapping without altering the cache.
        if item["homeTeam"]["name"] == "New Alias":
            item = {**item, "homeTeam": {"name": "Fulham"}}
        return original(item, competition, day, retrieved_at=retrieved_at)

    monkeypatch.setattr(results_sync, "completed_match", newly_reviewed_alias)
    second = BudgetedGoalProvider("not-in-cache", max_requests=1, cache_dir=cache)
    report = sync_results(
        provider=second,
        history=baseline(),
        plan=[(PL, DAY)],
        output_path=output,
        manifest_path=manifest,
        as_of=NOW,
    )
    assert second.requests_used == 0 and second.cache_hits == 1
    assert len(calls) == 1
    assert report["added_matches"] == 1
    written = pd.read_csv(output)
    timestamp = written.loc[written["source_name"] == "Goal API", "retrieved_at"].iloc[0]
    assert timestamp == record["fetched_at"]
    assert registered("Fulham", PL)


def test_all_unknown_clubs_are_reported_in_one_pass_without_publishing(tmp_path, monkeypatch):
    fake_http(
        monkeypatch,
        [
            page([fixture(homeTeam={"name": "Unknown One"})]),
            page([fixture(homeTeam={"name": "Unknown Two"}, kickoffUtc="2026-10-13T15:00:00Z")]),
        ],
    )
    provider = BudgetedGoalProvider("key", cache_dir=tmp_path / "cache")
    output = tmp_path / "snapshot.csv.gz"
    with pytest.raises(ResultsSyncError, match="Unknown One.*Unknown Two"):
        sync_results(
            provider=provider,
            history=baseline(),
            plan=[(PL, DAY), (PL, date(2026, 10, 13))],
            output_path=output,
            manifest_path=tmp_path / "manifest.json",
            as_of=NOW,
        )
    assert provider.requests_used == 2
    assert len(list((tmp_path / "cache").glob("*.json"))) == 2
    assert not output.exists()


@pytest.mark.parametrize("corruption", ["expired", "bad_json", "wrong_url", "bad_payload"])
def test_unusable_cache_is_refetched(tmp_path, monkeypatch, corruption):
    calls = fake_http(monkeypatch, [page([fixture()]), page([])])
    first = BudgetedGoalProvider("key", cache_dir=tmp_path)
    first.result_items(PL, DAY)
    path = next(tmp_path.glob("*.json"))
    record = json.loads(path.read_text())
    if corruption == "expired":
        record["fetched_at"] = "2020-01-01T00:00:00+00:00"
    elif corruption == "wrong_url":
        record["url"] = "https://example.com/wrong"
    elif corruption == "bad_payload":
        record["payload"] = {"success": False}
    path.write_text("{not json" if corruption == "bad_json" else json.dumps(record))
    second = BudgetedGoalProvider("key", cache_dir=tmp_path)
    assert second.result_items(PL, DAY) == []
    assert second.requests_used == 1 and second.cache_hits == 0
    assert len(calls) == 2


def test_fresh_flag_bypasses_valid_cache(tmp_path, monkeypatch):
    calls = fake_http(monkeypatch, [page([fixture()]), page([])])
    BudgetedGoalProvider("key", cache_dir=tmp_path).result_items(PL, DAY)
    refreshed = BudgetedGoalProvider("key", cache_dir=tmp_path, fresh=True)
    assert refreshed.result_items(PL, DAY) == []
    assert len(calls) == 2 and refreshed.cache_hits == 0


@pytest.mark.parametrize(
    ("league", "home", "away", "expected"),
    [
        (Competition.BUNDESLIGA, "Elversberg", "Paderborn", "SV 07 Elversberg"),
        (
            Competition.LA_LIGA,
            "Deportivo de La Coruña",
            "Racing de Santander",
            "RC Deportivo La Coruña",
        ),
        (Competition.LIGUE_1, "Troyes", "Paris Saint Germain", "ESTAC Troyes"),
        (Competition.PRIMEIRA_LIGA, "Estrela", "Benfica", "CF Estrela da Amadora"),
        (Competition.SERIE_A, "Frosinone", "Roma", "Frosinone Calcio"),
    ],
)
def test_reported_aliases_parse_finished_results_without_new_club_identities(
    league, home, away, expected
):
    match, reason = completed_match(
        fixture(homeTeam={"name": home}, awayTeam={"name": away}),
        league,
        DAY,
        retrieved_at=NOW,
    )
    assert reason == "accepted"
    assert match.home_team == expected
    assert match.result.value == "D"


def test_failed_cli_sync_preserves_checked_date_checkpoint(tmp_path, monkeypatch):
    import sys

    from football_predictor import results_sync

    bundled, output = tmp_path / "bundle.csv", tmp_path / "local.csv.gz"
    baseline().to_csv(bundled, index=False)
    state = tmp_path / "results_sync_state.json"
    state.write_text(
        json.dumps(
            {
                "version": 1,
                "leagues": {
                    "premier_league": {
                        "checked_from": "2026-09-18",
                        "checked_through": "2026-09-20",
                        "history_through": "2026-09-20",
                        "matches": 1,
                        "pending_dates": [],
                    }
                },
            }
        )
    )
    original = state.read_bytes()
    monkeypatch.setattr(results_sync, "BUNDLED_HISTORY", bundled)
    monkeypatch.setattr(results_sync, "LOCAL_HISTORY", output)
    monkeypatch.setattr(results_sync, "LOCAL_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setenv("GOAL_API_KEY", "test")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "results_sync",
            "--league",
            "premier_league",
            "--since",
            "2026-09-20",
            "--through",
            "2026-09-21",
        ],
    )
    fake_http(
        monkeypatch,
        [
            page([]),
            page([fixture(kickoffUtc="2026-09-21T15:00:00Z", homeTeam={"name": "Unknown Club"})]),
        ],
    )
    with pytest.raises(SystemExit) as stopped:
        results_sync.main()
    assert stopped.value.code == 1
    assert state.read_bytes() == original
    assert not output.exists()
