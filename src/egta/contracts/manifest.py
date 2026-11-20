"""Controlled-experiment manifest contract.

# Implements: FR-05, NFR-08, NFR-09

An :class:`ExperimentManifest` freezes everything that makes a comparison run
reproducible and fair: the input snapshot, the model configuration, the prompt
bundle, and the exact variant configurations to run against that one snapshot.

Only runs that share ``target_snapshot_id``, ``model_config_hash`` and
``prompt_hash`` may be compared. A mismatch means the pair is not a controlled
comparison and its result is ``incomplete`` rather than a win for any variant.

The variants name the baseline (B0) and the enhanced builds (B1/B2/B3). Each
variant is an opaque configuration dict the app/runner understands; the
manifest does not interpret its contents beyond requiring baseline and
required enhanced variants to be present.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_HASH_PATTERN = r"^[0-9a-f]{64}$"

# The baseline (B0) must always be present; enhanced variants B1–B3 are the
# configured enhancements (full, and its ablations).
REQUIRED_VARIANTS = ("B0", "B1")


class ExperimentManifest(BaseModel):
    """Frozen inputs for one controlled comparison across variants.

    Field meanings:

    - ``manifest_id``: unique id of this experiment definition.
    - ``created_at``: when the manifest was frozen, timezone-aware UTC.
    - ``target_snapshot_id``: id of the shared input snapshot every variant
      consumes; comparisons across different snapshots are invalid.
    - ``model_config_hash``: SHA-256 of the model configuration all variants use.
    - ``prompt_hash``: SHA-256 of the prompt bundle all variants use.
    - ``variants``: mapping of variant name (``B0`` baseline, ``B1``/``B2``/``B3``
      enhanced/ablations) to its configuration dict.
    - ``metrics_rubric``: metric definitions used to score every variant.
    """

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    manifest_id: str = Field(min_length=1, description="Unique id of this experiment.")
    created_at: datetime = Field(description="Freeze time, timezone-aware UTC.")
    target_snapshot_id: str = Field(
        min_length=1, description="Shared input snapshot id all variants consume."
    )
    model_config_hash: str = Field(
        pattern=_HASH_PATTERN, description="SHA-256 (lowercase hex) of the model config."
    )
    prompt_hash: str = Field(
        pattern=_HASH_PATTERN, description="SHA-256 (lowercase hex) of the prompt bundle."
    )
    variants: dict[str, dict[str, Any]] = Field(
        description="Variant name (B0 baseline, B1/B2/B3 enhanced) to configuration dict."
    )
    metrics_rubric: dict[str, Any] = Field(
        description="Metric definitions (metric to operator/threshold/weight) used to score variants."
    )

    @field_validator("created_at")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _require_core_variants(self) -> ExperimentManifest:
        missing = [name for name in REQUIRED_VARIANTS if name not in self.variants]
        if missing:
            raise ValueError(f"manifest is missing required variants: {', '.join(missing)}")
        baseline = self.variants.get("B0")
        if not baseline:
            raise ValueError("variant B0 (baseline) must have a non-empty configuration")
        return self
