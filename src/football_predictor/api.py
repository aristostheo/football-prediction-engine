"""FastAPI surface for model health, fixture discovery, and match probabilities."""

from __future__ import annotations

import mimetypes
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from football_predictor.domain import Competition
from football_predictor.live_fixtures import (
    FixtureProvider,
    FixtureProviderError,
    LiveFixture,
    fixture_provider_from_environment,
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
    fixture_id: str
    competition: Competition
    kickoff_at: str
    home_team: str
    away_team: str


def create_app(
    *,
    engine: PredictionEngine | None = None,
    fixture_provider: FixtureProvider | None = None,
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
            configured_provider = fixture_provider_from_environment()
        return configured_provider

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/fixtures", response_model=list[LiveFixtureResponse])
    async def fixtures(
        competition: Competition,
        fixture_date: date = Query(alias="date"),
    ) -> list[LiveFixtureResponse]:
        try:
            live_fixtures = get_fixture_provider().list_fixtures(competition, fixture_date)
        except FixtureProviderError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return [_fixture_response(fixture) for fixture in live_fixtures]

    @app.post("/predict", response_model=PredictionResponse)
    async def predict(request: PredictionRequest) -> PredictionResponse:
        try:
            prediction = get_engine().predict(FixtureToPredict(**request.model_dump()))
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _prediction_response(prediction)

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
