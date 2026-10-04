from __future__ import annotations

import io
import json
from datetime import UTC, datetime

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


def test_odds_provider_requires_configuration(monkeypatch) -> None:
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    with pytest.raises(MarketOddsError, match="THE_ODDS_API_KEY"):
        TheOddsApiProvider.from_environment()
