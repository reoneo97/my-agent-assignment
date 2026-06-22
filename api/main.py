from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from ola.config import DB_PATH  # noqa: E402
from ola.domain.events import OperatorInteraction  # noqa: E402
from ola.memory.store import get_profile  # noqa: E402
from ola.pipeline import stream_interaction  # noqa: E402

app = FastAPI(title="Operator Learning Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_DB = os.environ.get("OLA_DB_PATH", DB_PATH)


class ChatRequest(BaseModel):
    operator_id: str = "op-demo-01"
    message: str
    event_type: str = "question"
    alarm_code: str | None = None
    shift: str | None = "day"


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    interaction = OperatorInteraction(
        id=str(uuid.uuid4()),
        operator_id=req.operator_id,
        timestamp=datetime.now(timezone.utc),
        shift=req.shift,  # type: ignore[arg-type]
        event_type=req.event_type,
        alarm_code=req.alarm_code,
        raw_text=req.message,
        outcome=None,
    )

    async def event_generator():  # type: ignore[return]
        try:
            async for event in stream_interaction(interaction, db_path=_DB):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/profile/{operator_id}")
async def profile(operator_id: str):  # type: ignore[return]
    prof = get_profile(operator_id, db_path=_DB)
    return {
        "operator_id": prof.operator_id,
        "items": [
            {
                "id": item.id,
                "text": item.text,
                "category": item.category.value,
                "status": item.status,
                "evidence_count": item.evidence_count,
            }
            for item in prof.active_items
        ],
    }


@app.get("/api/health")
async def health():  # type: ignore[return]
    return {"status": "ok"}


# Serve the React build when running in Docker (ui/dist is copied into the image)
_UI_DIR = Path(__file__).parent.parent / "ui" / "dist"
if _UI_DIR.exists():
    app.mount("/", StaticFiles(directory=_UI_DIR, html=True), name="ui")
