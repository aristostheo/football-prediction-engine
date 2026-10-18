from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest

import football_predictor.market_odds as market_odds
from football_predictor.domain import Competition
from football_predictor.market_odds import MarketOddsError, TheOddsApiProvider


def _payload() -> bytes:
    return json.dumps([{
        "home_team": "Nottingham Forest",
        "away_team": "Arsenal",
        "commence_time": "2026-10-18T14:00:00Z",
        "bookmakers": [
            {"key": "book-a", "markets": [{"key": "h2h", "outcomes": [
                {"name": "Nottingham Forest", "price": 3.0},
                {"name": "Draw", "price": 3.4},
                {"name": "Arsenal", "price": 2.4},
            ]}]},
            {"key": "book-b", "markets": [{"key": "h2h", "outcomes": [
                {"name": "Nottingham Forest", "price": 3.1},
                {"name": "Draw", "price": 3.3},
                {"name": "Arsenal", "price": 2.3},
            ]}]},
        ],
    }]).encode()


def test_odds_provider_matches_fixture_removes_vig_and_caches(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        requests.append(request)
        return io.BytesIO(_payload())

    monkeypatch.setattr(market_odds, "urlopen", fake_urlopen)
    provider = TheOddsApiProvider("secret")
    kickoff = datetime(2026, 10, 18, 14, 0, tzinfo=UTC)

    first = provider.get_match_odds(
        Competition.PREMIER_LEAGUE, "Nottingham Forest FC", "Arsenal FC", kickoff
    )
    second = provider.get_match_odds(
        Competition.PREMIER_LEAGUE, "Nottingham Forest", "Arsenal", kickoff
    )

    assert first.bookmaker_count == 2
    assert second.bookmaker_count == first.bookmaker_count
    assert first.home_fair_odds > 1
    assert first.draw_fair_odds > 1
    assert first.away_fair_odds > 1
    assert first.fetched_at.tzinfo is UTC
    assert len(requests) == 1
    assert "soccer_epl" in requests[0].full_url
    assert "regions=eu" in requests[0].full_url


def test_odds_provider_requires_exact_match_and_kickoff_window(monkeypatch) -> None:
    monkeypatch.setattr(market_odds, "urlopen", lambda request, timeout: io.BytesIO(_payload()))
    provider = TheOddsApiProvider("secret")
    with pytest.raises(MarketOddsError, match="No matching 1X2"):
        provider.get_match_odds(
            Competition.PREMIER_LEAGUE,
            "Chelsea",
            "Arsenal",
            datetime(2026, 10, 18, 14, 0, tzinfo=UTC),
        )
    with pytest.raises(MarketOddsError, match="No matching 1X2"):
        provider.get_match_odds(
            Competition.PREMIER_LEAGUE,
            "Nottingham Forest",
            "Arsenal",
            datetime(2026, 10, 19, 14, 0, tzinfo=UTC),
        )


def test_odds_provider_resolves_greek_club_aliases(monkeypatch) -> None:
    payload = json.dumps([{
        "home_team": "Olympiacos",
        "away_team": "PAOK Thessaloniki",
        "commence_time": "2026-10-18T17:00:00Z",
        "bookmakers": [{
            "markets": [{"key": "h2h", "outcomes": [
                {"name": "Olympiacos", "price": 1.9},
                {"name": "Draw", "price": 3.3},
                {"name": "PAOK Thessaloniki", "price": 4.0},
            ]}],
        }],
    }]).encode()
    monkeypatch.setattr(market_odds, "urlopen", lambda request, timeout: io.BytesIO(payload))
    quote = TheOddsApiProvider("secret").get_match_odds(
        Competition.SUPER_LEAGUE_GREECE,
        "Olympiakos Piraeus",
        "PAOK Saloniki",
        datetime(2026, 10, 18, 17, 0, tzinfo=UTC),
    )
    assert quote.bookmaker_count == 1


def test_odds_provider_requires_configuration(monkeypatch) -> None:
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    with pytest.raises(MarketOddsError, match="THE_ODDS_API_KEY"):
        TheOddsApiProvider.from_environment()


def test_cached_quotes_keep_fetch_and_source_times(monkeypatch):
    payload = json.loads(_payload())
    books = payload[0]["bookmakers"]
    books[0]["last_update"] = "2026-10-13T10:00:00Z"
    books[0]["markets"][0]["last_update"] = "2026-10-13T11:00:00Z"
    books[1]["last_update"] = "2026-10-14T10:00:00Z"
    calls = []
    clock = [datetime(2026, 10, 17, 12, tzinfo=UTC)]

    def respond(request, timeout):
        calls.append(request)
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(market_odds, "urlopen", respond)
    provider = TheOddsApiProvider("test-only", now=lambda: clock[0])
    args = (Competition.PREMIER_LEAGUE, "Nottingham Forest", "Arsenal",
            datetime(2026, 10, 18, 14, tzinfo=UTC))
    first = provider.get_match_odds(*args)
    clock[0] += timedelta(minutes=3)
    second = provider.get_match_odds(*args)
    assert first == second
    assert first.fetched_at == datetime(2026, 10, 17, 12, tzinfo=UTC)
    assert first.oldest_quote_at == datetime(2026, 10, 13, 11, tzinfo=UTC)
    assert first.newest_quote_at == datetime(2026, 10, 14, 10, tzinfo=UTC)
    assert first.timestamped_bookmaker_count == 2
    assert first.bookmakers == ("book-a", "book-b")
    assert len(calls) == 1
    provider._cache_seconds = 0
    third = provider.get_match_odds(*args)
    assert third.fetched_at == clock[0]
    assert third.oldest_quote_at == first.oldest_quote_at
    assert len(calls) == 2


@pytest.mark.parametrize("timestamp", [None, "invalid", "2026-10-17T12:00:00",
                                       "2099-01-01T00:00:00Z"])
def test_missing_invalid_or_future_quote_times_are_not_fabricated(monkeypatch, timestamp):
    payload = json.loads(_payload())
    for book in payload[0]["bookmakers"]:
        book["last_update"] = timestamp
    monkeypatch.setattr(market_odds, "urlopen",
                        lambda request, timeout: io.BytesIO(json.dumps(payload).encode()))
    quote = TheOddsApiProvider("test-only").get_match_odds(
        Competition.PREMIER_LEAGUE, "Nottingham Forest", "Arsenal",
        datetime(2026, 10, 18, 14, tzinfo=UTC),
    )
    assert quote.oldest_quote_at is quote.newest_quote_at is None
    assert quote.timestamped_bookmaker_count == 0


@pytest.mark.parametrize("price", [float("inf"), float("nan"), -3, 1])
def test_odds_consensus_excludes_books_with_invalid_prices(monkeypatch, price):
    payload = json.loads(_payload())
    payload[0]["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] = price
    monkeypatch.setattr(market_odds, "urlopen",
                        lambda request, timeout: io.BytesIO(json.dumps(payload).encode()))
    quote = TheOddsApiProvider("test-only").get_match_odds(
        Competition.PREMIER_LEAGUE, "Nottingham Forest", "Arsenal",
        datetime(2026, 10, 18, 14, tzinfo=UTC),
    )
    assert quote.bookmaker_count == 1
    assert quote.bookmakers == ("book-b",)


def test_concurrent_odds_calls_share_one_snapshot_fetch(monkeypatch):
    started, release = Event(), Event()
    calls = []

    def respond(request, timeout):
        calls.append(request)
        started.set()
        assert release.wait(3)
        return io.BytesIO(_payload())

    monkeypatch.setattr(market_odds, "urlopen", respond)
    provider = TheOddsApiProvider("test-only")
    args = (Competition.PREMIER_LEAGUE, "Nottingham Forest", "Arsenal",
            datetime(2026, 10, 18, 14, tzinfo=UTC))
    with ThreadPoolExecutor(max_workers=8) as pool:
        first = pool.submit(provider.get_match_odds, *args)
        assert started.wait(3)
        others = [pool.submit(provider.get_match_odds, *args) for _ in range(7)]
        release.set()
        quote = first.result(timeout=3)
        assert all(f.result(timeout=3) == quote for f in others)
    assert len(calls) == 1
