from __future__ import annotations

import json
import sqlite3
import uuid as _uuid_mod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ola.config import DB_PATH
from ola.domain.events import OperatorInteraction
from ola.domain.memory import (
    Hypothesis,
    MemoryItem,
    MemoryOperation,
    OperatorProfile,
)
from ola.domain.signals import TraitCategory
from ola.memory.tiers import assign_status

_SCHEMA_SQL = Path(__file__).parent.parent.parent.parent / "data" / "sql" / "schema.sql"

_FALLBACK_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, operator_id TEXT NOT NULL, opened_at TEXT NOT NULL,
    closed_at TEXT, trigger_alarm_code TEXT, machine_id TEXT,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, operator_id TEXT NOT NULL, session_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator', timestamp TEXT NOT NULL,
    shift TEXT, machine_id TEXT, alarm_code TEXT, event_type TEXT NOT NULL,
    requested_modality TEXT, content TEXT NOT NULL, outcome TEXT
);
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY, source_event_id TEXT NOT NULL, operator_id TEXT NOT NULL,
    category TEXT NOT NULL, value TEXT NOT NULL, observation TEXT, timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_operations (
    id TEXT PRIMARY KEY, operator_id TEXT NOT NULL, op_type TEXT NOT NULL,
    target_item_id TEXT, text TEXT, value TEXT, category TEXT, source_event_id TEXT,
    source TEXT NOT NULL DEFAULT 'hot_path',
    high_weight INTEGER NOT NULL DEFAULT 0, timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_synopsis (
    operator_id TEXT PRIMARY KEY, text TEXT NOT NULL,
    generated_at TEXT NOT NULL, source_through TEXT, version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS conformance_events (
    id TEXT PRIMARY KEY, source_event_id TEXT NOT NULL, operator_id TEXT NOT NULL,
    alarm_code TEXT, procedure_id TEXT, expected_disposition TEXT, observed_action TEXT,
    conformance TEXT, outcome_status TEXT NOT NULL DEFAULT 'pending',
    outcome_quality TEXT, quadrant TEXT, review_due_at TEXT, reviewed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS outcomes (
    id TEXT PRIMARY KEY, conformance_event_id TEXT, machine_id TEXT NOT NULL,
    window_start TEXT NOT NULL, window_end TEXT NOT NULL,
    downtime_sec INTEGER, alarm_count INTEGER, peer_alarm_avg REAL, recurred INTEGER
);
CREATE TABLE IF NOT EXISTS hypotheses (
    id TEXT PRIMARY KEY, operator_id TEXT, kind TEXT NOT NULL,
    description TEXT NOT NULL, evidence_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'proposed', source_event_ids TEXT, created_at TEXT NOT NULL
);
"""


def _init_schema(conn: sqlite3.Connection) -> None:
    if _SCHEMA_SQL.exists():
        conn.executescript(_SCHEMA_SQL.read_text())
    else:
        conn.executescript(_FALLBACK_SCHEMA)


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


# ── Sessions ──────────────────────────────────────────────────────────────────

def get_open_session(operator_id: str, db_path: str = DB_PATH) -> str | None:
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT id FROM sessions WHERE operator_id = ? AND status = 'open' ORDER BY opened_at DESC LIMIT 1",
        (operator_id,),
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def open_session(
    operator_id: str,
    trigger_alarm_code: str | None = None,
    machine_id: str | None = None,
    db_path: str = DB_PATH,
) -> str:
    session_id = str(_uuid_mod.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    conn.execute(
        "INSERT INTO sessions (id, operator_id, opened_at, trigger_alarm_code, machine_id) VALUES (?,?,?,?,?)",
        (session_id, operator_id, now, trigger_alarm_code, machine_id),
    )
    conn.commit()
    conn.close()
    return session_id


def close_session(session_id: str, status: str, db_path: str = DB_PATH) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    conn.execute(
        "UPDATE sessions SET status = ?, closed_at = ? WHERE id = ?",
        (status, now, session_id),
    )
    conn.commit()
    conn.close()


def get_or_create_session(
    operator_id: str,
    trigger_alarm_code: str | None = None,
    machine_id: str | None = None,
    db_path: str = DB_PATH,
) -> str:
    sid = get_open_session(operator_id, db_path=db_path)
    if sid:
        return sid
    return open_session(operator_id, trigger_alarm_code, machine_id, db_path=db_path)


# ── Events ────────────────────────────────────────────────────────────────────

def append_event(interaction: OperatorInteraction, db_path: str = DB_PATH) -> None:
    conn = _connect(db_path)
    conn.execute(
        """INSERT OR IGNORE INTO events
           (id, operator_id, session_id, role, timestamp, shift, machine_id,
            alarm_code, event_type, requested_modality, content, outcome)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            interaction.id,
            interaction.operator_id,
            interaction.session_id or "",
            interaction.role,
            interaction.timestamp.isoformat(),
            interaction.shift,
            interaction.machine_id,
            interaction.alarm_code,
            interaction.event_type,
            interaction.requested_modality,
            interaction.content,
            interaction.outcome,
        ),
    )
    conn.commit()
    conn.close()


def get_session_thread(session_id: str, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    """Return all events for a session ordered by timestamp (both roles)."""
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT role, event_type, content, timestamp FROM events WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_events(
    operator_id: str,
    limit: int = 50,
    db_path: str = DB_PATH,
) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM events WHERE operator_id = ? AND role = 'operator' ORDER BY timestamp DESC LIMIT ?",
        (operator_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Signals ───────────────────────────────────────────────────────────────────

def append_signal(
    signal_id: str,
    source_event_id: str,
    operator_id: str,
    category: str,
    value: str,
    observation: str,
    timestamp: datetime,
    db_path: str = DB_PATH,
) -> None:
    conn = _connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO signals (id, source_event_id, operator_id, category, value, observation, timestamp) VALUES (?,?,?,?,?,?,?)",
        (signal_id, source_event_id, operator_id, category, value, observation, timestamp.isoformat()),
    )
    conn.commit()
    conn.close()


# ── Memory operations ─────────────────────────────────────────────────────────

def append_operation(op: MemoryOperation, db_path: str = DB_PATH) -> None:
    conn = _connect(db_path)
    conn.execute(
        """INSERT OR IGNORE INTO memory_operations
           (id, operator_id, op_type, target_item_id, text, value, category,
            source_event_id, source, high_weight, timestamp)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            op.id,
            op.operator_id,
            op.op_type,
            op.target_item_id,
            op.text,
            op.value,
            op.category.value if op.category else None,
            op.source_event_id,
            op.source,
            1 if op.high_weight else 0,
            op.timestamp.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


# ── Profile fold ──────────────────────────────────────────────────────────────

def get_profile(operator_id: str, db_path: str = DB_PATH) -> OperatorProfile:
    """Fold the memory_operations log into the current active profile. Deterministic."""
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM memory_operations WHERE operator_id = ? ORDER BY timestamp ASC",
        (operator_id,),
    ).fetchall()
    conn.close()

    items: dict[str, dict[str, Any]] = {}

    for row in rows:
        op_type = row["op_type"]
        item_id = row["id"]
        target = row["target_item_id"]
        ts = row["timestamp"]
        src = row["source_event_id"]
        hw = bool(row["high_weight"])

        if op_type == "ADD":
            items[item_id] = {
                "id": item_id, "operator_id": operator_id,
                "text": row["text"], "value": row["value"], "category": row["category"],
                "evidence_count": 1, "source_event_ids": [src],
                "created_at": ts, "last_reinforced_at": ts,
                "superseded_by": None, "confirmed": hw,
            }

        elif op_type == "REINFORCE" and target and target in items:
            item = items[target]
            if item["superseded_by"] is None:
                item["evidence_count"] += 1
                item["last_reinforced_at"] = ts
                if src not in item["source_event_ids"]:
                    item["source_event_ids"].append(src)
                if hw:
                    item["confirmed"] = True

        elif op_type == "SUPERSEDE" and target and target in items:
            items[target]["superseded_by"] = item_id
            items[item_id] = {
                "id": item_id, "operator_id": operator_id,
                "text": row["text"], "value": row["value"], "category": row["category"],
                "evidence_count": 1, "source_event_ids": [src],
                "created_at": ts, "last_reinforced_at": ts,
                "superseded_by": None, "confirmed": hw,
            }

    active: list[MemoryItem] = []
    for state in items.values():
        if state["superseded_by"] is not None:
            continue
        category = TraitCategory(state["category"]) if state["category"] else None
        if category is None:
            continue
        status = assign_status(state["evidence_count"], state["confirmed"])
        active.append(
            MemoryItem(
                id=state["id"], operator_id=operator_id,
                text=state["text"], value=state["value"], category=category, status=status,
                evidence_count=state["evidence_count"],
                source_event_ids=state["source_event_ids"],
                created_at=datetime.fromisoformat(state["created_at"]),
                last_reinforced_at=datetime.fromisoformat(state["last_reinforced_at"]),
                superseded_by=state["superseded_by"],
            )
        )

    return OperatorProfile(operator_id=operator_id, active_items=active)


# ── Synopsis (delegates to memory.synopsis) ───────────────────────────────────

def get_synopsis(operator_id: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    from ola.memory.synopsis import get_synopsis as _get
    return _get(operator_id, db_path=db_path)


def save_synopsis(operator_id: str, text: str, db_path: str = DB_PATH) -> None:
    from ola.memory.synopsis import save_synopsis as _save
    _save(operator_id, text, db_path=db_path)


# ── Conformance ───────────────────────────────────────────────────────────────

def append_conformance_event(
    event_id: str,
    source_event_id: str,
    operator_id: str,
    alarm_code: str | None,
    procedure_id: str | None,
    expected_disposition: str | None,
    db_path: str = DB_PATH,
) -> None:
    from datetime import timedelta
    review_due = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    conn = _connect(db_path)
    conn.execute(
        """INSERT OR IGNORE INTO conformance_events
           (id, source_event_id, operator_id, alarm_code, procedure_id,
            expected_disposition, review_due_at)
           VALUES (?,?,?,?,?,?,?)""",
        (event_id, source_event_id, operator_id, alarm_code, procedure_id,
         expected_disposition, review_due),
    )
    conn.commit()
    conn.close()


def get_pending_conformance_events(operator_id: str, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM conformance_events WHERE operator_id = ? AND outcome_status = 'pending'",
        (operator_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_conformance_event(
    event_id: str,
    conformance: str,
    observed_action: str,
    outcome_quality: str,
    quadrant: str,
    db_path: str = DB_PATH,
) -> None:
    conn = _connect(db_path)
    conn.execute(
        """UPDATE conformance_events SET
             conformance=?, observed_action=?, outcome_quality=?,
             quadrant=?, outcome_status='resolved'
           WHERE id=?""",
        (conformance, observed_action, outcome_quality, quadrant, event_id),
    )
    conn.commit()
    conn.close()


# ── Hypotheses ────────────────────────────────────────────────────────────────

def append_hypothesis(h: Hypothesis, db_path: str = DB_PATH) -> None:
    conn = _connect(db_path)
    conn.execute(
        """INSERT OR IGNORE INTO hypotheses
           (id, operator_id, kind, description, evidence_count, status, source_event_ids, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            h.id, h.operator_id, h.kind, h.description, h.evidence_count, h.status,
            json.dumps(h.source_event_ids), h.created_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


# ── Reset (demo utility) ──────────────────────────────────────────────────────

def reset_operator(operator_id: str, db_path: str = DB_PATH) -> None:
    """Delete all learned state. Does not touch domain KG or persona."""
    conn = _connect(db_path)
    for table in ("signals", "memory_operations", "conformance_events", "hypotheses"):
        conn.execute(f"DELETE FROM {table} WHERE operator_id = ?", (operator_id,))  # noqa: S608
    conn.execute("DELETE FROM events WHERE operator_id = ?", (operator_id,))
    conn.execute("DELETE FROM sessions WHERE operator_id = ?", (operator_id,))
    conn.execute("DELETE FROM operator_synopsis WHERE operator_id = ?", (operator_id,))
    conn.commit()
    conn.close()
