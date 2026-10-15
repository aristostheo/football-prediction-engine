"""Bounded fixture cache that shares concurrent loads and provider failures."""

from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future
from datetime import UTC, date, datetime, timedelta
from threading import Lock

from football_predictor.domain import Competition
from football_predictor.live_fixtures import FixtureProviderError, LiveFixture


class FixtureCacheMiss(RuntimeError):
    pass


class FixtureDateCache:
    def __init__(
        self,
        fetch: Callable[[Competition, date], list[LiveFixture]],
        *,
        capacity: int = 1024,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("cache capacity must be positive")
        self.fetch, self.capacity = fetch, capacity
        self.now = now or (lambda: datetime.now(UTC))
        self._entries: OrderedDict[
            tuple[Competition, date],
            tuple[datetime, tuple[LiveFixture, ...] | FixtureProviderError],
        ] = OrderedDict()
        self._loading: dict[tuple[Competition, date], Future] = {}
        self._lock = Lock()

    def refresh_priority(self, competition: Competition, day: date) -> datetime:
        """Check never-loaded dates before reloading expired recent dates."""
        with self._lock:
            cached = self._entries.get((competition, day))
            return cached[0] if cached else datetime.min.replace(tzinfo=UTC)

    def get(
        self, competition: Competition, day: date, *, allow_fetch: bool = True
    ) -> list[LiveFixture]:
        key, now = (competition, day), self.now()
        with self._lock:
            cached = self._entries.get(key)
            if cached and cached[0] > now:
                self._entries.move_to_end(key)
                value = cached[1]
                if isinstance(value, FixtureProviderError):
                    raise value
                return list(value)
            self._entries.pop(key, None)
            future = self._loading.get(key)
            owner = future is None
            if owner:
                if not allow_fetch:
                    raise FixtureCacheMiss()
                future = Future()
                self._loading[key] = future
        if not owner:
            return list(future.result())
        try:
            value = tuple(self.fetch(competition, day))
            # Older dates change rarely; include empty responses in this TTL.
            if day < now.date() - timedelta(days=14):
                ttl = timedelta(hours=24)
            elif day > now.date():
                ttl = timedelta(minutes=10)
            else:
                ttl = timedelta(minutes=5)
            self._store(key, value, ttl)
            future.set_result(value)
            return list(value)
        except BaseException as error:
            if isinstance(error, FixtureProviderError):
                self._store(key, error, timedelta(minutes=5))
            future.set_exception(error)
            raise
        finally:
            with self._lock:
                self._loading.pop(key, None)

    def _store(self, key, value, ttl) -> None:
        with self._lock:
            self._entries[key] = (self.now() + ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)
