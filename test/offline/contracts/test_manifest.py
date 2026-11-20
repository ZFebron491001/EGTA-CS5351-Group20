"""Offline contract tests for :mod:`egta.contracts.manifest`.

Negative cases raise strictly (no ``xfail``/``skip``). Where a rejection is not
obvious, the test documents which branch fires:

- missing B0 / missing B1 / empty B0 -> ``_require_core_variants`` (model_validator),
  not a Pydantic type error.
- ``metrics_rubric`` looseness is asserted explicitly here (see the deferred note)
  so the current permissive behavior is a known, visible fact rather than silent.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from egta.contracts.manifest import ExperimentManifest

VALID_HASH = "a" * 64


def _utc() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _manifest(**overrides) -> ExperimentManifest:
    base = {
        "manifest_id": "m1",
        "created_at": _utc(),
        "target_snapshot_id": "snap1",
        "model_config_hash": VALID_HASH,
        "prompt_hash": VALID_HASH,
        "variants": {"B0": {"mode": "baseline"}, "B1": {"mode": "enhanced"}},
        "metrics_rubric": {"token_cost": {"operator": "lte", "threshold": 2.0}},
    }
    base.update(overrides)
    return ExperimentManifest(**base)


# --- positive ----------------------------------------------------------------


def test_manifest_with_b0_and_b1_constructs():
    m = _manifest()
    assert set(m.variants) >= {"B0", "B1"}
    assert m.variants["B0"] == {"mode": "baseline"}


# --- negative: required variants (model_validator branch) --------------------


def test_missing_b0_rejected_by_validator():
    # _require_core_variants: B0 absent from variants -> ValueError surfaced as
    # ValidationError. Not a Pydantic type error.
    with pytest.raises(ValidationError):
        _manifest(variants={"B1": {"mode": "enhanced"}})


def test_missing_b1_rejected_by_validator():
    # _require_core_variants: B1 absent -> ValueError surfaced as ValidationError.
    with pytest.raises(ValidationError):
        _manifest(variants={"B0": {"mode": "baseline"}})


def test_empty_b0_rejected_by_validator():
    # "B0": {} passes the dict type check, then fails the `if not baseline`
    # branch in _require_core_variants (empty dict is falsy). This exercises the
    # model_validator, not a type error.
    with pytest.raises(ValidationError):
        _manifest(variants={"B0": {}, "B1": {"mode": "enhanced"}})


# --- negative: hashes --------------------------------------------------------


@pytest.mark.parametrize("bad", ["XYZ", "A" * 64, "a" * 63, ""])
def test_bad_model_config_hash_rejected(bad):
    with pytest.raises(ValidationError):
        _manifest(model_config_hash=bad)


@pytest.mark.parametrize("bad", ["XYZ", "A" * 64, "a" * 63, ""])
def test_bad_prompt_hash_rejected(bad):
    with pytest.raises(ValidationError):
        _manifest(prompt_hash=bad)


# --- negative: timezone ------------------------------------------------------


def test_naive_created_at_rejected():
    with pytest.raises(ValidationError):
        _manifest(created_at=datetime(2026, 1, 2, 3, 4, 5))


# --- metrics_rubric: current behavior is explicit (structure deferred) --------


def test_empty_metrics_rubric_currently_accepted():
    """Documents the current LOOSE behavior of ``metrics_rubric``.

    The rubric is ``dict[str, Any]`` and is NOT yet structurally validated, so an
    empty rubric is accepted today. A stricter ``MetricDef`` schema is deferred to
    the next round (see PR written response). This test makes the gap explicit:
    if the contract later rejects ``{}`` this test flips, forcing a conscious
    decision rather than a silent behavior change.
    """
    m = _manifest(metrics_rubric={})
    assert m.metrics_rubric == {}


def test_non_dict_metrics_rubric_rejected():
    # A type-level guard that still applies under the loose schema: a list is not
    # a mapping, so Pydantic rejects it. This is independent of the deferred
    # MetricDef structure work.
    with pytest.raises(ValidationError):
        _manifest(metrics_rubric=["not", "a", "mapping"])
