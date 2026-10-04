"""Prospective market consensus odds from The Odds API."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from football_predictor.domain import Competition
from football_predictor.team_names import canonical_team_name

ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEYS = {
    Competition.PREMIER_LEAGUE: "soccer_epl",
    Competition.SUPER_LEAGUE_GREECE: "soccer_greece_super_league",
}


@dataclass(frozen=True)
class MarketOdds:
    home_fair_odds: float
    draw_fair_odds: float
    away_fair_odds: float
    bookmaker_count: int
    fetched_at: datetime


class MarketOddsError(RuntimeError):
    """Raised when live market odds cannot be retrieved safely."""


class TheOddsApiProvider:
    """Fetch and cache prospective 1X2 quotes; never used for historical training."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = ODDS_API_BASE_URL,
        cache_seconds: int = 600,
    ) -> None:
        if not api_key:
            raise ValueError("The Odds API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._cache_seconds = cache_seconds
        self._cache: dict[Competition, tuple[float, list[dict[str, object]]]] = {}
        self._lock = Lock()

    @classmethod
    def from_environment(cls) -> TheOddsApiProvider:
        api_key = os.environ.get("THE_ODDS_API_KEY")
        if not api_key:
            raise MarketOddsError("THE_ODDS_API_KEY is not configured")
        return cls(api_key)

    def get_match_odds(
        self,
        competition: Competition,
        home_team: str,
        away_team: str,
        kickoff_at: datetime,
    ) -> MarketOdds:
        events = self._events(competition)
        target_kickoff = _as_utc(kickoff_at)
        for event in events:
            if not isinstance(event, dict):
                continue
            if not _same_team(event.get("home_team"), home_team, competition):
                continue
            if not _same_team(event.get("away_team"), away_team, competition):
                continue
            try:
                event_kickoff = datetime.fromisoformat(
                    str(event["commence_time"]).replace("Z", "+00:00")
                )
            except (KeyError, TypeError, ValueError):
                continue
            if abs((_as_utc(event_kickoff) - target_kickoff).total_seconds()) > 12 * 3600:
                continue
            probabilities = _bookmaker_consensus(event, competition)
            if probabilities is None:
                continue
            return MarketOdds(
                home_fair_odds=1 / probabilities[0],
                draw_fair_odds=1 / probabilities[1],
                away_fair_odds=1 / probabilities[2],
                bookmaker_count=probabilities[3],
                fetched_at=datetime.now(UTC),
            )
        raise MarketOddsError(
            "No matching 1X2 market was available for this fixture yet."
        )

    def _events(self, competition: Competition) -> list[dict[str, object]]:
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(competition)
            if cached and now - cached[0] < self._cache_seconds:
                return cached[1]
        query = urlencode(
            {
                "apiKey": self._api_key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal",
            }
        )
        request = Request(
            f"{self._base_url}/sports/{SPORT_KEYS[competition]}/odds/?{query}",
            headers={"Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed provider URL
                payload = json.load(response)
        except HTTPError as error:
            if error.code in (401, 403):
                raise MarketOddsError(
                    "The Odds API rejected the key or this league is not available on its plan."
                ) from error
            raise MarketOddsError(f"The Odds API returned HTTP {error.code}.") from error
        except (OSError, json.JSONDecodeError) as error:
            raise MarketOddsError("The Odds API request failed.") from error
        if not isinstance(payload, list):
            raise MarketOddsError("The Odds API returned an unexpected response.")
        events = [item for item in payload if isinstance(item, dict)]
        with self._lock:
            self._cache[competition] = (time.monotonic(), events)
        return events


def _bookmaker_consensus(
    event: dict[str, object], competition: Competition
) -> tuple[float, float, float, int] | None:
    bookmakers = event.get("bookmakers")
    if not isinstance(bookmakers, list):
        return None
    fair_books: list[tuple[float, float, float]] = []
    home = str(event.get("home_team", ""))
    away = str(event.get("away_team", ""))
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, dict):
            continue
        markets = bookmaker.get("markets")
        if not isinstance(markets, list):
            continue
        market = next(
            (entry for entry in markets if isinstance(entry, dict) and entry.get("key") == "h2h"),
            None,
        )
        outcomes = market.get("outcomes") if isinstance(market, dict) else None
        if not isinstance(outcomes, list):
            continue
        prices: dict[str, float] = {}
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            name = outcome.get("name")
            try:
                price = float(outcome.get("price"))
            except (TypeError, ValueError):
                continue
            if price > 1 and isinstance(name, str):
                prices[name] = price
        home_price = next((v for k, v in prices.items() if _same_team(k, home, competition)), None)
        away_price = next((v for k, v in prices.items() if _same_team(k, away, competition)), None)
        draw_price = next((v for k, v in prices.items() if k.strip().lower() == "draw"), None)
        if home_price and away_price and draw_price:
            raw = (1 / home_price, 1 / draw_price, 1 / away_price)
            margin = sum(raw)
            fair_books.append(tuple(value / margin for value in raw))
    if not fair_books:
        return None
    mean = tuple(sum(row[index] for row in fair_books) / len(fair_books) for index in range(3))
    total = sum(mean)
    normalized = tuple(value / total for value in mean)
    return normalized[0], normalized[1], normalized[2], len(fair_books)


def _team_key(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    return re.sub(r"\b(fc|afc|cf|sc|club)\b", "", normalized).strip()


def _same_team(first: object, second: object, competition: Competition) -> bool:
    first_name = canonical_team_name(str(first), competition)
    second_name = canonical_team_name(str(second), competition)
    first_key = _team_key(first_name)
    return bool(first_key) and first_key == _team_key(second_name)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
