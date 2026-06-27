FROM node:20-alpine AS ui-builder
WORKDIR /ui
COPY ui/package.json ui/package-lock.json* ./
RUN npm install
COPY ui/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install deps first for layer caching
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src/ ./src/
COPY sim/ ./sim/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY entrypoint.sh ./
COPY --from=ui-builder /ui/dist ./ui/dist

RUN uv sync --no-dev && chmod +x entrypoint.sh

ENV PYTHONUNBUFFERED=1

# Bootstrap runs python -m ola.bootstrap (idempotent), then execs uvicorn.
# Neo4j must be healthy before this container starts (compose depends_on).
ENTRYPOINT ["./entrypoint.sh"]
