"""Offline tests: ``RunEvent.metrics`` must stay JSON-safe.

Target contract (docs/req/contracts-summary.md §4): a metrics validator rejects
non-finite floats (NaN, ±inf) and non-serializable objects at construction with
``pydantic.ValidationError``. This replaces the earlier "pinned null behavior"
DEFECT tests: the contract is now required to REJECT, not silently corrupt.

RED on the spec branch (no src/) and RED against the current contract until the
metrics validator is implemented.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from egta.contracts.events import Phase, RunEvent, RunStatus

pytestmark = pytest.mark.spec

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


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_metric_rejected(bad):
    """NaN / ±inf are not valid JSON numbers -> reject at construction."""
    with pytest.raises(ValidationError):
        _event({"x": bad})


def test_non_json_object_metric_rejected():
    """A non-serializable object must be rejected at construction, not at dump."""
    with pytest.raises(ValidationError):
        _event({"x": object()})


def test_nested_non_finite_metric_rejected():
    """Non-finite nested inside a list/dict value is also rejected."""
    with pytest.raises(ValidationError):
        _event({"a": {"b": [1.0, float("nan")]}})


def test_json_safe_metrics_roundtrip():
    """Positive: JSON-safe metrics serialize and validate cleanly."""
    ev = _event({"tokens": 10, "usd": 0.5, "flag": True, "note": "ok"})
    dumped = ev.model_dump_json()
    assert '"tokens":10' in dumped
    again = RunEvent.model_validate_json(dumped)
    assert again.metrics == ev.metrics


def test_validation_error_type_is_pydantic():
    with pytest.raises(ValidationError):
        RunEvent(
            event_id="e", run_id="r", sequence=0, phase=Phase.APP,
            timestamp=datetime(2026, 1, 2, 3, 4, 5), status=RunStatus.OK,
            payload_hash=VALID_HASH, prev_event_hash="", metrics={},
        )
