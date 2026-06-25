from __future__ import annotations

from typing import Any

from ola.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

_driver = None


def get_driver():  # type: ignore[return]
    """Return a lazily-initialised Neo4j driver. Returns None if Neo4j is unavailable."""
    global _driver
    if _driver is not None:
        return _driver
    try:
        from neo4j import GraphDatabase  # type: ignore[import]
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
    except Exception:
        # Don't cache a driver that failed to verify — retry on next call
        # instead of permanently returning a dead driver to every caller.
        return None
    _driver = driver
    return _driver


def run_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a read query. Returns [] if Neo4j is unavailable."""
    driver = get_driver()
    if driver is None:
        return []
    with driver.session() as session:
        result = session.run(cypher, params or {})
        return [dict(record) for record in result]


def run_write(cypher: str, params: dict[str, Any] | None = None) -> None:
    """Execute a write query. No-ops if Neo4j is unavailable."""
    driver = get_driver()
    if driver is None:
        return
    with driver.session() as session:
        session.run(cypher, params or {})
