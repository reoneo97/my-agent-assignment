from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from ola.config import DB_PATH
from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryItem, MemoryOperation, OperatorProfile
from ola.domain.signals import TraitCategory
from ola.memory.tiers import assign_status

_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    shift TEXT,
    event_type TEXT NOT NULL,
    alarm_code TEXT,
    raw_text TEXT NOT NULL,
    outcome TEXT
)
"""

_CREATE_MEMORY_OPS = """
CREATE TABLE IF NOT EXISTS memory_operations (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    op_type TEXT NOT NULL,
    target_item_id TEXT,
    text TEXT,
    category TEXT,
    source_event_id TEXT NOT NULL,
    timestamp TEXT NOT NULL
)
"""


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_CREATE_EVENTS)
    conn.execute(_CREATE_MEMORY_OPS)
    conn.commit()
    return conn


def append_event(interaction: OperatorInteraction, db_path: str = DB_PATH) -> None:
    conn = _connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?)",
        (
            interaction.id,
            interaction.operator_id,
            interaction.timestamp.isoformat(),
            interaction.shift,
            interaction.event_type,
            interaction.alarm_code,
            interaction.raw_text,
            interaction.outcome,
        ),
    )
    conn.commit()
    conn.close()


def append_operation(op: MemoryOperation, db_path: str = DB_PATH) -> None:
    conn = _connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO memory_operations VALUES (?,?,?,?,?,?,?,?)",
        (
            op.id,
            op.operator_id,
            op.op_type,
            op.target_item_id,
            op.text,
            op.category.value if op.category else None,
            op.source_event_id,
            op.timestamp.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_profile(operator_id: str, db_path: str = DB_PATH) -> OperatorProfile:
    """Fold the memory_operations log into the current active profile.

    Deterministic: given the same log rows in insertion order, always produces
    the same profile. The profile is fully reconstructable from the log alone.
    """
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM memory_operations WHERE operator_id = ? ORDER BY timestamp ASC",
        (operator_id,),
    ).fetchall()
    conn.close()

    # item_id -> mutable state dict during fold
    items: dict[str, dict[str, Any]] = {}

    for row in rows:
        op_type = row["op_type"]
        item_id = row["id"]  # each op row's own id serves as the item id for ADD
        target = row["target_item_id"]
        ts = row["timestamp"]
        src = row["source_event_id"]

        if op_type == "ADD":
            items[item_id] = {
                "id": item_id,
                "operator_id": operator_id,
                "text": row["text"],
                "category": row["category"],
                "status": "tentative",
                "evidence_count": 1,
                "source_event_ids": [src],
                "created_at": ts,
                "last_reinforced_at": ts,
                "superseded_by": None,
                "confirmed": False,
            }

        elif op_type == "REINFORCE" and target and target in items:
            item = items[target]
            if item["superseded_by"] is None:  # only reinforce active items
                item["evidence_count"] += 1
                item["last_reinforced_at"] = ts
                if src not in item["source_event_ids"]:
                    item["source_event_ids"].append(src)

        elif op_type == "SUPERSEDE" and target and target in items:
            items[target]["superseded_by"] = item_id  # old item points to replacement
            # new item created by this same op
            items[item_id] = {
                "id": item_id,
                "operator_id": operator_id,
                "text": row["text"],
                "category": row["category"],
                "status": "tentative",
                "evidence_count": 1,
                "source_event_ids": [src],
                "created_at": ts,
                "last_reinforced_at": ts,
                "superseded_by": None,
                "confirmed": False,
            }

        # NOOP: no state change

    # Derive status from code rule for each item
    active: list[MemoryItem] = []
    for state in items.values():
        status = (
            "superseded"
            if state["superseded_by"] is not None
            else assign_status(state["evidence_count"], state["confirmed"])
        )
        if status == "superseded":
            continue
        category = TraitCategory(state["category"]) if state["category"] else None
        if category is None:
            continue
        active.append(
            MemoryItem(
                id=state["id"],
                operator_id=operator_id,
                text=state["text"],
                category=category,
                status=status,
                evidence_count=state["evidence_count"],
                source_event_ids=state["source_event_ids"],
                created_at=datetime.fromisoformat(state["created_at"]),
                last_reinforced_at=datetime.fromisoformat(state["last_reinforced_at"]),
                superseded_by=state["superseded_by"],
            )
        )

    return OperatorProfile(operator_id=operator_id, active_items=active)
