"""Budget Governor: admission control for external model calls (FR-02 / INV-03).

Public API (frozen by plan §5.1):

    BudgetGovernor.reserve(call_spec) -> Reservation | BudgetDenied
    BudgetGovernor.settle(reservation_id, actual_usage_or_unknown) -> BudgetState

A call must reserve budget BEFORE it is sent; the reservation is only released when
the call's usage is settled. Unknown usage (``settle(id, None)``) keeps the whole
reservation held (and is persisted), and a not-yet-settled reservation keeps its
amount held, so a governor bug that refunds early is caught by the frozen spec.

Construction (``BudgetGovernor(limits=..., db_path=...)``) is the agreed interface
for this implementation; reserve/settle persistence lives in ``ledger`` (SQLite).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from egta.budget.ledger import (
    BudgetInputError,
    BudgetLedger,
    SettlementConflict,
    UnknownReservation,
)


@dataclass(frozen=True)
class Reservation:
    """A granted budget reservation. ``reservation_id`` identifies it for settle."""

    reservation_id: str


@dataclass(frozen=True)
class BudgetDenied:
    """A refusal: the call would exceed at least one budget axis."""

    reason_code: str = "BUDGET_DENIED"


@dataclass(frozen=True)
class BudgetState:
    """Result of a settle, reflecting the ACTUAL persisted outcome.

    ``settled`` is True only when a settle changed persisted state. ``usage_unknown``
    is True when an unknown-usage settle was recorded (reservation still held).
    """

    reservation_id: str
    settled: bool
    usage_unknown: bool = False


class BudgetGovernor:
    def __init__(self, *, limits: dict[str, Any], db_path: str | Path) -> None:
        self._ledger = BudgetLedger(limits=limits, db_path=db_path)

    def reserve(self, call_spec: dict[str, Any]) -> Reservation | BudgetDenied:
        rid = self._ledger.reserve(call_spec)
        if not rid:
            return BudgetDenied()
        return Reservation(reservation_id=rid)

    def settle(
        self, reservation_id: str, actual_usage_or_unknown: dict[str, Any] | None
    ) -> BudgetState:
        """Settle a reservation; the returned state reflects what was persisted.

        Raises ``UnknownReservation`` for a missing id, ``BudgetInputError`` for
        invalid usage, and ``SettlementConflict`` for a conflicting re-settle.
        """
        changed = self._ledger.settle(reservation_id, actual_usage_or_unknown)
        return BudgetState(
            reservation_id=reservation_id,
            settled=changed,
            usage_unknown=actual_usage_or_unknown is None,
        )


__all__ = [
    "BudgetDenied",
    "BudgetGovernor",
    "BudgetInputError",
    "BudgetState",
    "Reservation",
    "SettlementConflict",
    "UnknownReservation",
]
