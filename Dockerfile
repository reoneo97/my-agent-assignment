FROM node:20-alpine AS ui-builder
WORKDIR /ui
COPY ui/package.json ui/package-lock.json* ./
RUN npm install
COPY ui/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src/ ./src/
COPY sim/ ./sim/
COPY scripts/ ./scripts/
COPY api/ ./api/
COPY --from=ui-builder /ui/dist ./ui/dist

RUN uv sync --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
