"""Run-event contract for the audit log.

Every module (evidence, budget, deliberation, risk_gate, evaluation) emits a
:class:`RunEvent` when a phase changes. The evaluation module subscribes to
these events, verifies the hash chain, and replays them to rebuild a run's
recorded state and metrics.

Tamper-evidence and replay prevention come from the two hash fields:

- ``payload_hash`` is the SHA-256 of the event's own payload. Recomputing it on
  replay proves the payload has not been altered since it was written.
- ``prev_event_hash`` is the ``payload_hash`` of the previous event in the same
  run. Chained event-by-event, it makes the log append-only: changing or
  dropping any earlier event breaks every later link, and re-inserting an old
  event under a new sequence number fails the chain check.

Both hashes are hex-encoded lowercase SHA-256 digests (64 characters). Time is
timezone-aware UTC. The ordering key is ``(run_id, sequence)``; a subscriber
deduplicates on ``event_id`` so a redelivered event is applied once.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A SHA-256 digest rendered as lowercase hex.
_HASH_PATTERN = r"^[0-9a-f]{64}$"


class Phase(StrEnum):
    """The pipeline phase that produced an event."""

    EVIDENCE = "evidence"
    BUDGET = "budget"
    DELIBERATION = "deliberation"
    RISK_GATE = "risk_gate"
    LEDGER = "ledger"
    EVALUATION = "evaluation"
    APP = "app"


class RunStatus(StrEnum):
    """Terminal-or-intermediate status of a phase for one run.

    ``BLOCKED``, ``INCOMPLETE`` and ``REVIEW`` are system states, distinct from
    a valid ``HOLD`` decision; they must not be counted as success in reports.
    """

    STARTED = "started"
    OK = "ok"
    BLOCKED = "blocked"
    INCOMPLETE = "incomplete"
    REVIEW = "review"
    FAILED = "failed"


class ReasonCode(StrEnum):
    """Canonical failure/refusal reason codes shared across modules."""

    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    FUTURE_DATA = "FUTURE_DATA"
    BUDGET_DENIED = "BUDGET_DENIED"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    POLICY_REJECTED = "POLICY_REJECTED"
    STALE_PORTFOLIO = "STALE_PORTFOLIO"
    AUDIT_UNAVAILABLE = "AUDIT_UNAVAILABLE"
    INCOMPATIBLE_STATE = "INCOMPATIBLE_STATE"


class RunEvent(BaseModel):
    """One append-only entry in a run's audit log.

    Field meanings:

    - ``event_id``: unique id of this event; the dedupe key for subscribers.
    - ``run_id``: the run this event belongs to.
    - ``sequence``: monotonic, gap-free position within ``run_id`` (0-based).
    - ``phase``: which pipeline phase emitted the event.
    - ``timestamp``: when the event was emitted, timezone-aware UTC.
    - ``status``: phase status (see :class:`RunStatus`).
    - ``payload_hash``: SHA-256 of the event payload; proves the payload is
      unaltered on replay.
    - ``prev_event_hash``: ``payload_hash`` of the previous event in the same
      run, or the empty string for the first event; chains entries so deletions
      and reorderings are detectable.
    - ``metrics``: free-form numeric/structured metrics for this phase.
    - ``reason_code``: optional canonical reason when ``status`` is not ``OK``.
    """

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    event_id: str = Field(min_length=1, description="Unique id of this event.")
    run_id: str = Field(min_length=1, description="Run this event belongs to.")
    sequence: int = Field(ge=0, description="Monotonic, gap-free index within the run.")
    phase: Phase = Field(description="Pipeline phase that emitted the event.")
    timestamp: datetime = Field(description="Emission time, timezone-aware UTC.")
    status: RunStatus = Field(description="Phase status for this run.")
    payload_hash: str = Field(
        pattern=_HASH_PATTERN,
        description="SHA-256 (lowercase hex) of the event payload; tamper-evident on replay.",
    )
    prev_event_hash: str = Field(
        pattern=r"^([0-9a-f]{64})?$",
        description=(
            "payload_hash of the previous event in the same run, or empty for "
            "the first event; chains the log to prevent deletion/reordering."
        ),
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Structured metrics for this phase."
    )
    reason_code: ReasonCode | None = Field(
        default=None, description="Canonical reason when status is not OK."
    )

    @field_validator("timestamp")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return value.astimezone(UTC)
