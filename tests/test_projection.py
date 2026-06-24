"""
Unit tests for KG projection gating. No network, no Neo4j required.
Tests that projection is triggered only when an item crosses 'established'.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ola.domain.memory import MemoryItem, OperatorProfile
from ola.domain.signals import TraitCategory
from ola.kg.projection import _infer_edge, project_profile


def _make_item(
    text: str,
    category: TraitCategory,
    status: str = "tentative",
    evidence_count: int = 1,
    item_id: str = "item-001",
    operator_id: str = "op-1",
) -> MemoryItem:
    now = datetime.now(timezone.utc)
    return MemoryItem(
        id=item_id,
        operator_id=operator_id,
        text=text,
        category=category,
        status=status,  # type: ignore[arg-type]
        evidence_count=evidence_count,
        source_event_ids=["evt-1"],
        created_at=now,
        last_reinforced_at=now,
    )


def test_infer_edge_visual_modality() -> None:
    item = _make_item("Prefers visual step-by-step instructions", TraitCategory.INSTRUCTION_MODALITY)
    result = _infer_edge(item)
    assert result is not None
    assert result[0] == "PREFERS"
    assert result[1] == "Modality"
    assert result[2] == "VISUAL"


def test_infer_edge_confident_with_alarm() -> None:
    item = _make_item("Operator is confident resolving PA-2201 independently", TraitCategory.ISSUE_CONFIDENCE)
    result = _infer_edge(item)
    assert result is not None
    assert result[0] == "CONFIDENT_WITH"
    assert result[2] == "PA-2201"


def test_infer_edge_struggles_with_alarm() -> None:
    item = _make_item("Operator struggles with HY-0042 hydraulic faults", TraitCategory.ISSUE_CONFIDENCE)
    result = _infer_edge(item)
    assert result is not None
    assert result[0] == "STRUGGLES_WITH"
    assert result[2] == "HY-0042"


def test_infer_edge_no_match_for_escalation() -> None:
    item = _make_item("Escalates complex faults quickly", TraitCategory.ESCALATION)
    result = _infer_edge(item)
    assert result is None


def test_project_profile_only_newly_established() -> None:
    """project_profile should only write edges for items that newly crossed established."""
    item_already = _make_item("Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY, "established", 4, "item-001")
    item_new = _make_item("Operator confident with PA-2201", TraitCategory.ISSUE_CONFIDENCE, "established", 3, "item-002")

    profile_before = OperatorProfile(operator_id="op-1", active_items=[item_already])
    profile_after = OperatorProfile(operator_id="op-1", active_items=[item_already, item_new])

    with patch("ola.kg.projection.project_item") as mock_project:
        mock_project.return_value = True
        projected = project_profile(profile_after, profile_before)

    # Only the newly-established item should have been projected
    assert len(projected) == 1
    assert "item-002" in projected
    mock_project.assert_called_once()


def test_project_profile_noop_when_nothing_new() -> None:
    item = _make_item("Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY, "established", 4)
    profile = OperatorProfile(operator_id="op-1", active_items=[item])

    with patch("ola.kg.projection.project_item") as mock_project:
        projected = project_profile(profile, profile)

    assert projected == []
    mock_project.assert_not_called()
