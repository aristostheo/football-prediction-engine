# Live fixtures and API service

The service exposes an optional live-fixture adapter and a prediction endpoint:

```bash
API_FOOTBALL_KEY=your_key \
uv run uvicorn football_predictor.api:app --reload
```

- `GET /health` confirms that the service is running.
- `GET /fixtures?competition=premier_league&date=YYYY-MM-DD` reads scheduled
  fixtures from API-Football when `API_FOOTBALL_KEY` is configured.
- `POST /predict` accepts canonical project team names and a fixture date after
  the local historical dataset's final result.

## Provider decision

V1 uses the optional [API-Football](https://www.api-football.com/) adapter for
current fixture discovery. Its free tier is sufficient for a portfolio demo;
the key is always an environment variable and is never committed.

## Freshness guardrail

The response always reports `history_through` and `history_age_days`. The
service deliberately refuses to back-predict a date at or before the local
history's latest completed match, preventing future information from entering a
historical prediction. Fixture discovery requires a live-provider key, while a
prediction only needs the local historical dataset. Current-result
synchronization and provider-to-canonical team mapping are the next production
hardening step.
