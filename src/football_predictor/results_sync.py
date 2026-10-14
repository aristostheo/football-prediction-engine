"""Bounded, fail-closed import of finished regular-season results from Goal API."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from numbers import Integral
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request

import pandas as pd

from football_predictor.data_status import format_coverage, history_coverage
from football_predictor.dataset import build_match_dataframe, canonicalize_match_labels
from football_predictor.domain import Competition, HistoricalMatch
from football_predictor.history_paths import BUNDLED_HISTORY, LOCAL_HISTORY, LOCAL_MANIFEST
from football_predictor.ingestion import (
    _dataset_payload_is_unchanged,
    _football_season,
    write_dataset_snapshot,
)
from football_predictor.live_fixtures import (
    GOAL_API_USER_AGENT,
    FixtureProviderError,
    GoalApiFixtureProvider,
    _goal_api_fixture,
    _nonnegative_score,
)
from football_predictor.team_names import canonical_team_name, is_registered_team
from football_predictor.validation import validate_match_collection

REGULAR_STAGES = {"current", "regular", "regular season", "regular-season"}
FINISHED_STATUSES = {"FINISHED", "FT"}
IDENTITY = ["competition", "match_date", "home_team", "away_team"]


class ResultsSyncError(ValueError):
    """The result import cannot safely update the model's historical inputs."""


class BudgetedGoalProvider(GoalApiFixtureProvider):
    def __init__(self, api_key: str, *, max_requests: int = 250) -> None:
        super().__init__(api_key)
        if not 1 <= max_requests <= 1000:
            raise ResultsSyncError("max_requests must be between 1 and 1000")
        self.max_requests = max_requests
        self.requests_used = 0

    def _request_json(self, request: Request) -> dict[str, object]:
        if self.requests_used >= self.max_requests:
            raise ResultsSyncError("request budget exhausted; no snapshot was updated")
        self.requests_used += 1
        return super()._request_json(request)

    def result_items(self, competition: Competition, day: date) -> list[dict[str, object]]:
        """Require complete pagination instead of accepting a repeated/truncated page."""
        league_id = self._league_id(competition)
        items: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        offset = 0
        expected_total = None
        for _ in range(20):
            query = urlencode({"leagueId": league_id, "limit": 100, "offset": offset})
            request = Request(
                f"{self._base_url}/fixtures/date/{day.isoformat()}?{query}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                    "User-Agent": GOAL_API_USER_AGENT,
                },
            )
            payload = self._request_json(request)
            page = payload.get("data")
            if isinstance(page, dict):
                page = page.get("fixtures", page.get("matches"))
            pagination = payload.get("pagination")
            if not isinstance(page, list) or any(not isinstance(x, dict) for x in page):
                raise ResultsSyncError("unexpected fixture list; no snapshot was updated")
            if not isinstance(pagination, dict):
                raise ResultsSyncError("missing pagination; cannot verify complete date response")
            total, limit, page_offset = (
                pagination.get("total"),
                pagination.get("limit"),
                pagination.get("offset"),
            )
            has_more = pagination.get("hasMore")
            if (
                any(
                    isinstance(x, bool) or not isinstance(x, Integral)
                    for x in (total, limit, page_offset)
                )
                or total < 0
                or limit < 1
                or page_offset != offset
                or not isinstance(has_more, bool)
                or len(page) > limit
            ):
                raise ResultsSyncError("invalid pagination; no snapshot was updated")
            if expected_total is not None and total != expected_total:
                raise ResultsSyncError("fixture total changed during pagination; retry later")
            expected_total = total
            for item in page:
                fixture_id = item.get("id")
                if not isinstance(fixture_id, str) or not fixture_id or fixture_id in seen_ids:
                    raise ResultsSyncError("missing or repeated fixture id during pagination")
                if str(item.get("leagueId", "")) != league_id:
                    raise ResultsSyncError("response contains a different or unverified league")
                seen_ids.add(fixture_id)
            items.extend(page)
            if not has_more:
                if len(items) != total:
                    raise ResultsSyncError("incomplete date response; no snapshot was updated")
                return items
            if not page or len(page) != limit or len(items) >= total:
                raise ResultsSyncError("contradictory pagination; no snapshot was updated")
            offset += limit
        raise ResultsSyncError("too many fixture pages; no snapshot was updated")


