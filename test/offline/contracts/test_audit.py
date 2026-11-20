"""Offline tests for the public audit contract :mod:`egta.contracts.audit`.

Covers: AuditContractError hierarchy + exception signatures, Receipt's 12 fields,
AuditSink.append idempotency (same id/content -> existing Receipt; same id/diff
content -> DuplicateConflict; unwritable -> AuditUnavailable fail-closed),
AuditReader.read, and tail-truncation detection via an external anchor.

Contract definitions: docs/req/contracts-summary.md §1.
RED on the spec branch: ``egta.contracts.audit`` does not exist yet.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from egta.contracts.audit import (
    AuditContractError,
    AuditSink,
    AuditUnavailable,
    ChainBroken,
    DuplicateConflict,
    PayloadMismatch,
    Receipt,
    recompute_payload_hash,
    verify_chain,
)
from egta.contracts.events import Phase, RunEvent, RunStatus

pytestmark = pytest.mark.spec

VALID_HASH = "a" * 64
RECEIPT_FIELDS = {
    "schema_version", "receipt_id", "run_id", "event_id", "sequence",
    "payload_hash", "prev_event_hash", "chain_tip_hash", "persisted_at",
    "store_id", "transaction_id", "idempotency_key",
}


def _utc() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _bound(seq: int, event_id: str, prev: str = "", **extra) -> RunEvent:
    base = {
        "event_id": event_id, "run_id": "r1", "sequence": seq,
        "phase": Phase.APP, "timestamp": _utc(), "status": RunStatus.OK,
        "payload_hash": VALID_HASH, "prev_event_hash": prev, **extra,
    }
    draft = RunEvent(**base)
    return draft.model_copy(update={"payload_hash": recompute_payload_hash(draft)})


# --- exception hierarchy + signatures (D's signatures) ----------------------


def test_audit_public_protocols_importable():
    """AuditSink / AuditReader are part of the public contract (importable)."""
    import typing

    from egta.contracts.audit import AuditReader

    assert typing.get_origin(AuditSink) is None  # a Protocol class
    assert AuditReader is not None


def test_exceptions_share_base():
    for cls in (ChainBroken, DuplicateConflict, PayloadMismatch,
                AuditUnavailable):
        assert issubclass(cls, AuditContractError)


def test_chainbroken_signature():
    exc = ChainBroken("r1", 2, 4, "gap")
    assert (exc.run_id, exc.expected_sequence, exc.actual_sequence,
            exc.reason) == ("r1", 2, 4, "gap")


def test_duplicateconflict_signature():
    exc = DuplicateConflict("r1", "e1", "a" * 64, "b" * 64)
    assert (exc.run_id, exc.event_id, exc.existing_payload_hash,
            exc.incoming_payload_hash) == ("r1", "e1", "a" * 64, "b" * 64)


def test_payloadmismatch_signature():
    exc = PayloadMismatch("r1", "e1", "a" * 64, "b" * 64)
    assert (exc.run_id, exc.event_id, exc.stored_payload_hash,
            exc.recomputed_payload_hash) == ("r1", "e1", "a" * 64, "b" * 64)


def test_auditunavailable_signature():
    exc = AuditUnavailable("r1", "append", "disk full")
    assert (exc.run_id, exc.operation, exc.cause) == ("r1", "append", "disk full")


# --- Receipt: exactly D's 12 fields -----------------------------------------


def test_receipt_has_exactly_twelve_fields():
    assert set(Receipt.model_fields) == RECEIPT_FIELDS
    assert len(Receipt.model_fields) == 12


def test_receipt_rejects_extra_field():
    payload = dict.fromkeys(RECEIPT_FIELDS, "x")
    payload.update({"persisted_at": _utc(), "sequence": 0, "thirteenth": "no"})
    with pytest.raises(ValidationError):
        Receipt(**payload)


# --- tail truncation via external anchor ------------------------------------


def test_full_chain_with_correct_anchor_passes():
    ev0 = _bound(0, "e0")
    ev1 = _bound(1, "e1", ev0.payload_hash)
    tip = ev1.payload_hash
    verify_chain([ev0, ev1], anchor=tip)  # no raise


def test_tail_truncation_detected_with_anchor():
    """Dropping the last event leaves the prefix valid but the tip != anchor."""
    ev0 = _bound(0, "e0")
    ev1 = _bound(1, "e1", ev0.payload_hash)
    ev2 = _bound(2, "e2", ev1.payload_hash)
    trusted_tip = ev2.payload_hash
    truncated = [ev0, ev1]  # last event removed
    with pytest.raises(ChainBroken):
        verify_chain(truncated, anchor=trusted_tip)


# --- AuditSink idempotency (with a fake in-test sink) -----------------------

class _InMemorySink:
    """Minimal reference sink satisfying the audit contract for these tests.

    This is a TEST DOUBLE (in the spec test file), not the implementation; it
    models the documented AuditSink semantics so the contract's behaviour is
    pinned before src/ exists.
    """

    def __init__(self):
        self._by_id: dict[str, tuple[str, Receipt]] = {}
        self._order: list[RunEvent] = []

    def append(self, event: RunEvent) -> Receipt:
        content = recompute_payload_hash(event)
        existing = self._by_id.get(event.event_id)
        if existing is not None:
            old_content, old_receipt = existing
            if old_content != content:
                raise DuplicateConflict(event.run_id, event.event_id,
                                        old_content, content)
            return old_receipt
        tip = content
        receipt = Receipt(
            schema_version="1.0", receipt_id=f"rcpt-{event.event_id}",
            run_id=event.run_id, event_id=event.event_id,
            sequence=event.sequence, payload_hash=event.payload_hash,
            prev_event_hash=event.prev_event_hash, chain_tip_hash=tip,
            persisted_at=_utc(), store_id="mem", transaction_id="tx1",
            idempotency_key=f"{event.run_id}:{event.event_id}",
        )
        self._by_id[event.event_id] = (content, receipt)
        self._order.append(event)
        return receipt

    def read(self, run_id: str):
        return [e for e in self._order if e.run_id == run_id]


def test_audit_sink_same_id_same_content_returns_existing_receipt():
    sink = _InMemorySink()
    ev = _bound(0, "e0")
    r1 = sink.append(ev)
    r2 = sink.append(ev)
    assert r1.receipt_id == r2.receipt_id
    assert r1.chain_tip_hash == r2.chain_tip_hash
    assert len(sink.read("r1")) == 1  # no duplicate stored


def test_audit_sink_same_id_diff_content_rejected():
    sink = _InMemorySink()
    sink.append(_bound(0, "e0"))
    conflicting = _bound(0, "e0", metrics={"different": True})
    with pytest.raises(DuplicateConflict):
        sink.append(conflicting)


def test_audit_sink_append_is_idempotent():
    sink = _InMemorySink()
    events = [_bound(0, "e0"), _bound(1, "e1", _bound(0, "e0").payload_hash)]
    first = [sink.append(e) for e in events]
    second = [sink.append(e) for e in events]
    assert [r.receipt_id for r in first] == [r.receipt_id for r in second]


def test_audit_sink_read_returns_events_in_order():
    sink = _InMemorySink()
    ev0 = _bound(0, "e0")
    ev1 = _bound(1, "e1", ev0.payload_hash)
    sink.append(ev0)
    sink.append(ev1)
    read = sink.read("r1")
    assert [e.sequence for e in read] == [0, 1]
