"""Fixtures for the offline FR-02 / INV-03 budget-reservation specification.

The budget implementation is imported lazily inside the ``governor_factory`` body
so that collection works while ``src/egta/budget`` is absent. The ``governor_factory``
fixture itself always succeeds and returns a callable; a missing implementation
fails only when a TEST CALLS that callable (``governor_factory()``), at the lazy
``from egta.budget import BudgetGovernor`` line. Each behavioural case therefore
fails red on its own, at the test's call site, instead of aborting collection.
There is intentionally no ``xfail``/``skip`` for a missing implementation.

The two public entry points this spec pins are the ones frozen in
``execution_plan_261111.md`` §5.1:

    BudgetGovernor.reserve(call_spec) -> Reservation | BudgetDenied
    BudgetGovernor.settle(reservation_id, actual_usage_or_unknown) -> BudgetState

The governor construction below (``BudgetGovernor(limits=..., db_path=...)``) is a
CANDIDATE interface, not a frozen one; it is listed as an open item for B/E in
``docs/req/trace-FR-02-budget-reservation.md``. Nothing in this file is production
code, and nothing here fakes a governor to make a test pass.
"""

from __future__ import annotations

import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fakes import base_limits  # noqa: E402  (test-only builders; see fakes.py)


@dataclass
class GovernorHarness:
    governor: Any


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch):
    def _deny(*args, **kwargs):
        raise AssertionError("network access is forbidden in offline budget tests")

    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)


@pytest.fixture
def governor_factory(tmp_path):
    """Return a factory that builds a governor (candidate construction signature).

    The factory itself never imports ``egta.budget``; the lazy import lives inside
    the returned callable so a test that calls it fails at that call, not here.
    """

    def _make(*, limits: dict[str, Any] | None = None) -> GovernorHarness:
        # Lazy import: collection stays green; the failing test fails at its call.
        from egta.budget import BudgetGovernor

        if limits is None:
            limits = base_limits()
        governor = BudgetGovernor(limits=limits, db_path=tmp_path / "budget.db")
        return GovernorHarness(governor=governor)

    return _make
