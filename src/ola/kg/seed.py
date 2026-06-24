"""
KG seeding — apply schema constraints and Wave-1 domain data.
Uses MERGE throughout so it is safe to run repeatedly.
"""

from __future__ import annotations

from pathlib import Path

from ola.kg.client import get_driver, run_query

_REPO   = Path(__file__).parent.parent.parent.parent  # src/ola/kg -> src/ola -> src -> repo root
_SCHEMA = _REPO / "data" / "kg" / "schema.cypher"
_SEED   = _REPO / "data" / "kg" / "seed.cypher"


def is_seeded() -> bool:
    """Return True if Wave-1 domain data is already present."""
    rows = run_query("MATCH (n:MachineType) RETURN count(n) AS c")
    return bool(rows) and rows[0].get("c", 0) > 0


def _run_cypher_file(path: Path) -> int:
    """Execute a .cypher file statement-by-statement. Returns number of statements run."""
    driver = get_driver()
    if driver is None:
        raise RuntimeError("Neo4j is unavailable — cannot apply " + path.name)

    # Strip comment lines FIRST so semicolons inside comments don't split statements.
    code_lines = [
        line for line in path.read_text().splitlines()
        if not line.strip().startswith("//")
    ]
    code = "\n".join(code_lines)

    statements = [s.strip() for s in code.split(";") if s.strip()]

    run_count = 0
    with driver.session() as session:
        for stmt in statements:
            session.run(stmt)
            run_count += 1

    return run_count


def apply_schema() -> None:
    n = _run_cypher_file(_SCHEMA)
    print(f"  schema: {n} statement(s) applied")


def apply_seed() -> None:
    if is_seeded():
        print("  seed: already seeded — skipped")
        return
    n = _run_cypher_file(_SEED)
    print(f"  seed: {n} statement(s) applied")
