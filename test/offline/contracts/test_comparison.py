"""Offline tests: incompatible manifests -> INCOMPLETE (not a win, not raised).

A paired comparison across snapshots/models/prompts is only valid when the run
inputs match. On mismatch the pair is ``completion_status=INCOMPLETE`` with the
matching ``IncompleteReason``, and it is NOT counted as a win for either variant.

code/policy mismatch is PENDING (B): ExperimentManifest currently has no
code_hash/policy_hash, so only snapshot/model/prompt are asserted here.

Contract definitions: docs/req/contracts-summary.md §2/§3.
"""

from __future__ import annotations

import pytest

from egta.contracts.evaluation import (
    CompletionStatus,
    IncompleteReason,
    compare_runs,
)

pytestmark = pytest.mark.spec

VALID_HASH = "a" * 64


def _run(snapshot="snap1", model=VALID_HASH, prompt=VALID_HASH, variant="B0"):
    return {
        "variant": variant,
        "target_snapshot_id": snapshot,
        "model_config_hash": model,
        "prompt_hash": prompt,
    }


@pytest.mark.parametrize(
    "field, reason",
    [
        ("snapshot", IncompleteReason.SNAPSHOT_MISMATCH),
        ("model", IncompleteReason.MODEL_MISMATCH),
        ("prompt", IncompleteReason.PROMPT_MISMATCH),
    ],
)
def test_mismatch_yields_incomplete_not_win(field, reason):
    baseline = _run(variant="B0")
    enhanced = _run(variant="B1")
    # make the enhanced run differ in exactly one field
    if field == "snapshot":
        enhanced["target_snapshot_id"] = "snap2"
    elif field == "model":
        enhanced["model_config_hash"] = "b" * 64
    else:
        enhanced["prompt_hash"] = "b" * 64

    result = compare_runs(baseline, enhanced)
    assert result.completion_status is CompletionStatus.INCOMPLETE
    assert result.incomplete_reason is reason
    # not counted as a win for either variant
    assert getattr(result, "baseline_win", None) in (False, None)
    assert getattr(result, "enhanced_win", None) in (False, None)


def test_matching_inputs_are_comparable():
    result = compare_runs(_run("snap1", variant="B0"), _run("snap1", variant="B1"))
    # comparable pair should not be INCOMPLETE for a mismatch reason
    assert result.completion_status is not CompletionStatus.INCOMPLETE or (
        result.incomplete_reason not in {
            IncompleteReason.SNAPSHOT_MISMATCH,
            IncompleteReason.MODEL_MISMATCH,
            IncompleteReason.PROMPT_MISMATCH,
        }
    )
