"""
Manual Extractor — build-time, strong model.
Parses a procedure manual (plain text) and produces:
  - A KGDraft: structured nodes + edges (source=MANUAL)
  - Procedure content records (prose payload, indexed by procedure_id)
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_strong_model, STRONG_SETTINGS
from ola.telemetry import traced_agent


class KGNode(BaseModel):
    label: str          # e.g. "AlarmCode", "Procedure", "ProcedureStep"
    properties: dict    # e.g. {"code": "PA-2201", "severity": "medium"}


class KGEdge(BaseModel):
    from_label: str
    from_key: str       # property name used to match the from-node
    from_value: str
    rel_type: str       # e.g. "RESOLVED_BY"
    to_label: str
    to_key: str
    to_value: str
    properties: dict = {}


class ProcedureContent(BaseModel):
    procedure_id: str
    title: str
    prose: str          # full procedure text for retrieval
    steps: list[str]    # ordered step texts


class KGDraft(BaseModel):
    nodes: list[KGNode]
    edges: list[KGEdge]
    procedure_contents: list[ProcedureContent]


_agent: Agent[None, KGDraft] = Agent(
    make_strong_model(),
    name="manual_extractor",
    output_type=KGDraft,
    retries=3,
    model_settings=STRONG_SETTINGS,
    system_prompt="""\
You are extracting structured knowledge from a manufacturing procedure manual.
Given the manual text, produce:
1. KG nodes: AlarmCode, Procedure, ProcedureStep, Skill, MachineType nodes mentioned.
2. KG edges: RESOLVED_BY, HAS_STEP, REQUIRES_SKILL, OCCURS_ON_TYPE relationships.
3. Procedure contents: full prose and ordered steps for each procedure.

Rules:
- Only extract facts explicitly stated in the manual.
- AlarmCode properties: code (e.g. PA-2201), severity (low/medium/high),
  complexity (low/medium/high), category (mechanical/process/sensor/recipe),
  expected_disposition (SELF_RESOLVE/ESCALATE/EITHER).
- Procedure IDs: derive from alarm code, e.g. "PROC-PA-2201-RESET".
- Step IDs: PROC-ID-S1, PROC-ID-S2, etc.
- Do not invent facts not in the text.
""",
)


@traced_agent(name="manual-extractor")
async def extract_from_manual(manual_text: str, source_name: str = "manual") -> KGDraft:
    prompt = f"Manual source: {source_name}\n\n---\n{manual_text}\n---\n\nExtract KG nodes, edges, and procedure contents."
    result = await _agent.run(prompt)
    return result.output


async def apply_kg_draft(draft: KGDraft) -> dict:
    """
    Apply the extracted KGDraft to Neo4j.
    Returns summary of what was written.
    """
    from ola.kg.client import run_write

    nodes_written = 0
    edges_written = 0

    for node in draft.nodes:
        props_str = ", ".join(f"n.{k} = ${k}" for k in node.properties)
        match_key = next(iter(node.properties))
        run_write(
            f"MERGE (n:{node.label} {{{match_key}: $match_val}}) SET {props_str}, n.source = 'MANUAL'",
            {"match_val": node.properties[match_key], **node.properties},
        )
        nodes_written += 1

    for edge in draft.edges:
        run_write(
            f"""
            MERGE (a:{edge.from_label} {{{edge.from_key}: $from_val}})
            MERGE (b:{edge.to_label} {{{edge.to_key}: $to_val}})
            MERGE (a)-[r:{edge.rel_type}]->(b)
            SET r += $props, r.source = 'MANUAL'
            """,
            {"from_val": edge.from_value, "to_val": edge.to_value, "props": edge.properties},
        )
        edges_written += 1

    return {
        "nodes_written": nodes_written,
        "edges_written": edges_written,
        "procedures": len(draft.procedure_contents),
    }
