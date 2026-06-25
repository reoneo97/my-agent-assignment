from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from ola.api.auth import BasicAuthMiddleware  # noqa: E402
from ola.api.routes import router  # noqa: E402
from ola.telemetry import setup_tracing  # noqa: E402

setup_tracing()

app = FastAPI(title="Operator Learning Assistant API")

_CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_CORS_ORIGIN, "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Must come after CORSMiddleware in source (Starlette applies middleware
# innermost-first by add order, so this runs its auth check before CORS).
app.add_middleware(BasicAuthMiddleware)

app.include_router(router)

# Serve the React build when running in Docker (ui/dist copied into image)
_UI_DIR = Path(__file__).parent.parent.parent.parent / "ui" / "dist"
if _UI_DIR.exists():
    app.mount("/", StaticFiles(directory=_UI_DIR, html=True), name="ui")
