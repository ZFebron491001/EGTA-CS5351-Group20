"""Offline tests: ``incomplete`` is a STATUS, never an exception.

``egta.contracts.evaluation`` exposes ``CompletionStatus`` and
``IncompleteReason`` enums and ``EvaluationResult.completion_status`` /
``.incomplete_reason`` fields. A manifest mismatch is represented as
``completion_status=INCOMPLETE`` (returned, not raised).

Contract definitions: docs/req/contracts-summary.md §2. RED on spec branch.
"""

from __future__ import annotations

import pytest

from egta.contracts.evaluation import (
    CompletionStatus,
    EvaluationResult,
    IncompleteReason,
)

pytestmark = pytest.mark.spec


def test_completion_status_members():
    assert {s.name for s in CompletionStatus} == {
        "COMPLETE", "INCOMPLETE", "BLOCKED", "REVIEW", "FAILED"
    }


def test_incomplete_reason_members():
    names = {r.name for r in IncompleteReason}
    assert {"MANIFEST_MISMATCH", "SNAPSHOT_MISMATCH", "MODEL_MISMATCH",
            "PROMPT_MISMATCH", "CODE_MISMATCH", "MISSING_RESULT"} <= names


def test_incomplete_result_does_not_raise():
    """Constructing an INCOMPLETE result returns an object (no exception)."""
    result = EvaluationResult(
        run_pair_id="p1", case_id="c1", variant="B0",
        completion_status=CompletionStatus.INCOMPLETE,
        incomplete_reason=IncompleteReason.SNAPSHOT_MISMATCH,
    )
    assert result.completion_status is CompletionStatus.INCOMPLETE
    assert result.incomplete_reason is IncompleteReason.SNAPSHOT_MISMATCH


def test_complete_result_has_no_incomplete_reason():
    result = EvaluationResult(
        run_pair_id="p1", case_id="c1", variant="B0",
        completion_status=CompletionStatus.COMPLETE,
    )
    assert result.incomplete_reason is None