def completed_match(
    item: dict[str, object], competition: Competition, day: date, *, retrieved_at: datetime
) -> tuple[HistoricalMatch | None, str]:
    try:
        fixture = _goal_api_fixture(item, competition)
    except (KeyError, TypeError, ValueError) as error:
        raise ResultsSyncError(f"invalid fixture metadata on {day}") from error
    if fixture.kickoff_at.astimezone(UTC).date() != day:
        raise ResultsSyncError(f"fixture kickoff does not match requested date {day}")
    if fixture.status not in FINISHED_STATUSES:
        return None, "not_finished_or_nonregulation"
    if fixture.kickoff_at >= retrieved_at:
        raise ResultsSyncError("provider marked a future kickoff as finished")
    stage = item.get("stageName")
    if not isinstance(stage, str) or not stage.strip():
        raise ResultsSyncError("finished fixture has no verifiable competition stage")
    if stage.strip().casefold() not in REGULAR_STAGES:
        return None, "nonregular_stage"
    expected_season = _football_season(day)
    full_season = f"{expected_season[:4]}/{int(expected_season[:4]) + 1}"
    if str(item.get("leagueYear", "")) not in {expected_season, full_season}:
        raise ResultsSyncError("finished fixture has a missing or inconsistent season")
    for side in ("home", "away"):
        # Invalid explicit FT scores must not fall back to another score field.
        key = f"{side}TeamFtScore"
        value = item.get(key)
        if value is not None and _nonnegative_score(value) is None:
            raise ResultsSyncError("invalid regulation-time score")
    if fixture.home_goals is None or fixture.away_goals is None:
        raise ResultsSyncError("finished fixture has missing or invalid regulation-time goals")
    for team in (fixture.home_team, fixture.away_team):
        if not is_registered_team(team, competition):
            raise ResultsSyncError(f"unregistered club in {competition.value}: {team}")
    match = HistoricalMatch(
        match_date=day,
        competition=competition,
        season=expected_season,
        home_team=canonical_team_name(fixture.home_team, competition),
        away_team=canonical_team_name(fixture.away_team, competition),
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        source_name="Goal API",
        source_url=f"https://api.goal-api.com/v1/fixtures/{quote(fixture.fixture_id, safe='')}",
        retrieved_at=retrieved_at,
    )
    return match, "accepted"


