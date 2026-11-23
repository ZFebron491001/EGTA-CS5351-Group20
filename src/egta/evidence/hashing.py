"""Local canonical hashing for the evidence pack (module A, FR-01).

Why this file exists
--------------------
``pack_hash`` must equal what the risk gate recomputes, or the gate rejects the
pack as ``INTEGRITY_VIOLATION``. The risk gate's canonical helper lives in
``egta.risk_gate.canonical``, but AGENTS.md §3 / NFR-06 forbid module ``evidence``
from importing another business module (``risk_gate``). Copying the shared helper
into ``egta.contracts`` would be a contracts change owned by B.

So module A computes the evidence hash itself, **byte-identically** to
``egta.risk_gate.canonical.recompute_evidence_hash``. The equivalence is not a
claim: ``test/offline/evidence/test_pack.py::test_pack_hash_matches_risk_gate_canonical``
imports the risk-gate helper (tests may reference other modules) and asserts
equality over several fixtures. If the risk gate ever changes its canonical form,
that test fails and both sides must change together.

The hasher is also injectable: ``build_pack(..., hasher=...)`` lets a caller pass
an alternative ``pack -> hex`` function; the default is :func:`canonical_pack_hash`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any


def _normalize(value: Any) -> Any:
    """Canonical JSON normalization — byte-identical to risk_gate.canonical._normalize."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.isoformat()
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (tuple, list)):
        return [_normalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_normalize(item) for item in value)
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda pair: str(pair[0]))
        return {str(key): _normalize(item) for key, item in items}
    if hasattr(value, "to_canonical_dict"):
        return _normalize(value.to_canonical_dict())
    raise TypeError(f"cannot canonicalize {type(value)!r}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _item_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return {
            "evidence_id": item.get("evidence_id"),
            "source_uri": item.get("source_uri"),
            "published_at": item.get("published_at"),
            "fetched_at": item.get("fetched_at"),
            "content_hash": item.get("content_hash"),
            "excerpt": item.get("excerpt"),
            "availability": item.get("availability"),
            "trust_label": item.get("trust_label"),
        }
    return {
        "evidence_id": getattr(item, "evidence_id", None),
        "source_uri": getattr(item, "source_uri", None),
        "published_at": getattr(item, "published_at", None),
        "fetched_at": getattr(item, "fetched_at", None),
        "content_hash": getattr(item, "content_hash", None),
        "excerpt": getattr(item, "excerpt", None),
        "availability": getattr(item, "availability", None),
        "trust_label": getattr(item, "trust_label", None),
    }


def evidence_fields(pack: Any) -> dict[str, Any]:
    """The canonical field set hashed for a pack — identical to the risk gate's."""
    items = getattr(pack, "items", ()) or ()
    excluded = getattr(pack, "excluded_items", ()) or ()
    return {
        "run_id": getattr(pack, "run_id", None),
        "snapshot_id": getattr(pack, "snapshot_id", None),
        "items": tuple(_item_dict(item) for item in items),
        "excluded_items": tuple(_item_dict(item) for item in excluded),
        "cutoff": getattr(pack, "cutoff", None),
    }


def canonical_pack_hash(pack: Any) -> str:
    """SHA-256 over the canonical evidence fields (== risk gate's recompute)."""
    return hashlib.sha256(_canonical_bytes(evidence_fields(pack))).hexdigest()


__all__ = ["canonical_pack_hash", "evidence_fields"]
