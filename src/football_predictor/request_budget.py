"""Limit actual Goal API HTTP attempts during journal backfills."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, date, datetime
from threading import Lock


class GoalRequestLimit(RuntimeError):
    """Defer a result lookup rather than spending beyond its allowance."""


class DailyAllowance:
    """A UTC-day allowance shared by one API process, not an account-wide meter."""

    def __init__(self, limit: int = 100, *, today: Callable[[], date] | None = None) -> None:
        if limit < 0:
            raise ValueError("daily allowance cannot be negative")
        self.limit = limit
        self.today = today or (lambda: datetime.now(UTC).date())
        self._day: date | None = None
        self._used = 0
        self._lock = Lock()

    def consume(self) -> None:
        with self._lock:
            day = self.today()
            if day != self._day:
                self._day, self._used = day, 0
            if self._used >= self.limit:
                raise GoalRequestLimit("journal daily Goal API allowance reached")
            self._used += 1


@dataclass
class _RequestScope:
    limit: int
    daily: DailyAllowance
    used: int = 0


_scope: ContextVar[_RequestScope | None] = ContextVar("journal_goal_request_scope", default=None)


@contextmanager
def goal_request_scope(limit: int, daily: DailyAllowance) -> Iterator[None]:
    token = _scope.set(_RequestScope(limit=limit, daily=daily))
    try:
        yield
    finally:
        _scope.reset(token)


def consume_goal_request() -> None:
    scope = _scope.get()
    if scope is None:
        return
    if scope.used >= scope.limit:
        raise GoalRequestLimit("journal request allowance reached")
    scope.daily.consume()
    scope.used += 1
