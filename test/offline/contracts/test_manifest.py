"""Offline contract tests for :mod:`egta.contracts.manifest` (B's decisions).

Negative cases raise strictly (no ``xfail``/``skip``). Tests encoding B's
not-yet-implemented decisions are expected RED until the contract implements
them (no xfail/skip; red is the test-first signal).

Contract definitions: docs/req/contracts-summary.md §3.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from egta.contracts.manifest import ExperimentManifest

pytestmark = pytest.mark.spec

VALID_HASH = "a" * 64

ALL_VARIANTS = {
    "B0": {"mode": "baseline"},
    "B1": {"mode": "enhanced"},
    "B2": {"mode": "ablation-1"},
    "B3": {"mode": "ablation-2"},
}

_METRIC_DEF = {
    "metric": "token_cost",
    "operator": "lte",
    "threshold": 2.0,
    "verification": "pytest",
    "source": "budget",
    "aggregation": "median",
    "unit": "USD",
}

_VALID_QUALITY = {
    "levels": ["gold", "silver", "bronze"],
    "double_blind": True,
    "third_party_adjudication": True,
    "llm_judge_assist": False,
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
        "metrics_rubric": {"token_cost": dict(_METRIC_DEF)},
        "quality_rubric": dict(_VALID_QUALITY),
    }
    base.update(overrides)
    return ExperimentManifest(**base)


# --- positive ----------------------------------------------------------------


def test_manifest_with_all_four_variants_constructs():
    m = _manifest()
    assert set(m.variants) == {"B0", "B1", "B2", "B3"}


def test_non_empty_b1_b2_b3_positive():
    """All four variants present and non-empty -> valid."""
    m = _manifest()
    for name in ("B1", "B2", "B3"):
        assert m.variants[name]


# --- negative: required variants (four mandatory) ---------------------------


@pytest.mark.parametrize("missing", ["B0", "B1", "B2", "B3"])
def test_missing_any_variant_rejected(missing):
    """B: all four B0/B1/B2/B3 mandatory (RED until implemented)."""
    variants = {k: v for k, v in ALL_VARIANTS.items() if k != missing}
    with pytest.raises(ValidationError):
        _manifest(variants=variants)


def test_unknown_variant_key_rejected():
    """An unknown variant key (e.g. B9) is not allowed."""
    variants = dict(ALL_VARIANTS)
    variants["B9"] = {"mode": "bogus"}
    with pytest.raises(ValidationError):
        _manifest(variants=variants)


def test_empty_b0_rejected_by_validator():
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


# --- metrics_rubric: typed MetricDef ----------------------------------------


def test_empty_metrics_rubric_rejected():
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
    entry = dict(_METRIC_DEF)
    entry.pop(field)
    with pytest.raises(ValidationError):
        _manifest(metrics_rubric={"token_cost": entry})


# --- quality_rubric: independent field --------------------------------------


def test_quality_rubric_positive():
    m = _manifest()
    assert m.quality_rubric.levels  # non-empty, >=3
    assert len(m.quality_rubric.levels) >= 3


@pytest.mark.parametrize(
    "field", ["levels", "double_blind", "third_party_adjudication",
              "llm_judge_assist"]
)
def test_quality_rubric_missing_field_rejected(field):
    q = dict(_VALID_QUALITY)
    q.pop(field)
    with pytest.raises(ValidationError):
        _manifest(quality_rubric=q)


def test_quality_rubric_requires_three_levels():
    q = dict(_VALID_QUALITY)
    q["levels"] = ["only-one"]
    with pytest.raises(ValidationError):
        _manifest(quality_rubric=q)


def test_quality_rubric_illegal_bool_rejected():
    q = dict(_VALID_QUALITY)
    q["double_blind"] = "yes-please"  # not a bool
    with pytest.raises(ValidationError):
        _manifest(quality_rubric=q)
