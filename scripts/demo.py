#!/usr/bin/env python3
"""
Demo driver: run the persona simulator for N interactions,
print operations, evolving profile, and personalized response after each step.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

# Allow running from the repo root without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ola.pipeline import process_interaction
from sim.persona import simulate_interactions

_SEP = "─" * 70


def _print_profile(profile) -> None:  # type: ignore[no-untyped-def]
    if not profile.active_items:
        print("  (profile empty)")
        return
    for item in profile.active_items:
        caution = " ← confirm!" if item.status == "tentative" else ""
        print(
            f"  [{item.status:12s}] (n={item.evidence_count}) "
            f"[{item.category.value}] {item.text}{caution}"
        )


async def run_demo(n: int = 10, db_path: str | None = None) -> None:
    print(_SEP)
    print(" OPERATOR LEARNING ASSISTANT — Stage 1 Demo")
    print(_SEP)

    interaction_num = 0
    async for interaction in simulate_interactions(n):
        interaction_num += 1
        print(f"\n{'=' * 70}")
        print(f"  Interaction {interaction_num}/{n}")
        print(f"  [{interaction.shift}] {interaction.event_type.upper()}"
              + (f" ({interaction.alarm_code})" if interaction.alarm_code else ""))
        print(f"  {interaction.raw_text}")
        print()

        ops, profile, response = await process_interaction(interaction, db_path=db_path)

        # Memory operations
        print("  Memory Operations:")
        if not ops:
            print("    (none)")
        for op in ops:
            if op.op_type == "NOOP":
                print(f"    NOOP")
            elif op.op_type == "ADD":
                print(f"    ADD  [{op.category.value if op.category else '?'}] \"{op.text}\"")
            elif op.op_type == "REINFORCE":
                print(f"    REINFORCE -> {op.target_item_id}")
            elif op.op_type == "SUPERSEDE":
                print(f"    SUPERSEDE {op.target_item_id} -> [{op.category.value if op.category else '?'}] \"{op.text}\"")

        print()
        print("  Current Profile:")
        _print_profile(profile)

        print()
        print("  Personalized Response:")
        for line in response.strip().splitlines():
            print(f"    {line}")
        print()


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    db_path = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(run_demo(n, db_path))


if __name__ == "__main__":
    main()
