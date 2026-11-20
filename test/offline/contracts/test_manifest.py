"""Offline contract tests for :mod:`egta.contracts.manifest`.

Negative cases raise strictly (no ``xfail``/``skip``). Where a rejection branch
is non-obvious, the test says which one fires.

Round status for this spec:
- The B0/B1-only, loose-rubric behavior was the ORIGINAL contract.
- B has now decided (see PR #3 body) that ``ExperimentManifest`` must require the
  four variants B0/B1/B2/B3, and that ``metrics_rubric`` is a typed structure
  (``MetricDef`` entries inside a ``QualityRubric``).
- Tests encoding B's NEW decisions are marked "dependency not yet implemented"
  and are expected to be RED until the implementation lands. They remain strict
  (no xfail/skip): red here is the test-first signal, not a masked pass.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from egta.contracts.manifest import ExperimentManifest

VALID_HASH = "a" * 64

# B's decision: all four variants are mandatory.
ALL_VARIANTS = {
    "B0": {"mode": "baseline"},
    "B1": {"mode": "enhanced"},
    "B2": {"mode": "ablation-1"},
    "B3": {"mode": "ablation-2"},
}


def _utc() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _manifest(**overrides) -> ExperimentManifest:
    base = {
        "manifest_id": "m1",
        "created_at": _utc(),
        "target_snapshot_id": "snap1",
        "model_config_hash": VALID_HASH,
        "prompt_hash": VALID_HASH,
        "variants": dict(ALL_VARIANTS),
        "metrics_rubric": {
            "token_cost": {
                "metric": "token_cost",
                "operator": "lte",
                "threshold": 2.0,
                "verification": "pytest",
                "source": "budget",
                "aggregation": "median",
                "unit": "USD",
            }
        },
    }
    base.update(overrides)
    return ExperimentManifest(**base)


# --- positive ----------------------------------------------------------------


def test_manifest_with_all_four_variants_constructs():
    """B's decision: B0/B1/B2/B3 all present -> valid."""
    m = _manifest()
    assert set(m.variants) == {"B0", "B1", "B2", "B3"}


# --- negative: required variants (all four mandatory) ------------------------


@pytest.mark.parametrize("missing", ["B0", "B1", "B2", "B3"])
def test_missing_any_variant_rejected(missing):
    """dependency not yet implemented: B requires all four B0/B1/B2/B3.

    Each omission must be rejected by the manifest validator (currently only
    B0/B1 are required, so B2/B3 omissions will be RED until implemented).
    """
    variants = {k: v for k, v in ALL_VARIANTS.items() if k != missing}
    with pytest.raises(ValidationError):
        _manifest(variants=variants)


def test_empty_b0_rejected_by_validator():
    # "B0": {} passes the dict type check, then fails the `if not baseline`
    # branch in the validator (empty dict is falsy) -- not a type error.
    variants = dict(ALL_VARIANTS)
    variants["B0"] = {}
    with pytest.raises(ValidationError):
        _manifest(variants=variants)


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


# --- metrics_rubric: typed MetricDef / QualityRubric (B's decision) ----------


def test_empty_metrics_rubric_rejected():
    """dependency not yet implemented: typed rubric must reject empty.

    B decided metrics_rubric is a typed QualityRubric; an empty rubric is not a
    valid rubric. Currently the loose dict accepts {} (RED until implemented).
    """
    with pytest.raises(ValidationError):
        _manifest(metrics_rubric={})


def test_non_dict_metrics_rubric_rejected():
    with pytest.raises(ValidationError):
        _manifest(metrics_rubric=["not", "a", "mapping"])


@pytest.mark.parametrize(
    "field", ["metric", "operator", "threshold", "verification", "source",
              "aggregation", "unit"]
)
def test_metric_def_missing_required_field_rejected(field):
    """dependency not yet implemented: MetricDef requires all seven fields.

    metric/operator/threshold/verification/source/aggregation/unit are each
    mandatory; dropping any one must be rejected.
    """
    entry = {
        "metric": "token_cost",
        "operator": "lte",
        "threshold": 2.0,
        "verification": "pytest",
        "source": "budget",
        "aggregation": "median",
        "unit": "USD",
    }
    entry.pop(field)
    with pytest.raises(ValidationError):
        _manifest(metrics_rubric={"token_cost": entry})


def test_quality_rubric_requires_three_levels_and_adjudication():
    """dependency not yet implemented: QualityRubric declares the judging policy.

    B's decision: a quality rubric records three levels, double-blind review,
    third-party adjudication, and whether an LLM judge may assist. Missing those
    policy fields must be rejected.
    """
    with pytest.raises(ValidationError):
        _manifest(metrics_rubric={"levels": []})
