"""
All Cypher queries in one place. Each function returns structured Python dicts.
Gracefully returns empty results if Neo4j is unavailable.
"""

from __future__ import annotations

from typing import Any, Literal

from ola.kg.client import run_query


def get_alarm_context(alarm_code: str) -> dict[str, Any]:
    """Procedure, disposition, modalities, skills, and sibling alarms for an alarm code."""
    rows = run_query(
        """
        MATCH (a:AlarmCode {code: $code})
        OPTIONAL MATCH (a)-[:RESOLVED_BY]->(p:Procedure)
        OPTIONAL MATCH (p)-[:AVAILABLE_IN]->(m:Modality)
        OPTIONAL MATCH (p)-[:REQUIRES_SKILL]->(s:Skill)
        OPTIONAL MATCH (a)-[:RELATED_TO]->(sib:AlarmCode)
        RETURN
            a.expected_disposition AS expected_disposition,
            a.complexity           AS complexity,
            a.severity             AS severity,
            a.category             AS alarm_category,
            p.id                   AS procedure_id,
            p.title                AS procedure_title,
            collect(DISTINCT m.name) AS modalities,
            collect(DISTINCT s.name) AS skills,
            collect(DISTINCT sib.code) AS related_alarms
        """,
        {"code": alarm_code},
    )
    if not rows:
        return {}
    r = rows[0]
    return {
        "expected_disposition": r.get("expected_disposition"),
        "complexity": r.get("complexity"),
        "severity": r.get("severity"),
        "alarm_category": r.get("alarm_category"),
        "procedure_id": r.get("procedure_id"),
        "procedure_title": r.get("procedure_title"),
        "modalities": r.get("modalities") or [],
        "skills": r.get("skills") or [],
        "related_alarms": r.get("related_alarms") or [],
    }


def get_operator_confidence_transfer(operator_id: str, alarm_code: str) -> float | None:
    """
    Check if the operator has CONFIDENT_WITH on a sibling alarm via RELATED_TO.
    Returns confidence value or None if no transfer applies.
    """
    rows = run_query(
        """
        MATCH (:Operator {id: $op})-[c:CONFIDENT_WITH]->(:AlarmCode)-[:RELATED_TO]->(target:AlarmCode {code: $code})
        RETURN c.confidence AS confidence
        LIMIT 1
        """,
        {"op": operator_id, "code": alarm_code},
    )
    return rows[0]["confidence"] if rows else None


def get_escalation_candidates(alarm_code: str, current_shift: str, exclude_operator: str) -> list[dict[str, Any]]:
    """Find operators with the skill to resolve this alarm on the current shift."""
    return run_query(
        """
        MATCH (a:AlarmCode {code: $code})-[:RESOLVED_BY]->(:Procedure)-[:REQUIRES_SKILL]->(s:Skill)
        MATCH (expert:Operator)-[:CERTIFIED_FOR]->(s)
        WHERE expert.shift = $shift AND expert.id <> $exclude
        RETURN DISTINCT expert.id AS id, expert.name AS name, s.name AS skill
        """,
        {"code": alarm_code, "shift": current_shift, "exclude": exclude_operator},
    )


def list_alarm_codes(machine_type: str | None = None) -> list[dict[str, Any]]:
    """All AlarmCodes, optionally filtered to those occurring on a given MachineType."""
    if machine_type:
        return run_query(
            """
            MATCH (a:AlarmCode)-[:OCCURS_ON_TYPE]->(:MachineType {name: $mt})
            RETURN a.code AS code, a.complexity AS complexity, a.severity AS severity,
                   a.category AS category, a.expected_disposition AS expected_disposition
            """,
            {"mt": machine_type},
        )
    return run_query(
        """
        MATCH (a:AlarmCode)
        RETURN a.code AS code, a.complexity AS complexity, a.severity AS severity,
               a.category AS category, a.expected_disposition AS expected_disposition
        """
    )


def list_machines(machine_type: str) -> list[str]:
    """Machine ids of a given MachineType."""
    rows = run_query(
        "MATCH (m:Machine)-[:OF_TYPE]->(:MachineType {name: $mt}) RETURN m.id AS id",
        {"mt": machine_type},
    )
    return [r["id"] for r in rows]


def get_operator_alarm_disposition(
    operator_id: str, alarm_code: str
) -> Literal["confident", "struggles", "unknown"]:
    """Direct CONFIDENT_WITH/STRUGGLES_WITH edge on this exact alarm code (not sibling transfer)."""
    rows = run_query(
        """
        MATCH (:Operator {id: $op})-[r:CONFIDENT_WITH|STRUGGLES_WITH]->(:AlarmCode {code: $code})
        RETURN type(r) AS rel_type
        LIMIT 1
        """,
        {"op": operator_id, "code": alarm_code},
    )
    if not rows:
        return "unknown"
    return "confident" if rows[0]["rel_type"] == "CONFIDENT_WITH" else "struggles"


def get_operator_learned_edges(operator_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return all Wave-2 learned edges for an operator."""
    prefers = run_query(
        "MATCH (:Operator {id:$op})-[r:PREFERS]->(m:Modality) RETURN m.name AS name, r.evidence_count AS n",
        {"op": operator_id},
    )
    confident = run_query(
        "MATCH (:Operator {id:$op})-[r:CONFIDENT_WITH]->(a:AlarmCode) RETURN a.code AS code, r.evidence_count AS n",
        {"op": operator_id},
    )
    struggles = run_query(
        "MATCH (:Operator {id:$op})-[r:STRUGGLES_WITH]->(a:AlarmCode) RETURN a.code AS code, r.evidence_count AS n",
        {"op": operator_id},
    )
    return {"prefers": prefers, "confident_with": confident, "struggles_with": struggles}
