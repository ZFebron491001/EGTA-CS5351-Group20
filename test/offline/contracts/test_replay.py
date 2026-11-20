"""Offline tests for replay determinism :mod:`egta.contracts.evaluation` (replay).

Replay reconstructs a run's recorded state/metrics from its event log ordered by
``(run_id, sequence)`` and deduped by ``event_id``. It must be deterministic and
fully offline (no LLM/network).

Contract definitions: docs/req/contracts-summary.md. RED on spec branch.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from egta.contracts.audit import recompute_payload_hash
from egta.contracts.evaluation import replay_events
from egta.contracts.events import Phase, RunEvent, RunStatus

pytestmark = pytest.mark.spec

VALID_HASH = "a" * 64


def _utc() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _bound(seq: int, event_id: str, prev: str = "", **extra) -> RunEvent:
    base = {
        "event_id": event_id, "run_id": "r1", "sequence": seq,
        "phase": Phase.EVIDENCE, "timestamp": _utc(), "status": RunStatus.OK,
        "payload_hash": VALID_HASH, "prev_event_hash": prev, **extra,
    }
    draft = RunEvent(**base)
    return draft.model_copy(update={"payload_hash": recompute_payload_hash(draft)})


def _log():
    ev0 = _bound(0, "e0", metrics={"tokens": 10, "a": 1, "b": 2})
    ev1 = _bound(1, "e1", ev0.payload_hash, metrics={"tokens": 5})
    return [ev0, ev1]


def test_replay_is_deterministic():
    log = _log()
    state1 = replay_events(log)
    state2 = replay_events(log)
    assert state1 == state2


def test_replay_is_independent_of_input_order():
    """Replay must order by (run_id, sequence), not list position."""
    ev0 = _bound(0, "e0", metrics={"tokens": 10})
    ev1 = _bound(1, "e1", ev0.payload_hash, metrics={"tokens": 5})
    assert replay_events([ev0, ev1]) == replay_events([ev1, ev0])


def test_replay_is_offline_no_llm(monkeypatch):
    """Replay must not touch any model/network. Poison common entry points."""
    import socket

    def _boom(*a, **k):
        raise AssertionError("replay must be offline: network/model touched")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom, raising=False)
    # Should complete purely from the event log.
    assert replay_events(_log()) is not None


def test_replay_dedupes_identical_events_once():
    log = _log()
    doubled = log + [log[0]]  # identical duplicate
    assert replay_events(doubled) == replay_events(log)
