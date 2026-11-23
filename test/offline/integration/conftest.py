"""Fixtures for the offline FR-02 gateway / runner INTEGRATION spec.

Separate from ``test/offline/budget/conftest.py`` on purpose: the frozen #22
governor suite (``test/offline/budget`` with ``-m spec``) must keep collecting
exactly its four approved cases, so the gateway and runner integration cases live
under ``test/offline/integration`` instead.

The governor and the adapter are imported lazily inside the fixture body / test
bodies so collection stays green while ``src/egta/budget`` (already merged on main)
and ``src/egta/adapters`` / ``src/egta/app`` (candidate, unbuilt) are absent. A
missing implementation fails only when a TEST CALLS the callable — not at
collection. There is intentionally no ``xfail``/``skip`` for missing code.

Reuses the real ``BudgetGovernor`` (main, #45), the real ``NormalizedChatOpenAI`` +
``httpx.MockTransport`` (fictional key, no network), the real risk gate and the
real audit sink for the runner cases. Only the MODEL is faked.
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
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


@dataclass
class GovernorHarness:
    governor: Any


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch):
    """No real socket connect in the integration spec (MockTransport only)."""

    def _deny(*args, **kwargs):
        raise AssertionError("network access is forbidden in offline integration tests")

    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)


@pytest.fixture
def governor_factory(tmp_path):
    """Return a factory that builds the REAL governor over a temp SQLite DB."""

    def _make(*, limits: dict[str, Any] | None = None) -> GovernorHarness:
        from egta.budget import BudgetGovernor

        if limits is None:
            limits = {"max_total_tokens": 10000, "max_calls": 5, "max_cost_usd": "1.00"}
        governor = BudgetGovernor(limits=limits, db_path=tmp_path / "budget.db")
        return GovernorHarness(governor=governor)

    return _make
