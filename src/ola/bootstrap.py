"""
OLA Bootstrap — idempotent, importable, testable.

Orchestrates:
  1. Neo4j schema (constraints + indexes)
  2. Wave-1 KG seed data
  3. Manual Extractor on data/manuals/ (skipped if procedures already exist)

Idempotency contract:
  - Schema uses IF NOT EXISTS — always safe.
  - Seed checks for existing MachineType nodes and skips if present.
  - Manual Extractor checks for existing Procedure nodes and skips if present.
  - Safe to re-run on every container start; only pays LLM cost on a fresh graph.

Entry points:
  python -m ola.bootstrap                                          # module
  from ola.bootstrap import run_initialization; await run_initialization()
"""

from __future__ import annotations

import asyncio
from pathlib import Path

_REPO        = Path(__file__).parent.parent.parent  # src/ola -> src -> repo root
_MANUALS_DIR = _REPO / "data" / "manuals"


def _procedures_exist() -> bool:
    from ola.kg.client import run_query
    rows = run_query("MATCH (p:Procedure) RETURN count(p) AS c")
    return bool(rows) and rows[0].get("c", 0) > 0


async def _run_manual_extractor(manuals_dir: Path) -> None:
    from ola.agents.manual_extractor import apply_kg_draft, extract_from_manual

    if _procedures_exist():
        print("  manuals: procedures already in graph — skipped")
        return

    files = sorted(manuals_dir.glob("*.md")) + sorted(manuals_dir.glob("*.txt"))
    if not files:
        print(f"  manuals: no files found in {manuals_dir} — skipped")
        return

    for f in files:
        print(f"  manuals: extracting {f.name} …", end=" ", flush=True)
        try:
            draft = await extract_from_manual(f.read_text(), source_name=f.stem)
            summary = await apply_kg_draft(draft)
            print(f"nodes={summary['nodes_written']} edges={summary['edges_written']} procedures={summary['procedures']}")
        except Exception as exc:
            print(f"ERROR — {exc}")


async def run_initialization(manuals_dir: Path | None = None) -> None:
    """Idempotent bootstrap. Neo4j must be reachable before calling."""
    from ola.kg.seed import apply_schema, apply_seed

    print("── OLA Bootstrap ─────────────────────")
    print("1. KG schema …")
    apply_schema()

    print("2. KG seed …")
    apply_seed()

    print("3. Manual Extractor …")
    await _run_manual_extractor(manuals_dir or _MANUALS_DIR)

    print("── Bootstrap complete ────────────────")


if __name__ == "__main__":
    asyncio.run(run_initialization())
