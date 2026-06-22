"""Pure unit tests for the tier rule — no network, no LLM."""

import pytest
from ola.memory.tiers import assign_status


def test_tentative_below_threshold():
    assert assign_status(0) == "tentative"
    assert assign_status(1) == "tentative"
    assert assign_status(2) == "tentative"


def test_established_at_threshold():
    assert assign_status(3) == "established"
    assert assign_status(10) == "established"


def test_confirmed_overrides_count():
    assert assign_status(1, confirmed=True) == "confirmed"
    assert assign_status(0, confirmed=True) == "confirmed"
    assert assign_status(5, confirmed=True) == "confirmed"
