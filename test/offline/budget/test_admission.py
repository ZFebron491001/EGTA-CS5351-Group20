"""Offline spec for FR-02 / INV-03 admission — governor-layer (concurrency only).

This file keeps ONE genuine governor test: the concurrency no-oversell check, which
reaches the governor through the frozen ``reserve`` entry and asserts the exact
admission outcomes.

Why only this test lives here: the structured-fallback, tool-binding and
send-then-interrupt cases need a unified gateway entry that lets the TESTED code
itself trigger the send, the fallback, and the admission, so that a budget bypass in
the project's real path is caught. No such gateway entry exists yet (there is no
``src/egta/budget/`` and no injectable model gateway on ``main``). Writing those
cases with a test-built entry or with the test calling ``reserve`` by hand would let a
real bypass pass green, so they are NOT written here; they are listed as
"pending gateway wiring" acceptance items in
``docs/req/trace-FR-02-admission.md``.

Frozen entry point (§5.1):

    BudgetGovernor.reserve(call_spec) -> Reservation | BudgetDenied

RED by design: ``egta.budget`` is absent on this branch, so the test fails when it
calls ``governor_factory()`` (lazy import), not at collection. No fake governor.
"""

from __future__ import annotations

import threading

import pytest
from fakes import ONE_CALL_ASK, ONE_CALL_LIMITS

pytestmark = pytest.mark.spec


def _is_denied(result) -> bool:
    from egta.budget import BudgetDenied

    return isinstance(result, BudgetDenied)


def _is_reservation(result) -> bool:
    from egta.budget import Reservation

    return isinstance(result, Reservation)


# ---------------------------------------------------------------------------
# Concurrency: room for exactly one call slot; two valid calls race.
# Chain: the test starts two threads (barrier) that each call ``gov.reserve``;
# the governor's own lock decides. Observed: exactly one Reservation and one
# BudgetDenied. There is no transport here — this is a pure governor assertion,
# so no "transport received" claim is made.
# ---------------------------------------------------------------------------


def test_two_concurrent_calls_do_not_oversell_one_slot(governor_factory):
    gov = governor_factory(limits=ONE_CALL_LIMITS).governor

    barrier = threading.Barrier(2)
    results: list[object] = []
    lock = threading.Lock()

    def _attempt():
        barrier.wait(timeout=5)  # both start together; a hang fails, not hangs
        r = gov.reserve(ONE_CALL_ASK)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=_attempt, daemon=True) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive(), "a worker thread hung; the concurrency test cannot prove anything"

    assert len(results) == 2, "both calls must have entered the admission process"
    granted = [r for r in results if _is_reservation(r)]
    denied = [r for r in results if _is_denied(r)]
    assert len(granted) == 1, "exactly one call is granted (no over-sell)"
    assert len(denied) == 1, "the other call is refused with BudgetDenied"
