"""Offline tests: compare_runs typed inputs + incompatibility (D item 5).

- typed inputs (reject bare dict); rubric passed and used.
- mismatch (snapshot/model/prompt/code/policy) -> INCOMPLETE + specific reason,
  winner=None, both wins False (no getattr escape).
- matching -> COMPLETE.
- MISSING_RESULT -> INCOMPLETE, not a win.
- manifest_hash mismatch -> INCOMPLETE/MANIFEST_MISMATCH.

Definitions: docs/req/contracts-summary.md §2. RED on the spec branch.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from egta.contracts.evaluation import (
    CompletionStatus,
    EvaluationResult,
    IncompleteReason,
    RunSummary,
    compare_runs,
)
from egta.contracts.manifest import (
    ExperimentManifest,
    MetricDef,
    QualityRubric,
)

pytestmark = pytest.mark.spec

H = "a" * 64
H2 = "b" * 64


def _summary(**over):
    base = {
        "variant": "B0", "run_id": "run0",
        "target_snapshot_id": "snap1",
        "model_config_hash": H, "prompt_hash": H,
        "code_hash": H, "policy_hash": H,
        "manifest_hash": H,
        "has_result": True,
    }
    base.update(over)
    return RunSummary(**base)


def _rubric():
    return {
        "token_cost": MetricDef(
            metric="token_cost", operator="lte", threshold=2.0,
            verification="pytest", source="budget", aggregation="median",
            unit="USD",
        )
    }


def _manifest(**over):
    base = {
        "manifest_id": "m1",
        "created_at": datetime(2026, 1, 2, tzinfo=UTC),
        "target_snapshot_id": "snap1",
        "model_config_hash": H, "prompt_hash": H,
        "code_hash": H, "policy_hash": H, "manifest_hash": H,
        "variants": {"B0": {"m": 1}, "B1": {"m": 2}, "B2": {"m": 3}, "B3": {"m": 4}},
        "metrics_rubric": {"token_cost": _rubric()["token_cost"]},
        "quality_rubric": QualityRubric(
            levels=["gold", "silver", "bronze"], double_blind=True,
            third_party_adjudication=True, llm_judge_assist=False),
    }
    base.update(over)
    return ExperimentManifest(**base)


def test_compare_rejects_bare_dict():
    with pytest.raises((TypeError, ValueError)):
        compare_runs({"variant": "B0"}, {"variant": "B1"}, _rubric())


@pytest.mark.parametrize(
    "field, reason",
    [
        ("target_snapshot_id", IncompleteReason.SNAPSHOT_MISMATCH),
        ("model_config_hash", IncompleteReason.MODEL_MISMATCH),
        ("prompt_hash", IncompleteReason.PROMPT_MISMATCH),
        ("code_hash", IncompleteReason.CODE_MISMATCH),
        ("policy_hash", IncompleteReason.POLICY_MISMATCH),
    ],
)
def test_mismatch_yields_incomplete_not_win(field, reason):
    baseline = _summary(variant="B0")
    enhanced = _summary(variant="B1", **{field: H2})
    result = compare_runs(baseline, enhanced, _rubric())
    assert result.completion_status is CompletionStatus.INCOMPLETE
    assert result.incomplete_reason is reason
    assert result.winner is None
    assert result.baseline_win is False and result.enhanced_win is False


def test_manifest_hash_mismatch():
    baseline = _summary(variant="B0")
    enhanced = _summary(variant="B1", manifest_hash=H2)
    result = compare_runs(baseline, enhanced, _rubric())
    assert result.completion_status is CompletionStatus.INCOMPLETE
    assert result.incomplete_reason is IncompleteReason.MANIFEST_MISMATCH
    assert result.winner is None


def test_missing_result_is_incomplete_not_win():
    baseline = _summary(variant="B0")
    enhanced = _summary(variant="B1", has_result=False)
    result = compare_runs(baseline, enhanced, _rubric())
    assert result.completion_status is CompletionStatus.INCOMPLETE
    assert result.incomplete_reason is IncompleteReason.MISSING_RESULT
    assert result.winner is None
    assert result.baseline_win is False and result.enhanced_win is False


def test_matching_inputs_complete_and_rubric_used():
    baseline = _summary(variant="B0")
    enhanced = _summary(variant="B1")
    rubric = _rubric()
    result = compare_runs(baseline, enhanced, rubric)
    assert result.completion_status is CompletionStatus.COMPLETE
    assert result.incomplete_reason is None
    # rubric must influence the result: its metric appears in scored metrics
    assert "token_cost" in result.metrics
    assert isinstance(result, EvaluationResult)
