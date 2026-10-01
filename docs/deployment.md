# Dashboard and deployment

The React dashboard and FastAPI service deploy as one container. Vite produces
static assets during the first Docker stage; FastAPI serves those assets and the
JSON endpoints from the same origin in the runtime stage.

## Local development

Run the API and Vite development servers in separate terminals:

```bash
uv run uvicorn football_predictor.api:app --reload
cd web
npm install
npm run dev
```

Vite proxies `/api` requests to port 8000. The production build instead calls
the same-origin `/predict` and `/fixtures` routes directly.

## Container build

```bash
docker build -t football-prediction-engine .
docker run --rm -p 8000:8000 football-prediction-engine
```

Open `http://localhost:8000`. Supply `GOAL_API_KEY` at runtime to activate live
fixture discovery. `API_FOOTBALL_KEY` is an optional fallback. Manual prediction
remains available without either key.

The checked-in compressed model input is a generated, canonical dataset derived
from the source URLs documented in its rows. Raw third-party repositories are
not included. Rebuild it through the documented ingestion pipeline whenever the
history is updated.

## Render

`render.yaml` defines a Docker web service with `/health` as its health check.
Create the service from the repository and add `GOAL_API_KEY` as a secret
environment variable. Add `API_FOOTBALL_KEY` only if a paid/current-season
fallback is desired. The first prediction request trains the models and keeps
them in the server process for subsequent requests.
