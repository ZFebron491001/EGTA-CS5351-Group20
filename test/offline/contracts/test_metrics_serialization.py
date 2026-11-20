"""Offline tests: ``RunEvent.metrics`` JSON/non-finite serialization semantics.

``RunEvent`` sets ``allow_inf_nan=False`` on the *model*, but ``metrics`` is a
``dict[str, Any]``; that flag only guards declared float *fields*, not arbitrary
values nested inside a dict. These tests pin the CURRENT behavior so the gap is a
visible, conscious fact rather than a silent surprise.

Observed against the current contract (feature branch src):

- ``float('nan')`` / ``float('inf')`` inside ``metrics``: construction succeeds,
  and ``model_dump_json()`` emits JSON ``null`` for them. This is **data-loss /
  silent corruption**: a NaN metric serializes identically to a missing value
  (``null``), and the stored payload_hash would hash the pre-serialization object
  while the persisted JSON differs. DEFECT -- propose a metrics validator that
  rejects non-finite floats (or a custom encoder), tracked for the implementation.
- A non-serializable object (``object()``) inside ``metrics``: construction
  succeeds (``Any`` accepts it) but ``model_dump_json()`` raises
  ``PydanticSerializationError``. So it fails *late* at serialization, not at
  reception -- also undesirable; a metrics validator should reject non-JSON
  values at construction.

These are strict assertions of current behavior (no xfail/skip). When the
implementation adds a metrics validator, the DEFECT tests will flip to asserting
rejection, forcing a deliberate change.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from egta.contracts.events import Phase, RunEvent, RunStatus

VALID_HASH = "a" * 64


def _event(metrics) -> RunEvent:
    return RunEvent(
        event_id="e",
        run_id="r",
        sequence=0,
        phase=Phase.APP,
        timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        status=RunStatus.OK,
        payload_hash=VALID_HASH,
        prev_event_hash="",
        metrics=metrics,
    )


def test_nan_metric_serializes_to_null_defect():
    """DEFECT: NaN is silently dropped to JSON null (indistinguishable from None).

    Current behavior: construction succeeds and ``model_dump_json`` emits
    ``"x":null``. This loses information. Recorded as a defect pending a metrics
    validator. The final two assertions document the loss explicitly.
    """
    ev = _event({"x": float("nan")})
    dumped = ev.model_dump_json()
    assert '"x":null' in dumped  # NaN -> null (data loss)
    assert ev.metrics["x"] != ev.metrics["x"]  # NaN is not equal to itself


def test_inf_metric_serializes_to_null_defect():
    """DEFECT: +inf is silently dropped to JSON null (same loss as NaN)."""
    ev = _event({"x": float("inf")})
    assert '"x":null' in ev.model_dump_json()


def test_non_serializable_metric_fails_at_serialization():
    """A non-JSON object is accepted at construction but fails at dump time.

    Undesirable 'late' failure. Pinned so the implementation adds an early
    validator; meanwhile the fact that construction raises nothing is asserted.
    """
    ev = _event({"x": object()})  # Any accepts it; no error yet
    with pytest.raises(Exception) as exc:  # PydanticSerializationError
        ev.model_dump_json()
    assert "serialize" in str(exc.value).lower() or "unknown type" in str(exc.value).lower()


def test_json_safe_metrics_roundtrip():
    """Positive: JSON-safe metrics serialize and validate cleanly."""
    ev = _event({"tokens": 10, "usd": 0.5, "flag": True, "note": "ok"})
    dumped = ev.model_dump_json()
    assert '"tokens":10' in dumped
    again = RunEvent.model_validate_json(dumped)
    assert again.metrics == ev.metrics


def test_validation_error_type_is_pydantic():
    """Guard: the contract raises pydantic.ValidationError for bad field values.

    Ensures downstream tests catching ValidationError are catching the right type.
    """
    with pytest.raises(ValidationError):
        RunEvent(
            event_id="e", run_id="r", sequence=0, phase=Phase.APP,
            timestamp=datetime(2026, 1, 2, 3, 4, 5), status=RunStatus.OK,
            payload_hash=VALID_HASH, prev_event_hash="", metrics={},
        )
