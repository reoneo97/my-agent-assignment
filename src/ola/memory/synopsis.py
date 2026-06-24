from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ola.config import DB_PATH
from ola.memory.store import _init_schema


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def get_synopsis(operator_id: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM operator_synopsis WHERE operator_id = ?", (operator_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_synopsis(operator_id: str, text: str, source_through: str | None = None, db_path: str = DB_PATH) -> int:
    """Upsert synopsis; returns new version number."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT version FROM operator_synopsis WHERE operator_id = ?", (operator_id,)
    ).fetchone()
    version = (row["version"] + 1) if row else 1
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO operator_synopsis (operator_id, text, generated_at, source_through, version)
           VALUES (?,?,?,?,?)
           ON CONFLICT(operator_id) DO UPDATE SET
             text=excluded.text, generated_at=excluded.generated_at,
             source_through=excluded.source_through, version=excluded.version""",
        (operator_id, text, now, source_through, version),
    )
    conn.commit()
    conn.close()
    return version
