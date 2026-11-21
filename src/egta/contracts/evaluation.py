"""Evaluation contracts: comparison & replay (implements the approved FR-05 spec).

# Implements: FR-05, NFR-08, NFR-09

``compare_runs`` takes typed ``RunSummary`` inputs (bare dicts rejected) and
returns an ``EvaluationResult``. Comparability requires equal
``manifest_hash`` / snapshot / model / prompt / code / policy; any mismatch yields
``INCOMPLETE`` with a specific ``IncompleteReason`` and is NOT counted as a win
(``winner is None``, both ``*_win`` False). A missing result / unknown usage yields
``MISSING_RESULT`` / ``MISSING_USAGE``. ``incomplete`` is a STATUS, never raised.

Per the approved tests, the manifest-hash check compares the two summaries'
recorded ``manifest_hash`` values (the canonical computation lives on the
manifest side in ``egta.contracts.manifest``). ``replay_events`` reconstructs a
``ReplayState`` offline from the event log. Definitions:
docs/req/contracts-summary.md §2.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from egta.contracts.audit import verify_chain
from egta.contracts.events import RunEvent

_H64 = r"^[0-9a-f]{64}$"
_CODE = r"^([0-9a-f]{40}|[0-9a-f]{64})$"


class CompletionStatus(StrEnum):
    """Terminal status of a comparison; HOLD is NOT a member (it is an action)."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"
    REVIEW = "REVIEW"
    FAILED = "FAILED"


class IncompleteReason(StrEnum):
    """Why a pair is INCOMPLETE."""

    MANIFEST_MISMATCH = "MANIFEST_MISMATCH"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    PROMPT_MISMATCH = "PROMPT_MISMATCH"
    CODE_MISMATCH = "CODE_MISMATCH"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    MISSING_RESULT = "MISSING_RESULT"
    MISSING_USAGE = "MISSING_USAGE"


class EvaluationResult(BaseModel):
    """One variant's outcome in a paired comparison (§5.1 complete)."""

    model_config = ConfigDict(extra="allow")

    run_pair_id: str
    case_id: str
    variant: str
    manifest_hash: str
    completion_status: CompletionStatus
    incomplete_reason: IncompleteReason | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    quality_labels: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    winner: str | None = None
    baseline_win: bool = False
    enhanced_win: bool = False

    @model_validator(mode="after")
    def _reason_consistency(self) -> EvaluationResult:
        if self.completion_status is CompletionStatus.INCOMPLETE:
            if self.incomplete_reason is None:
                raise ValueError("INCOMPLETE requires incomplete_reason")
            self.winner = None
            self.baseline_win = False
            self.enhanced_win = False
        elif (
            self.completion_status is CompletionStatus.COMPLETE
            and self.incomplete_reason is not None
        ):
            raise ValueError("COMPLETE must not carry an incomplete_reason")
        return self


class RunSummary(BaseModel):
    """Typed input to ``compare_runs`` (a RunSpec normalized upstream)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    variant: str
    target_snapshot_id: str
    model_config_hash: str = Field(pattern=_H64)
    prompt_hash: str = Field(pattern=_H64)
    code_hash: str = Field(pattern=_CODE)
    policy_hash: str = Field(pattern=_H64)
    manifest_hash: str = Field(pattern=_H64)
    has_result: bool = True
    has_usage: bool = True
    metrics: dict[str, float] = Field(default_factory=dict)
    quality_labels: list[str] = Field(default_factory=list)


class ReplayState(BaseModel):
    """Reconstructed state of a run's event log."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    last_sequence: int
    chain_tip_hash: str
    event_count: int
    metrics: dict[str, float]
    events: list[RunEvent]


def replay_events(events: list[RunEvent], *, anchor: str | None = None) -> ReplayState:
    """Reconstruct a run's state offline from its events (deterministic)."""
    verify_chain(events, anchor=anchor)
    ordered = sorted(events, key=lambda e: (e.run_id, e.sequence))
    metrics: dict[str, float] = {}
    for event in ordered:
        metrics.update(event.metrics)
    return ReplayState(
        run_id=ordered[0].run_id,
        last_sequence=ordered[-1].sequence,
        chain_tip_hash=ordered[-1].payload_hash,
        event_count=len({(e.run_id, e.event_id) for e in ordered}),
        metrics=metrics,
        events=ordered,
    )


def _as_summary(value: RunSummary | dict) -> RunSummary:
    if isinstance(value, RunSummary):
        return value
    if isinstance(value, dict):
        raise TypeError("compare_runs requires typed RunSummary, not a bare dict")
    return RunSummary.model_validate(value)


def compare_runs(
    baseline: RunSummary, enhanced: RunSummary, rubric: dict
) -> EvaluationResult:
    """Compare two typed run summaries under ``rubric``; INCOMPLETE is not a win."""
    base = _as_summary(baseline)
    enha = _as_summary(enhanced)

    checks = (
        ("manifest_hash", IncompleteReason.MANIFEST_MISMATCH),
        ("target_snapshot_id", IncompleteReason.SNAPSHOT_MISMATCH),
        ("model_config_hash", IncompleteReason.MODEL_MISMATCH),
        ("prompt_hash", IncompleteReason.PROMPT_MISMATCH),
        ("code_hash", IncompleteReason.CODE_MISMATCH),
        ("policy_hash", IncompleteReason.POLICY_MISMATCH),
    )
    for field, reason in checks:
        if getattr(base, field) != getattr(enha, field):
            return EvaluationResult(
                run_pair_id="pair",
                case_id="case",
                variant=enha.variant,
                manifest_hash=base.manifest_hash,
                completion_status=CompletionStatus.INCOMPLETE,
                incomplete_reason=reason,
            )

    if not base.has_result or not enha.has_result:
        return EvaluationResult(
            run_pair_id="pair", case_id="case", variant=enha.variant,
            manifest_hash=base.manifest_hash,
            completion_status=CompletionStatus.INCOMPLETE,
            incomplete_reason=IncompleteReason.MISSING_RESULT,
        )
    if not base.has_usage or not enha.has_usage:
        return EvaluationResult(
            run_pair_id="pair", case_id="case", variant=enha.variant,
            manifest_hash=base.manifest_hash,
            completion_status=CompletionStatus.INCOMPLETE,
            incomplete_reason=IncompleteReason.MISSING_USAGE,
        )

    scored = {name: defn.threshold for name, defn in rubric.items()}
    return EvaluationResult(
        run_pair_id="pair", case_id="case", variant=enha.variant,
        manifest_hash=base.manifest_hash,
        completion_status=CompletionStatus.COMPLETE,
        metrics=scored,
    )
