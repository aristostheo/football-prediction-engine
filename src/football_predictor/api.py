"""FastAPI surface for model health, fixture discovery, and match probabilities."""

from __future__ import annotations

import mimetypes
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator

from football_predictor.domain import Competition
from football_predictor.live_fixtures import (
    FixtureProvider,
    FixtureProviderError,
    LiveFixture,
    fixture_provider_from_environment,
)
from football_predictor.market_odds import (
    MarketOddsError,
    TheOddsApiProvider,
)
from football_predictor.prediction import (
    FixtureToPredict,
    MatchPrediction,
    PredictionComponents,
    PredictionContext,
    PredictionEngine,
)


class PredictionRequest(BaseModel):
    competition: Competition
    kickoff_date: date
    kickoff_at: datetime | None = None
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)
    odds_home: float | None = Field(default=None, gt=1.0)
    odds_draw: float | None = Field(default=None, gt=1.0)
    odds_away: float | None = Field(default=None, gt=1.0)

    @model_validator(mode="after")
    def market_odds_must_be_complete(self) -> PredictionRequest:
        supplied = (self.odds_home, self.odds_draw, self.odds_away)
        if any(value is not None for value in supplied) and any(
            value is None for value in supplied
        ):
            raise ValueError("provide all three decimal odds: home, draw, and away")
        if self.kickoff_at is not None:
            if self.kickoff_at.tzinfo is None or self.kickoff_at.utcoffset() is None:
                raise ValueError("kickoff_at must include a timezone offset")
            if self.kickoff_at.date() != self.kickoff_date:
                raise ValueError("kickoff_at must fall on kickoff_date")
        return self


class MarketOddsResponse(BaseModel):
    home_fair_odds: float
    draw_fair_odds: float
    away_fair_odds: float
    bookmaker_count: int
    source: str
    fetched_at: datetime


class ScorecardFixtureRequest(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    competition: Competition
    kickoff_date: date
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)


class ScorecardResultsRequest(BaseModel):
    fixtures: list[ScorecardFixtureRequest] = Field(max_length=500)


class ScorecardResultResponse(BaseModel):
    id: str
    result: str | None


class PredictionResponse(BaseModel):
    competition: Competition
    kickoff_date: date
    kickoff_at: datetime | None
    home_team: str
    away_team: str
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    model_policy: str
    history_through: date
    history_age_days: int
    forecasted_at: datetime
    model_home_win_probability: float
    model_draw_probability: float
    model_away_win_probability: float
    market_home_win_probability: float | None
    market_draw_probability: float | None
    market_away_win_probability: float | None
    context: PredictionContext
    components: PredictionComponents


class LiveFixtureResponse(BaseModel):
    fixture_id: str
    competition: Competition
    kickoff_at: str
    home_team: str
    away_team: str
    home_badge_url: str | None = None
    away_badge_url: str | None = None