def merge_history(previous: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Keep all prior fixtures, accept exact overlaps and reject conflicting facts."""
    left = canonicalize_match_labels(previous)
    right = canonicalize_match_labels(incoming) if not incoming.empty else left.iloc[:0].copy()
    for frame in (left, right):
        frame["match_date"] = pd.to_datetime(frame["match_date"]).dt.strftime("%Y-%m-%d")
        if frame.duplicated(IDENTITY).any():
            raise ResultsSyncError("duplicate canonical fixture identities")
    old, new = left.set_index(IDENTITY), right.set_index(IDENTITY)
    shared = old.index.intersection(new.index)
    facts = ["season", "home_goals", "away_goals", "result"]
    if not old.loc[shared, facts].equals(new.loc[shared, facts]):
        raise ResultsSyncError(
            "conflicting recorded score or season; review sources before importing"
        )
    addition_keys = new.index.difference(old.index)
    merged = pd.concat([left, new.loc[addition_keys].reset_index()], ignore_index=True)
    # Reject newly introduced repeated pairs without hiding or discarding
    # legacy source anomalies that are already present in the baseline.
    pair = ["competition", "season", "home_team", "away_team"]
    previous_counts = left.groupby(pair).size()
    counts = merged.groupby(pair).size()
    if ((counts > 1) & (counts > previous_counts.reindex(counts.index, fill_value=0))).any():
        raise ResultsSyncError("same league/season/venue pair appears on different dates")
    appearances = pd.concat(
        [
            merged[["competition", "match_date", side]].rename(columns={side: "team"})
            for side in ("home_team", "away_team")
        ]
    )
    if appearances.duplicated(["competition", "match_date", "team"]).any():
        raise ResultsSyncError("team appears more than once on the same league date")
    records = []
    for row in merged.to_dict("records"):
        for key in ("home_goals", "away_goals"):
            if _nonnegative_score(row[key]) is None:
                raise ResultsSyncError("history contains non-integer or negative goals")
        match = HistoricalMatch.model_validate(row)
        if row["result"] != match.result.value:
            raise ResultsSyncError("recorded result disagrees with goals")
        records.append(match)
    return build_match_dataframe(validate_match_collection(records))


def sync_plan(
    history: pd.DataFrame,
    competitions: list[Competition],
    *,
    through: date,
    since: date | None = None,
    as_of: datetime | None = None,
) -> list[tuple[Competition, date]]:
    now = as_of or datetime.now(UTC)
    if through >= now.astimezone(UTC).date():
        raise ResultsSyncError("through must be before today (UTC); same-day results are excluded")
    plan = []
    for competition in dict.fromkeys(competitions):
        league = history[history["competition"] == competition.value]
        if league.empty:
            raise ResultsSyncError(f"no baseline history for {competition.value}")
        latest = pd.to_datetime(league["match_date"]).max().date()
        start = since or latest - timedelta(days=2)
        if start > through or (through - start).days >= 60:
            raise ResultsSyncError("sync range must contain between 1 and 60 days per league")
        if start > latest + timedelta(days=1):
            raise ResultsSyncError("sync range would skip dates after the latest recorded result")
        plan.extend(
            (competition, start + timedelta(days=i)) for i in range((through - start).days + 1)
        )
    return plan


def sync_results(
    *,
    provider: BudgetedGoalProvider,
    history: pd.DataFrame,
    plan: list[tuple[Competition, date]],
    output_path: Path,
    manifest_path: Path,
    as_of: datetime | None = None,
    progress=None,
) -> dict[str, object]:
    now = as_of or datetime.now(UTC)
    if output_path.resolve() == BUNDLED_HISTORY.resolve():
        raise ResultsSyncError("sync output must not overwrite the Git-tracked baseline")
    if output_path.resolve() == manifest_path.resolve():
        raise ResultsSyncError("CSV and manifest paths must differ")
    if not plan or any(day >= now.astimezone(UTC).date() for _, day in plan):
        raise ResultsSyncError("sync requires earlier dates, excluding today")
    if len(plan) > provider.max_requests:
        raise ResultsSyncError("planned date queries already exceed request budget")
    before = merge_history(history, history.iloc[:0])
    matches = []
    skipped: Counter[str] = Counter()
    queries = []
    for index, (competition, day) in enumerate(plan, 1):
        items = provider.result_items(competition, day)
        accepted = 0
        for item in items:
            match, reason = completed_match(item, competition, day, retrieved_at=now)
            if match:
                matches.append(match)
                accepted += 1
            else:
                skipped[reason] += 1
        queries.append(
            {
                "competition": competition.value,
                "date": day.isoformat(),
                "fixtures": len(items),
                "accepted": accepted,
                "payload_sha256": hashlib.sha256(
                    json.dumps(items, sort_keys=True).encode()
                ).hexdigest(),
            }
        )
        if progress:
            progress(
                f"[{index}/{len(plan)}] {competition.value} {day}: "
                f"{accepted} completed results; requests {provider.requests_used}"
            )
    incoming = build_match_dataframe(matches) if matches else before.iloc[:0].copy()
    merged = merge_history(before, incoming)
    added = len(merged) - len(before)
    previous_output = pd.read_csv(output_path) if output_path.is_file() else None
    unchanged = _dataset_payload_is_unchanged(previous_output, merged)
    if unchanged or (added == 0 and previous_output is None):
        return {
            "added_matches": 0,
            "total_matches": len(before),
            "requests_used": provider.requests_used,
            "written": False,
            "skipped": dict(skipped),
            "coverage": history_coverage(before, as_of=now.date()),
        }
    source = {
        "source_name": "Goal API",
        "requested_at": now.isoformat(),
        "requests_used": provider.requests_used,
        "date_queries": queries,
        "accepted_rows": len(incoming),
        "skipped": dict(skipped),
        "input_facts_sha256": hashlib.sha256(before.to_csv(index=False).encode()).hexdigest(),
    }
    manifest = write_dataset_snapshot(
        dataframe=merged,
        output_path=output_path,
        manifest_path=manifest_path,
        generated_at=now,
        sources=[source],
        keep_existing_dataset=unchanged,
    )
    return {
        **manifest,
        "added_matches": added,
        "requests_used": provider.requests_used,
        "written": True,
        "skipped": dict(skipped),
        "coverage": history_coverage(merged, as_of=now.date()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=date.fromisoformat)
    parser.add_argument(
        "--through", type=date.fromisoformat, default=datetime.now(UTC).date() - timedelta(days=1)
    )
    parser.add_argument("--league", action="append", choices=[c.value for c in Competition])
    parser.add_argument("--max-requests", type=int, default=250)
    parser.add_argument(
        "--dry-run", action="store_true", help="show query plan without API requests"
    )
    args = parser.parse_args()
    try:
        history = pd.read_csv(BUNDLED_HISTORY)
        if LOCAL_HISTORY.is_file():
            history = merge_history(history, pd.read_csv(LOCAL_HISTORY))
        else:
            history = merge_history(history, history.iloc[:0])
        competitions = [Competition(x) for x in args.league] if args.league else list(Competition)
        plan = sync_plan(history, competitions, through=args.through, since=args.since)
        if not 1 <= args.max_requests <= 1000:
            raise ResultsSyncError("max_requests must be between 1 and 1000")
        catalogue_allowance = sum(
            c not in GoalApiFixtureProvider("plan")._league_ids for c in set(competitions)
        )
        minimum = len(plan) + catalogue_allowance
        if minimum > args.max_requests:
            raise ResultsSyncError(
                f"at least {minimum} requests needed; budget is {args.max_requests}"
            )
        print(
            f"Date queries: {len(plan)}; catalogue queries: up to {catalogue_allowance}; "
            f"hard request cap: {args.max_requests} (pagination included).",
            flush=True,
        )
        for competition in competitions:
            days = [day for league, day in plan if league == competition]
            print(f"{competition.value}: {min(days)} through {max(days)}", flush=True)
        if args.dry_run:
            return
        provider = BudgetedGoalProvider.from_environment()
        provider.max_requests = args.max_requests
        report = sync_results(
            provider=provider,
            history=history,
            plan=plan,
            output_path=LOCAL_HISTORY,
            manifest_path=LOCAL_MANIFEST,
            progress=lambda message: print(message, flush=True),
        )
        print(f"Added {report['added_matches']} results using {report['requests_used']} requests.")
        print(format_coverage(report["coverage"]))
        if report["written"]:
            print(f"Saved {LOCAL_HISTORY}. Restart the backend to load it.")
        else:
            print(
                "No new results; existing files were left unchanged. "
                "A successful query does not establish complete season coverage."
            )
    except OSError as error:
        parser.exit(
            1, f"Results sync filesystem error: {error}\nCheck --check-data before restarting.\n"
        )
    except (ValueError, FixtureProviderError) as error:
        parser.exit(1, f"Results sync stopped: {error}\nNo results snapshot was updated.\n")


if __name__ == "__main__":
    main()
