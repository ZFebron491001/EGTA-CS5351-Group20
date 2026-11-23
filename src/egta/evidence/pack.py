"""Pack-level evidence assembly for FR-01 / INV-02 (module A).

``build_pack`` turns raw provider items into an immutable :class:`EvidencePack`
and its :class:`~egta.contracts.ExcludedItem` list; ``validate_claims`` fails
closed on a claim that cites an evidence id the pack does not contain.

# Implements: FR-01 (evidence pack), INV-02 (point-in-time admissibility)

Design decisions frozen by the approved pack-level spec
(``test/offline/evidence/test_pack.py``, PR #25) and the classification-precedence
spec (``test/offline/evidence/test_pack_precedence.py``, #51):

* ``pack_hash`` is **computed here**, never supplied by a caller. The default
  hasher is :func:`egta.evidence.hashing.canonical_pack_hash`, which is
  byte-identical to ``egta.risk_gate.canonical.recompute_evidence_hash`` (the risk
  gate recomputes and rejects a mismatch as ``INTEGRITY_VIOLATION``;
  ``test_pack_hash_matches_risk_gate_canonical`` proves the equality). The hasher
  is injectable via ``build_pack(..., hasher=...)`` so module A does not import the
  risk-gate module (NFR-06 / AGENTS §3).
* Claim citations use the **full** evidence id ``<run_id>-<case_local_id>``, matching
  the risk gate's index.
* A dangling citation raises :class:`InvalidCitation` carrying
  ``ReasonCode.INVALID_CITATION`` and naming the bad id.
* Classification order is **integrity -> staleness -> time -> dedupe**, first match
  wins: a tampered cache item is ``INTEGRITY_VIOLATION`` (not STALE); a well-formed
  cache item is ``STALE_DATA`` (E-26); a future cache item is ``STALE_DATA``
  (cache staged before the time filter, still excluded so INV-02
  ``future_items_admitted == 0`` holds); a future non-cache item is ``FUTURE_DATA``.
* ``pack.items`` preserves raw input order. A duplicate (same ``source_uri`` +
  publication instant + ``content_hash``) is silently collapsed.
* A caller-supplied ``conflict_key`` groups *more than one* admitted item.

Pure time filtering (E-13..E-20, E-27, E-28, E-31) is owned by
:func:`egta.evidence.time_policy.is_admissible`; this module only wires its verdicts
into the pack.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from egta.contracts import Availability, EvidenceItem, EvidencePack, ExcludedItem, RunSpec
from egta.contracts.events import ReasonCode
from egta.evidence.hashing import canonical_pack_hash
from egta.evidence.time_policy import is_admissible

_TIME_GRANULARITY_NONE = "none"
_INTEGRITY_AVAILABILITY = Availability.UNAVAILABLE
_PROVIDER_LOCAL_ID = "provider"
_HASH_ZERO = "0" * 64

PackHasher = Callable[[EvidencePack], str]


class InvalidCitation(Exception):
    """A claim cites an evidence id absent from the pack (``INVALID_CITATION``)."""

    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id
        self.reason_code = ReasonCode.INVALID_CITATION
        super().__init__(
            f"{ReasonCode.INVALID_CITATION.value}: claim cites unknown evidence id "
            f"{evidence_id!r}"
        )


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _publication_instant(published_at: Any) -> Any:
    """Normalize ``published_at`` for dedupe keys only (never mutates the item)."""
    if isinstance(published_at, datetime):
        return published_at.astimezone(UTC) if published_at.tzinfo is not None else published_at
    if isinstance(published_at, date):
        return published_at
    if isinstance(published_at, str):
        try:
            parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            return published_at
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed
    return published_at


def _raw_get(raw: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return raw.get(key, default)


def _is_cache(raw: Mapping[str, Any]) -> bool:
    return _raw_get(raw, "source_type") == "cache"


def _is_tampered(raw: Mapping[str, Any]) -> bool:
    excerpt = _raw_get(raw, "excerpt")
    content_hash = _raw_get(raw, "content_hash")
    if not isinstance(excerpt, str) or not isinstance(content_hash, str):
        return False
    return _sha256_hex(excerpt) != content_hash


def _dedupe_key(raw: Mapping[str, Any]) -> tuple[Any, Any, Any]:
    return (
        _raw_get(raw, "source_uri"),
        _publication_instant(_raw_get(raw, "published_at")),
        _raw_get(raw, "content_hash"),
    )


def _excluded(case_local_id: str, reason: ReasonCode, availability: Availability) -> ExcludedItem:
    return ExcludedItem(
        case_local_id=case_local_id,
        availability=availability,
        reason_code=reason,
    )


def _to_evidence_item(
    run_id: str,
    raw: Mapping[str, Any],
    *,
    conflict_group: str | None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"{run_id}-{raw['case_local_id']}",
        source_uri=raw["source_uri"],
        published_at=raw["published_at"],
        fetched_at=raw["fetched_at"],
        content_hash=raw["content_hash"],
        excerpt=raw["excerpt"],
        availability=Availability.AVAILABLE,
        trust_label=raw["trust_label"],
        reason_code=None,
        conflict_group=conflict_group,
    )


def _time_verdict(raw: Mapping[str, Any], run_spec: RunSpec):
    granularity = _raw_get(raw, "time_granularity", _TIME_GRANULARITY_NONE)
    return is_admissible(
        published_at=_raw_get(raw, "published_at"),
        time_granularity=granularity if isinstance(granularity, str) else _TIME_GRANULARITY_NONE,
        as_of=run_spec.as_of,
    )


def _assemble(
    run_spec: RunSpec,
    raw_items: Iterable[Mapping[str, Any]],
    *,
    provider_error: Any,
    conflict_key: str | None,
) -> tuple[list[EvidenceItem], list[ExcludedItem]]:
    exclusions: list[ExcludedItem] = []

    if provider_error is not None:
        exclusions.append(
            _excluded(_PROVIDER_LOCAL_ID, ReasonCode.VENDOR_UNAVAILABLE, Availability.UNREACHABLE)
        )

    admitted_raw: list[Mapping[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()

    # Precedence (frozen by trace-FR-01-pack-precedence.md):
    #   1. integrity -> 2. staleness -> 3. time -> 4. dedupe (first match wins).
    for raw in raw_items:
        local_id = _raw_get(raw, "case_local_id")
        if _is_tampered(raw):
            exclusions.append(
                _excluded(local_id, ReasonCode.INTEGRITY_VIOLATION, _INTEGRITY_AVAILABILITY)
            )
            continue
        if _is_cache(raw):
            exclusions.append(_excluded(local_id, ReasonCode.STALE_DATA, Availability.STALE))
            continue
        verdict = _time_verdict(raw, run_spec)
        if not verdict.admissible:
            exclusions.append(
                _excluded(local_id, ReasonCode(verdict.reason_code), Availability.UNAVAILABLE)
            )
            continue
        key = _dedupe_key(raw)
        if key in seen:
            continue
        seen.add(key)
        admitted_raw.append(raw)

    group = conflict_key if (conflict_key is not None and len(admitted_raw) > 1) else None
    items = [
        _to_evidence_item(run_spec.run_id, raw, conflict_group=group) for raw in admitted_raw
    ]
    return items, exclusions


def _pack_with_hash(
    run_spec: RunSpec,
    items: list[EvidenceItem],
    exclusions: list[ExcludedItem],
    hasher: PackHasher,
) -> EvidencePack:
    # Build with a placeholder, then bind pack_hash to the canonical recomputation.
    # The hasher ignores pack_hash, so the placeholder never affects the digest.
    provisional = EvidencePack(
        run_id=run_spec.run_id,
        snapshot_id=run_spec.snapshot_id,
        items=items,
        excluded_items=exclusions,
        cutoff=run_spec.as_of,
        pack_hash=_HASH_ZERO,
    )
    return provisional.model_copy(update={"pack_hash": hasher(provisional)})


def build_pack(
    run_spec: RunSpec,
    raw_items: Iterable[Mapping[str, Any]],
    *,
    provider_error: Any = None,
    conflict_key: str | None = None,
    hasher: PackHasher | None = None,
) -> EvidencePack:
    """Assemble an :class:`EvidencePack` from raw provider items (FR-01 / INV-02).

    ``hasher`` defaults to :func:`egta.evidence.hashing.canonical_pack_hash`, which
    is byte-identical to the risk gate's recompute. ``provider_error`` (any non-None
    value) records a provider-level exclusion (``VENDOR_UNAVAILABLE``/``unreachable``).
    ``conflict_key`` groups all admitted items when more than one remains.
    """
    items, exclusions = _assemble(
        run_spec,
        raw_items,
        provider_error=provider_error,
        conflict_key=conflict_key,
    )
    return _pack_with_hash(run_spec, items, exclusions, hasher or canonical_pack_hash)


def _claim_evidence_ids(claim: Any) -> Iterable[str]:
    if isinstance(claim, Mapping):
        return claim.get("evidence_ids", ()) or ()
    return getattr(claim, "evidence_ids", ()) or ()


def validate_claims(pack: EvidencePack, claims: Iterable[Any]) -> None:
    """Fail closed if any claim cites an evidence id absent from ``pack``."""
    known = {item.evidence_id for item in pack.items}
    for claim in claims:
        for evidence_id in _claim_evidence_ids(claim):
            if evidence_id not in known:
                raise InvalidCitation(str(evidence_id))


__all__ = ["InvalidCitation", "build_pack", "validate_claims"]
