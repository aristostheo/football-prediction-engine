FROM node:22-bookworm-slim AS web-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HISTORICAL_MATCHES_PATH=/app/data/model/historical_matches.csv.gz \
    WEB_DIST_PATH=/app/web/dist

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --locked --no-dev

COPY data/model/historical_matches.csv.gz ./data/model/historical_matches.csv.gz
COPY --from=web-builder /app/web/dist ./web/dist

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "football_predictor.api:app", "--host", "0.0.0.0", "--port", "8000"]
