"""Offline contract tests for :mod:`egta.contracts.events`.

Every negative case raises strictly (no ``xfail``/``skip``): if the contract
stops rejecting bad input, the test fails. The hash-chain tests deliberately
keep chain logic in the test module -- ``RunEvent`` only carries the two hash
fields and never re-checks the chain itself (see events.py docstring), so the
assertions here demonstrate what a consumer's verifier must prove.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from egta.contracts.events import Phase, ReasonCode, RunEvent, RunStatus

VALID_HASH = "a" * 64


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
    """A consumer-side digest of the event payload (independent of the contract).

    Not used by ``RunEvent``; it stands in for what an emitters' sink would hash
    and what a replay verifier would recompute.
    """
    payload = event.model_dump(mode="json", exclude={"payload_hash"})
    return hashlib.sha256(str(sorted(payload.items())).encode()).hexdigest()


def verify_chain(events: list[RunEvent]) -> bool:
    """Check that each event links to the previous one's ``payload_hash``.

    Returns True only when, in sequence order, every ``prev_event_hash`` equals
    the preceding event's ``payload_hash`` and the first event's is empty. This
    is the property a tamper-evident, append-only log relies on: altering or
    dropping an earlier event breaks a later link.
    """
    if not events:
        return False
    if events[0].prev_event_hash != "":
        return False
    return all(
        cur.prev_event_hash == prev.payload_hash
        for prev, cur in zip(events, events[1:], strict=False)
    )


# --- self-check: the verifier itself must discriminate valid vs broken -------


def test_verify_chain_helper_is_not_vacuous():
    """Guard against a verifier that always passes.

    If ``verify_chain`` returned True unconditionally, the tamper test below
    would pass vacuously. This self-check proves the helper accepts a genuine
    chain and rejects a broken one, so the real assertions are meaningful.
    """
    good = [_event(sequence=0), _event(sequence=1, event_id="e2",
                                        payload_hash="b" * 64,
                                        prev_event_hash=VALID_HASH)]
    assert verify_chain(good) is True

    broken = good.copy()
    broken[1] = broken[1].model_copy(update={"prev_event_hash": "c" * 64})
    assert verify_chain(broken) is False


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


# --- hash chain --------------------------------------------------------------


def test_hash_chain_links_and_tamper_breaks_it():
    """(a) a correct chain passes; (b) mutating an earlier payload_hash fails.

    The mutation changes ``ev1.payload_hash`` so it no longer matches
    ``ev2.prev_event_hash``; re-running ``verify_chain`` must then return False.
    This is exactly the tamper the append-only log is meant to expose.
    """
    ev1 = _event(sequence=0, payload_hash=payload_hash_of(_event(sequence=0)))
    ev2 = _event(sequence=1, event_id="e2",
                 payload_hash=payload_hash_of(_event(sequence=1, event_id="e2")),
                 prev_event_hash=ev1.payload_hash)

    # (a) correct chain passes
    assert verify_chain([ev1, ev2]) is True

    # (b) tamper an earlier event's payload_hash -> chain must fail
    tampered = [ev1.model_copy(update={"payload_hash": "f" * 64}), ev2]
    assert verify_chain(tampered) is False
