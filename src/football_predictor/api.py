"""FastAPI surface for model health, fixture discovery, and match probabilities."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from football_predictor.domain import Competition
from football_predictor.live_fixtures import (
    ApiFootballFixtureProvider,
    FixtureProvider,
    FixtureProviderError,
    LiveFixture,
)
from football_predictor.prediction import FixtureToPredict, MatchPrediction, PredictionEngine


class PredictionRequest(BaseModel):
    competition: Competition
    kickoff_date: date
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)


class PredictionResponse(BaseModel):
    competition: Competition
    kickoff_date: date
    home_team: str
    away_team: str
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    model_policy: str
    history_through: date
    history_age_days: int


class LiveFixtureResponse(BaseModel):
    fixture_id: int
    competition: Competition
    kickoff_at: str
    home_team: str
    away_team: str


def create_app(
    *, engine: PredictionEngine | None = None, fixture_provider: FixtureProvider | None = None
) -> FastAPI:
    app = FastAPI(title="European Football Prediction Engine", version="0.1.0")
    configured_engine = engine
    configured_provider = fixture_provider

    def get_engine() -> PredictionEngine:
        nonlocal configured_engine
        if configured_engine is None:
            history_path = Path(
                os.environ.get("HISTORICAL_MATCHES_PATH", "data/processed/historical_matches.csv")
            )
            configured_engine = PredictionEngine.from_csv(history_path)
        return configured_engine

    def get_fixture_provider() -> FixtureProvider:
        nonlocal configured_provider
        if configured_provider is None:
            configured_provider = ApiFootballFixtureProvider.from_environment()
        return configured_provider

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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

    @app.post("/predict", response_model=PredictionResponse)
    def predict(request: PredictionRequest) -> PredictionResponse:
        try:
            prediction = get_engine().predict(FixtureToPredict(**request.model_dump()))
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _prediction_response(prediction)

    return app


def _fixture_response(fixture: LiveFixture) -> LiveFixtureResponse:
    return LiveFixtureResponse(
        fixture_id=fixture.fixture_id,
        competition=fixture.competition,
        kickoff_at=fixture.kickoff_at.isoformat(),
        home_team=fixture.home_team,
        away_team=fixture.away_team,
    )


def _prediction_response(prediction: MatchPrediction) -> PredictionResponse:
    return PredictionResponse(
        competition=prediction.fixture.competition,
        kickoff_date=prediction.fixture.kickoff_date,
        home_team=prediction.fixture.home_team,
        away_team=prediction.fixture.away_team,
        home_win_probability=prediction.home_win_probability,
        draw_probability=prediction.draw_probability,
        away_win_probability=prediction.away_win_probability,
        model_policy=prediction.model_policy,
        history_through=prediction.history_through,
        history_age_days=prediction.history_age_days,
    )


app = create_app()
