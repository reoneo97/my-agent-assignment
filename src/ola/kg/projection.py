"""
Projection — the only path from SQL into the KG's operator-belief edges.
Triggered when a memory item crosses the 'established' tier (code rule).
Deterministic lookup against the KG vocabulary; no LLM.
"""

from __future__ import annotations

from ola.domain.memory import MemoryItem, OperatorProfile
from ola.domain.signals import TraitCategory
from ola.kg.client import run_write

# Canonical mapping from free-text category + value keywords → KG edge type + target label
_MODALITY_KEYWORDS = {"visual", "diagram", "picture", "image", "step-by-step"}
_CONFIDENT_KEYWORDS = {"confident", "resolves independently", "handles", "capable"}
_STRUGGLES_KEYWORDS = {"uncertain", "struggles", "limited", "needs support", "unfamiliar"}


def _infer_edge(item: MemoryItem) -> tuple[str, str, str] | None:
    """
    Returns (edge_type, target_label, target_value) or None if no KG edge applies.
    """
    text = item.text.lower()
    cat = item.category

    if cat == TraitCategory.INSTRUCTION_MODALITY:
        for kw in _MODALITY_KEYWORDS:
            if kw in text:
                # Determine modality name from text
                if "visual" in text or "diagram" in text:
                    return ("PREFERS", "Modality", "VISUAL")
                if "video" in text:
                    return ("PREFERS", "Modality", "VIDEO")
                return ("PREFERS", "Modality", "TEXT")

    if cat == TraitCategory.ISSUE_CONFIDENCE:
        if any(kw in text for kw in _CONFIDENT_KEYWORDS):
            # Try to extract alarm code from text (crude, demo-scale)
            import re
            match = re.search(r"[A-Z]{2,3}-\d{4}", item.text)
            if match:
                return ("CONFIDENT_WITH", "AlarmCode", match.group(0))

        if any(kw in text for kw in _STRUGGLES_KEYWORDS):
            import re
            match = re.search(r"[A-Z]{2,3}-\d{4}", item.text)
            if match:
                return ("STRUGGLES_WITH", "AlarmCode", match.group(0))

    return None


def project_item(item: MemoryItem) -> bool:
    """
    Project one established/confirmed memory item as a KG edge.
    Returns True if an edge was written, False if no mapping found or Neo4j unavailable.
    """
    edge_info = _infer_edge(item)
    if edge_info is None:
        return False

    edge_type, target_label, target_value = edge_info
    prop_key = "name" if target_label == "Modality" else "code"
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    run_write(
        f"""
        MATCH (op:Operator {{id: $op_id}})
        MATCH (target:{target_label} {{{prop_key}: $target_val}})
        MERGE (op)-[r:{edge_type}]->(target)
        SET r.evidence_count = $count,
            r.confidence     = $conf,
            r.last_updated   = $now,
            r.source_item_id = $item_id,
            r.valid_from     = coalesce(r.valid_from, $now)
        """,
        {
            "op_id": item.operator_id,
            "target_val": target_value,
            "count": item.evidence_count,
            "conf": min(1.0, item.evidence_count / 10.0),
            "now": now,
            "item_id": item.id,
        },
    )
    return True


def project_profile(
    profile_after: OperatorProfile,
    profile_before: OperatorProfile,
) -> list[str]:
    """
    Project any items that newly crossed 'established' in this interaction.
    Returns list of projected item IDs.
    """
    before_established = {
        item.id for item in profile_before.active_items
        if item.status in ("established", "confirmed")
    }
    projected: list[str] = []
    for item in profile_after.active_items:
        if item.status in ("established", "confirmed") and item.id not in before_established:
            if project_item(item):
                projected.append(item.id)
    return projected
