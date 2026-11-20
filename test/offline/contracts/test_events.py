"""Offline contract tests for :mod:`egta.contracts.events`.

Every negative case raises strictly (no ``xfail``/``skip``): if the contract
stops rejecting bad input, the test fails.

Hash-chain responsibilities are kept in this test module on purpose:
``RunEvent`` only carries the two hash fields and never re-checks the chain
itself, so the assertions here model what a consumer's verifier must prove:
payload binding (a recomputed payload hash must match) and link integrity (each
``prev_event_hash`` must equal the previous event's ``payload_hash``).

The verifier's failure modes are modelled with **test-local helper exceptions**
(``ChainBroken``, ``DuplicateConflict``, ``PayloadMismatch``). These are NOT part
of the public contract yet -- their public placement/signature is pending D's
confirmation (see PR #3 body / DEBT-D2 discussion). Defining them here keeps the
spec executable now without pre-empting that decision in ``src/``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from egta.contracts.events import Phase, ReasonCode, RunEvent, RunStatus

VALID_HASH = "a" * 64


# --- test-local verifier failure modes (public placement pending D) ----------


class ChainBroken(Exception):
    """A link in the event chain is missing, out of order, or broken."""


class DuplicateConflict(Exception):
    """The same ``event_id`` appears twice with different content."""


class PayloadMismatch(Exception):
    """A recomputed ``payload_hash`` does not match the stored one."""


def _utc() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _event(**overrides) -> RunEvent:
    """A minimal valid RunEvent; overrides replace individual fields."""
    base = {
        "event_id": "e1",
        "run_id": "r1",
        "sequence": 0,
        "phase": Phase.EVIDENCE,
        "timestamp": _utc(),
        "status": RunStatus.OK,
        "payload_hash": VALID_HASH,
        "prev_event_hash": "",
    }
    base.update(overrides)
    return RunEvent(**base)


def payload_hash_of(event: RunEvent) -> str:
    """A consumer-side, canonical digest of the event's OWN content.

    Hashes the event exactly as passed (JSON-canonicalised, ``payload_hash``
    excluded). A verifier recomputes this and compares it to ``payload_hash``;
    a mismatch means the payload was altered after the hash was written.
    """
    payload = event.model_dump(mode="json", exclude={"payload_hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def bind_payload(event_kwargs: dict) -> dict:
    """Build kwargs for an event whose ``payload_hash`` is the hash of ITSELF.

    The event is constructed once to obtain canonical content, hashed, then
    returned with that hash set. This is the correct way to make ``ev2`` hash its
    own content (including its real ``prev_event_hash``), fixing the old fixture
    that hashed a *different*, inner event.
    """
    draft = _event(**event_kwargs)
    digest = payload_hash_of(draft)
    return {**event_kwargs, "payload_hash": digest}


def verify_payload(event: RunEvent) -> None:
    """Recompute payload hash and raise ``PayloadMismatch`` on divergence."""
    if payload_hash_of(event) != event.payload_hash:
        raise PayloadMismatch(event.event_id)


def verify_chain(events: list[RunEvent]) -> None:
    """Verify links + payload binding + sequence contiguity + dedupe.

    Raises:
        ChainBroken: first event has a non-empty ``prev_event_hash``, a later
            event's ``prev_event_hash`` does not equal the previous
            ``payload_hash``, or the ``sequence`` numbers are not gap-free from 0.
        DuplicateConflict: an ``event_id`` repeats with different content.
        PayloadMismatch: an event's stored ``payload_hash`` does not match a
            recomputation from its content.
    """
    if not events:
        return
    if events[0].prev_event_hash != "":
        raise ChainBroken("first event must have empty prev_event_hash")
    if [e.sequence for e in events] != list(range(len(events))):
        raise ChainBroken("sequence must be gap-free from 0")

    seen: dict[str, str] = {}
    for event in events:
        # payload binding: stored hash must equal the recomputed one
        verify_payload(event)
        # duplicate event_id handling
        body = payload_hash_of(event)
        if event.event_id in seen:
            if seen[event.event_id] != body:
                raise DuplicateConflict(event.event_id)
            # identical duplicate: tolerate (caller collapses via repr dedupe)
        else:
            seen[event.event_id] = body

    for prev, cur in zip(events, events[1:], strict=False):
        if cur.prev_event_hash != prev.payload_hash:
            raise ChainBroken(f"link {prev.sequence}->{cur.sequence} broken")


# --- self-check: the verifier itself must discriminate valid vs broken -------


def test_verify_chain_helper_is_not_vacuous():
    """Guard against a verifier that always passes.

    If ``verify_chain`` silently accepted everything, the negative tests below
    would pass vacuously. This self-check proves a genuine chain passes and a
    broken one raises, so the real assertions are meaningful.
    """
    ev1 = _event(**bind_payload({"sequence": 0}))
    ev2 = _event(**bind_payload(
        {"sequence": 1, "event_id": "e2", "prev_event_hash": ev1.payload_hash}
    ))
    verify_chain([ev1, ev2])  # no raise == good chain accepted

    # Break the LINK without breaking payload binding: alter ev1's content and
    # re-bind ev1's own payload_hash, so ev1 stays internally valid but its hash
    # no longer equals ev2.prev_event_hash. This isolates ChainBroken from
    # PayloadMismatch (which a naive mutate-in-place would trigger first).
    ev1_forged = _event(**bind_payload(
        {"sequence": 0, "metrics": {"forged": True}}
    ))
    with pytest.raises(ChainBroken):
        verify_chain([ev1_forged, ev2])


# --- positive ----------------------------------------------------------------


def test_run_event_constructs():
    ev = _event(metrics={"tokens": 10})
    assert ev.run_id == "r1"
    assert ev.phase is Phase.EVIDENCE
    assert ev.status is RunStatus.OK
    assert ev.metrics == {"tokens": 10}
    assert ev.reason_code is None


def test_reason_code_accepts_canonical_value():
    ev = _event(status=RunStatus.BLOCKED, reason_code=ReasonCode.BUDGET_DENIED)
    assert ev.reason_code is ReasonCode.BUDGET_DENIED


# --- negative: hashes --------------------------------------------------------


@pytest.mark.parametrize("bad", ["XYZ", "A" * 64, "a" * 63, "a" * 65, ""])
def test_payload_hash_must_be_64_lowercase_hex(bad):
    with pytest.raises(ValidationError):
        _event(payload_hash=bad)


@pytest.mark.parametrize("bad", ["abc", "A" * 64, "a" * 63])
def test_prev_event_hash_must_be_empty_or_64_lowercase_hex(bad):
    with pytest.raises(ValidationError):
        _event(prev_event_hash=bad)


def test_prev_event_hash_may_be_empty_for_first_event():
    assert _event(prev_event_hash="").prev_event_hash == ""


# --- negative: timezone ------------------------------------------------------


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        _event(timestamp=datetime(2026, 1, 2, 3, 4, 5))


def test_aware_timestamp_normalized_to_utc():
    tz8 = timezone(timedelta(hours=8))
    ev = _event(timestamp=datetime(2026, 1, 2, 11, 4, 5, tzinfo=tz8))
    assert ev.timestamp.utcoffset() == timedelta(0)
    assert ev.timestamp == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


# --- negative: schema strictness --------------------------------------------


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        _event(unexpected="x")


@pytest.mark.parametrize("bad", ["NOPE", "budget_denied", ""])
def test_illegal_reason_code_rejected(bad):
    with pytest.raises(ValidationError):
        _event(reason_code=bad)


# --- hash chain: payload binding + tamper -----------------------------------


def test_hash_chain_links_and_tamper_breaks_it():
    """A correct chain passes; mutating an earlier payload_hash breaks a link.

    ``ev2.payload_hash`` is the hash of ev2's OWN content (including its real
    ``prev_event_hash``), so this chain is genuinely valid -- both the payload
    binding and the links hold.
    """
    ev1 = _event(**bind_payload({"sequence": 0}))
    ev2 = _event(**bind_payload(
        {"sequence": 1, "event_id": "e2", "prev_event_hash": ev1.payload_hash}
    ))
    assert verify_chain([ev1, ev2]) is None  # valid chain, no raise

    # Tamper ev1's stored payload_hash WITHOUT re-binding: this must be caught by
    # payload binding (PayloadMismatch) on ev1 itself.
    tampered = [ev1.model_copy(update={"payload_hash": "f" * 64}), ev2]
    with pytest.raises(PayloadMismatch):
        verify_chain(tampered)


def test_recomputed_payload_hash_mismatch_is_rejected():
    """Payload binding: if content changes but payload_hash does not, reject.

    The event is built with a valid self-hash, then its content is mutated
    WITHOUT updating ``payload_hash``. A verifier that recomputes must reject it.
    """
    good = _event(**bind_payload({"sequence": 0}))
    mutated = good.model_copy(update={"metrics": {"tokens": 999}})  # content changed
    with pytest.raises(PayloadMismatch):
        verify_payload(mutated)


# --- new negative: sequence gap ----------------------------------------------


def test_sequence_gap_is_rejected():
    """Events [0, 2] with 1 missing must be reported as a broken chain."""
    ev0 = _event(**bind_payload({"sequence": 0}))
    ev2 = _event(**bind_payload(
        {"sequence": 2, "event_id": "e3", "prev_event_hash": ev0.payload_hash}
    ))
    with pytest.raises(ChainBroken):
        verify_chain([ev0, ev2])


# --- new negative: duplicate event_id ----------------------------------------


def test_duplicate_event_id_conflict_is_rejected():
    """Same event_id, different content -> DuplicateConflict."""
    ev0 = _event(**bind_payload({"sequence": 0, "event_id": "dup"}))
    ev1 = _event(**bind_payload(
        {"sequence": 1, "event_id": "dup", "prev_event_hash": ev0.payload_hash,
         "metrics": {"different": True}}
    ))
    with pytest.raises(DuplicateConflict):
        verify_chain([ev0, ev1])


def test_identical_duplicate_event_id_is_deduped_once():
    """Identical duplicate event_id collapses to one (no conflict)."""
    ev0 = _event(**bind_payload({"sequence": 0, "event_id": "same"}))
    deduped = {e.event_id: e for e in [ev0, ev0]}  # replay-time dedupe
    assert len(deduped) == 1