def create_app(
    *,
    engine: PredictionEngine | None = None,
    fixture_provider: FixtureProvider | None = None,
    market_odds_provider: TheOddsApiProvider | None = None,
    web_dist_path: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="European Football Prediction Engine", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    configured_engine = engine
    configured_provider = fixture_provider
    configured_market_odds_provider = market_odds_provider
    engine_lock = Lock()

    def get_engine() -> PredictionEngine:
        nonlocal configured_engine
        if configured_engine is None:
            with engine_lock:
                if configured_engine is None:
                    history_path = Path(
                        os.environ.get(
                            "HISTORICAL_MATCHES_PATH", "data/model/historical_matches.csv.gz"
                        )
                    )
                    configured_engine = PredictionEngine.from_csv(history_path)
        return configured_engine

    def get_fixture_provider() -> FixtureProvider:
        nonlocal configured_provider
        if configured_provider is None:
            configured_provider = fixture_provider_from_environment()
        return configured_provider

    def get_market_odds_provider() -> TheOddsApiProvider:
        nonlocal configured_market_odds_provider
        if configured_market_odds_provider is None:
            configured_market_odds_provider = TheOddsApiProvider.from_environment()
        return configured_market_odds_provider

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/teams", response_model=list[str])
    def teams(competition: Competition) -> list[str]:
        try:
            return get_engine().available_teams(competition)
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/fixtures/next", response_model=LiveFixtureResponse | None)
    def next_fixture(
        competition: Competition,
        from_date: date = Query(alias="from"),
        days_ahead: int = Query(default=21, ge=1, le=31),
    ) -> LiveFixtureResponse | None:
        now = datetime.now(UTC)
        try:
            for offset in range(days_ahead):
                match_date = from_date + timedelta(days=offset)
                fixtures_for_day = get_fixture_provider().list_fixtures(competition, match_date)
                upcoming = [
                    fixture for fixture in fixtures_for_day
                    if _as_utc(fixture.kickoff_at) > now
                ]
                if upcoming:
                    first_fixture = min(upcoming, key=lambda item: _as_utc(item.kickoff_at))
                    return _fixture_response(first_fixture)
        except FixtureProviderError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return None

    @app.get("/fixtures", response_model=list[LiveFixtureResponse])
    def fixtures(
        competition: Competition,
        fixture_date: date = Query(alias="date"),
    ) -> list[LiveFixtureResponse]:
        try:
            live_fixtures = get_fixture_provider().list_fixtures(competition, fixture_date)
        except FixtureProviderError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return [_fixture_response(fixture) for fixture in live_fixtures]

    @app.get("/odds", response_model=MarketOddsResponse)
    def odds(
        competition: Competition,
        fixture_id: str,
        home_team: str,
        away_team: str,
        kickoff_at: datetime,
    ) -> MarketOddsResponse:
        if kickoff_at.tzinfo is None or kickoff_at.utcoffset() is None:
            raise HTTPException(status_code=422, detail="kickoff_at must include a timezone offset")
        if kickoff_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=400,
                detail="Market odds are available for upcoming fixtures only",
            )
        try:
            quote = get_market_odds_provider().get_match_odds(
                competition, home_team, away_team, kickoff_at
            )
        except MarketOddsError as error:
            status = 503 if "not configured" in str(error) else 502
            raise HTTPException(status_code=status, detail=str(error)) from error
        return MarketOddsResponse(
            home_fair_odds=quote.home_fair_odds,
            draw_fair_odds=quote.draw_fair_odds,
            away_fair_odds=quote.away_fair_odds,
            bookmaker_count=quote.bookmaker_count,
            source="The Odds API · bookmaker consensus, margin removed",
            fetched_at=quote.fetched_at,
        )

    @app.post("/predict", response_model=PredictionResponse)
    def predict(request: PredictionRequest) -> PredictionResponse:
        try:
            prediction = get_engine().predict(FixtureToPredict(**request.model_dump()))
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _prediction_response(prediction)

    @app.post("/scorecard/results", response_model=list[ScorecardResultResponse])
    def scorecard_results(request: ScorecardResultsRequest) -> list[ScorecardResultResponse]:
        if len({fixture.id for fixture in request.fixtures}) != len(request.fixtures):
            raise HTTPException(status_code=422, detail="scorecard fixture ids must be unique")
        engine = get_engine()
        keys = [
            (
                fixture.id,
                fixture.competition.value,
                fixture.kickoff_date,
                fixture.home_team,
                fixture.away_team,
            )
            for fixture in request.fixtures
        ]
        results = engine.find_results(keys)
        return [
            ScorecardResultResponse(id=fixture.id, result=results[fixture.id])
            for fixture in request.fixtures
        ]

    resolved_web_dist = web_dist_path or Path(os.environ.get("WEB_DIST_PATH", "web/dist"))
    if resolved_web_dist.is_dir():
        resolved_web_root = resolved_web_dist.resolve()

        @app.get("/{requested_path:path}", include_in_schema=False)
        async def frontend(requested_path: str) -> Response:
            requested_file = (resolved_web_root / requested_path).resolve()
            if (
                requested_path
                and requested_file.is_relative_to(resolved_web_root)
                and requested_file.is_file()
            ):
                media_type = mimetypes.guess_type(requested_file)[0]
                return Response(requested_file.read_bytes(), media_type=media_type)
            index_file = resolved_web_root / "index.html"
            return Response(index_file.read_bytes(), media_type="text/html")

    return app


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _fixture_response(fixture: LiveFixture) -> LiveFixtureResponse:
    return LiveFixtureResponse(
        fixture_id=fixture.fixture_id,
        competition=fixture.competition,
        kickoff_at=fixture.kickoff_at.isoformat(),
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        home_badge_url=fixture.home_badge_url,
        away_badge_url=fixture.away_badge_url,
    )


def _prediction_response(prediction: MatchPrediction) -> PredictionResponse:
    return PredictionResponse(
        competition=prediction.fixture.competition,
        kickoff_date=prediction.fixture.kickoff_date,
        kickoff_at=prediction.fixture.kickoff_at,
        home_team=prediction.fixture.home_team,
        away_team=prediction.fixture.away_team,
        home_win_probability=prediction.home_win_probability,
        draw_probability=prediction.draw_probability,
        away_win_probability=prediction.away_win_probability,
        model_policy=prediction.model_policy,
        history_through=prediction.history_through,
        history_age_days=prediction.history_age_days,
        forecasted_at=prediction.forecasted_at,
        model_home_win_probability=prediction.model_probabilities[0],
        model_draw_probability=prediction.model_probabilities[1],
        model_away_win_probability=prediction.model_probabilities[2],
        market_home_win_probability=(
            prediction.market_probabilities[0] if prediction.market_probabilities else None
        ),
        market_draw_probability=(
            prediction.market_probabilities[1] if prediction.market_probabilities else None
        ),
        market_away_win_probability=(
            prediction.market_probabilities[2] if prediction.market_probabilities else None
        ),
        context=prediction.context,
        components=prediction.components,
    )


app = create_app()
