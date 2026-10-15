import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from football_predictor import live_fixtures
from football_predictor.domain import Competition
from football_predictor.live_fixtures import FixtureProviderError, GoalApiFixtureProvider
from football_predictor.request_budget import (
    DailyAllowance,
    GoalRequestLimit,
    consume_goal_request,
    goal_request_scope,
)


def test_scope_and_daily_allowances_count_real_transport_attempts(monkeypatch):
    requests = []

    def respond(request, timeout):
        requests.append(request.full_url)
        return io.BytesIO(b'{"success": true, "data": []}')

    monkeypatch.setattr(live_fixtures, "urlopen", respond)
    clock = [date(2026, 10, 15)]
    daily = DailyAllowance(3, today=lambda: clock[0])
    provider = GoalApiFixtureProvider("test-only")
    with goal_request_scope(2, daily):
        for _ in range(2):
            provider.list_fixtures(Competition.PREMIER_LEAGUE, clock[0])
        with pytest.raises(GoalRequestLimit, match="request allowance"):
            provider.list_fixtures(Competition.PREMIER_LEAGUE, clock[0])
    with goal_request_scope(2, daily):
        provider.list_fixtures(Competition.PREMIER_LEAGUE, clock[0])
        with pytest.raises(GoalRequestLimit, match="daily"):
            provider.list_fixtures(Competition.PREMIER_LEAGUE, clock[0])
    assert len(requests) == 3
    clock[0] = date(2026, 10, 16)
    with goal_request_scope(2, daily):
        provider.list_fixtures(Competition.PREMIER_LEAGUE, clock[0])
    # Ordinary fixture discovery / CLI does not inherit a finished journal scope.
    provider.list_fixtures(Competition.PREMIER_LEAGUE, clock[0])
    assert len(requests) == 5


def test_pagination_cannot_bypass_transport_budget(monkeypatch):
    requests = []

    def respond(request, timeout):
        requests.append(request.full_url)
        return io.BytesIO(json.dumps({
            "success": True,
            "data": [{"id": str(len(requests))}],
            "pagination": {"limit": 1, "hasMore": True},
        }).encode())

    monkeypatch.setattr(live_fixtures, "urlopen", respond)
    with goal_request_scope(2, DailyAllowance()):
        with pytest.raises(GoalRequestLimit):
            GoalApiFixtureProvider("test-only").list_fixtures(
                Competition.PREMIER_LEAGUE, date(2024, 9, 21)
            )
    assert len(requests) == 2
    assert "offset=1" in requests[-1]


def test_failed_http_attempts_spend_budget(monkeypatch):
    calls = []

    def deny(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(live_fixtures, "urlopen", deny)
    provider = GoalApiFixtureProvider("test-only")
    with goal_request_scope(1, DailyAllowance()):
        with pytest.raises(FixtureProviderError):
            provider._request_json(Request("https://api.goal-api.com/test"))
        with pytest.raises(GoalRequestLimit):
            provider._request_json(Request("https://api.goal-api.com/test"))
    assert len(calls) == 1


def test_league_catalogue_resolution_spends_the_same_budget(monkeypatch):
    calls = []

    def respond(request, timeout):
        calls.append(request.full_url)
        return io.BytesIO(b'{"success":true,"data":['
                          b'{"id":"spanish-league","name":"La Liga","country":"Spain"}]}')

    monkeypatch.setattr(live_fixtures, "urlopen", respond)
    with goal_request_scope(1, DailyAllowance()):
        with pytest.raises(GoalRequestLimit):
            GoalApiFixtureProvider("test-only").list_fixtures(
                Competition.LA_LIGA, date(2024, 9, 21)
            )
    assert len(calls) == 1
    assert "/leagues?" in calls[0]


def test_concurrent_scopes_share_one_daily_allowance():
    daily = DailyAllowance(7)

    def consume():
        with goal_request_scope(1, daily):
            try:
                consume_goal_request()
                return True
            except GoalRequestLimit:
                return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(lambda _: consume(), range(50))) == 7
