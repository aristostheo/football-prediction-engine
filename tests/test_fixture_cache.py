from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Event

import pytest

from football_predictor.domain import Competition
from football_predictor.fixture_cache import FixtureCacheMiss, FixtureDateCache
from football_predictor.live_fixtures import FixtureProviderError
from football_predictor.request_budget import GoalRequestLimit


def test_cache_shares_concurrent_loads_and_returns_separate_lists():
    started, release = Event(), Event()
    calls = []

    def fetch(competition, day):
        calls.append((competition, day))
        started.set()
        assert release.wait(3)
        return []

    cache = FixtureDateCache(fetch)
    key = (Competition.PREMIER_LEAGUE, date(2024, 9, 21))
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(cache.get, *key)
        assert started.wait(3)
        waiter = pool.submit(cache.get, *key, allow_fetch=False)
        release.set()
        first, second = owner.result(timeout=3), waiter.result(timeout=3)
    first.append("caller mutation")
    assert second == cache.get(*key) == []
    assert calls == [key]


def test_cache_ttl_fair_refresh_order_and_lru_capacity():
    clock = [datetime(2026, 10, 15, tzinfo=UTC)]
    calls = []
    cache = FixtureDateCache(
        lambda competition, day: calls.append(day) or [], capacity=2, now=lambda: clock[0]
    )
    competition = Competition.PREMIER_LEAGUE
    old, recent = date(2024, 9, 21), clock[0].date()
    cache.get(competition, recent)
    clock[0] += timedelta(minutes=6)
    # Unchecked old dates take priority even when recent entries have expired.
    assert cache.refresh_priority(competition, old) < cache.refresh_priority(competition, recent)
    cache.get(competition, recent)
    cache.get(competition, old)
    clock[0] += timedelta(hours=23)
    cache.get(competition, old)
    assert calls == [recent, recent, old]
    cache.get(competition, old - timedelta(days=1))
    with pytest.raises(FixtureCacheMiss):
        cache.get(competition, recent, allow_fetch=False)
    clock[0] += timedelta(hours=2)
    cache.get(competition, old)
    assert calls.count(old) == 2


def test_provider_failures_are_cached_but_budget_exhaustion_is_not():
    clock = [datetime(2026, 10, 15, tzinfo=UTC)]
    failures = [FixtureProviderError("offline"), GoalRequestLimit("defer"), None]
    calls = []

    def fetch(competition, day):
        calls.append(day)
        error = failures.pop(0)
        if error:
            raise error
        return []

    cache = FixtureDateCache(fetch, now=lambda: clock[0])
    key = (Competition.PREMIER_LEAGUE, date(2024, 9, 21))
    for _ in range(2):
        with pytest.raises(FixtureProviderError, match="offline"):
            cache.get(*key)
    assert len(calls) == 1
    clock[0] += timedelta(minutes=6)
    with pytest.raises(GoalRequestLimit):
        cache.get(*key)
    assert cache.get(*key) == []
    assert len(calls) == 3
