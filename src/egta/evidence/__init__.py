"""Evidence module (A): point-in-time admissibility and pack assembly (FR-01 / INV-02).

    from egta.evidence import build_pack, validate_claims, InvalidCitation

``build_pack`` turns raw provider items into an immutable evidence pack and its
exclusions; ``validate_claims`` fails closed on a dangling citation.
"""

from __future__ import annotations

from egta.evidence.pack import InvalidCitation, build_pack, validate_claims

__all__ = ["InvalidCitation", "build_pack", "validate_claims"]
