"""SQLite-backed budget ledger: atomic reserve/settle for the three budget axes.

# Implements: FR-02, INV-03, §5.3 (persist every reserve/settle; unknown usage does
# not release the reservation).

Axes: tokens (int >= 0), calls (int >= 0), cost (Decimal >= 0, finite). A reservation
holds an amount on each axis until that axis is settled. `reserve` admits only if
HOLD + request fits under every limit, inside one BEGIN IMMEDIATE transaction so two
concurrent callers cannot take the last slot.

Settlement is per-axis and persisted:
- a settled axis stores its ACTUAL used amount and marks that axis settled; the
  unused portion is released for that axis only;
- an unnamed axis stays held (unknown), so it can be settled later;
- re-settling a settled axis with the SAME value is a no-op; with a DIFFERENT value
  it is refused as a conflict (never refunds twice);
- `settle(id, unknown)` records an "attempted, usage unknown" flag and keeps the
  reservation fully held.

Invalid input (negative/bool/non-int counts, non-finite/negative money, unknown
reservation id) never mutates the ledger and is reported to the caller.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS limits (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    max_total_tokens INTEGER NOT NULL,
    max_calls INTEGER NOT NULL,
    max_cost_usd TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    tokens INTEGER NOT NULL,          -- held tokens (settled: actual used)
    calls INTEGER NOT NULL,
    cost_usd TEXT NOT NULL,
    tokens_settled INTEGER NOT NULL DEFAULT 0,
    calls_settled INTEGER NOT NULL DEFAULT 0,
    cost_settled INTEGER NOT NULL DEFAULT 0,
    unknown_settle INTEGER NOT NULL DEFAULT 0   -- an unknown-usage settle was recorded
);
"""

AXES = ("tokens", "calls", "cost_usd")


class BudgetInputError(ValueError):
    """Invalid limits/call_spec/usage; the ledger is not changed."""


class UnknownReservation(KeyError):
    """No reservation with the given id."""


class SettlementConflict(ValueError):
    """An already-settled axis is re-settled with a different value."""


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise BudgetInputError(f"{field} must not be a bool")
    if isinstance(value, int):
        n = value
    else:
        raise BudgetInputError(f"{field} must be an int, got {type(value).__name__}")
    if n < 0:
        raise BudgetInputError(f"{field} must be >= 0, got {n}")
    return n


def _money(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise BudgetInputError(f"{field} must not be a bool")
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BudgetInputError(f"{field} is not a Decimal: {value!r}") from exc
    if not d.is_finite():
        raise BudgetInputError(f"{field} must be finite, got {value!r}")
    if d < 0:
        raise BudgetInputError(f"{field} must be >= 0, got {d}")
    return d


def _exact_add(a: Decimal, b: Decimal) -> Decimal:
    """Add two Decimals WITHOUT the global context silently rounding.

    Default context precision (28) drops a tiny addend (e.g. 1 + 1E-29 == 1), which
    would make a sub-cent over-budget request fit. Compute under a precision large
    enough for both operands' digits so the sum is exact.
    """
    digits = max(len(a.as_tuple().digits), len(b.as_tuple().digits)) + abs(
        a.as_tuple().exponent
    ) + abs(b.as_tuple().exponent) + 8
    with localcontext() as ctx:
        ctx.prec = max(ctx.prec, digits)
        return a + b


def _sum_money(values: list[str]) -> Decimal:
    total = Decimal(0)
    for v in values:
        total = _exact_add(total, Decimal(v))
    return total


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(Path(db_path)), timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@dataclass(frozen=True)
class Held:
    tokens: int
    calls: int
    cost_usd: Decimal


class BudgetLedger:
    def __init__(self, *, limits: dict[str, Any], db_path: str | Path) -> None:
        # Validate limits before persisting; invalid input must not touch the DB.
        self._max_tokens = _count(limits["max_total_tokens"], "max_total_tokens")
        self._max_calls = _count(limits["max_calls"], "max_calls")
        self._max_cost = _money(limits["max_cost_usd"], "max_cost_usd")
        self._db_path = Path(db_path)

        conn = connect(self._db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT max_total_tokens, max_calls, max_cost_usd FROM limits WHERE id=1"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO limits (id, max_total_tokens, max_calls, max_cost_usd) "
                    "VALUES (1, ?, ?, ?)",
                    (self._max_tokens, self._max_calls, format(self._max_cost, "f")),
                )
            else:
                persisted = (
                    int(row["max_total_tokens"]),
                    int(row["max_calls"]),
                    Decimal(row["max_cost_usd"]),
                )
                if persisted != (self._max_tokens, self._max_calls, self._max_cost):
                    conn.execute("ROLLBACK")
                    raise BudgetInputError(
                        "limits differ from the ones already persisted for this database: "
                        f"persisted={persisted!r} requested="
                        f"{(self._max_tokens, self._max_calls, self._max_cost)!r}"
                    )
            conn.execute("COMMIT")
        finally:
            conn.close()

    @staticmethod
    def _validate_usage(actual_usage: dict[str, Any]) -> None:
        if "tokens" in actual_usage:
            _count(actual_usage["tokens"], "usage.tokens")
        if "calls" in actual_usage:
            _count(actual_usage["calls"], "usage.calls")
        if "cost_usd" in actual_usage:
            _money(actual_usage["cost_usd"], "usage.cost_usd")

    @staticmethod
    def _held(conn: sqlite3.Connection) -> Held:
        row = conn.execute(
            "SELECT COALESCE(SUM(tokens),0) AS t, COALESCE(SUM(calls),0) AS c "
            "FROM reservations"
        ).fetchone()
        cost = _sum_money([r[0] for r in conn.execute("SELECT cost_usd FROM reservations")])
        return Held(int(row["t"]), int(row["c"]), cost)

    def reserve(self, call_spec: dict[str, Any]) -> str:
        """Admit the call (return reservation id) or return ``""`` on refusal.

        ``""`` means refused (the governor maps it to ``BudgetDenied``); invalid input
        raises ``BudgetInputError``. Check-and-take is one transaction.
        """
        want_tokens = _count(call_spec["max_tokens"], "call_spec.max_tokens")
        want_calls = _count(call_spec["max_calls"], "call_spec.max_calls")
        if want_calls < 1:
            # Every reserve is for one external model call, so it must occupy at
            # least one call slot. ``limits.max_calls = 0`` stays a valid
            # zero-budget configuration: it will simply refuse every such call.
            raise BudgetInputError("call_spec.max_calls must be >= 1 (one call per reserve)")
        want_cost = _money(call_spec["max_cost_usd"], "call_spec.max_cost_usd")

        conn = connect(self._db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            held = self._held(conn)
            fits = (
                held.tokens + want_tokens <= self._max_tokens
                and held.calls + want_calls <= self._max_calls
                and _exact_add(held.cost_usd, want_cost) <= self._max_cost
            )
            if not fits:
                conn.execute("ROLLBACK")
                return ""
            rid = "res-" + uuid.uuid4().hex
            conn.execute(
                "INSERT INTO reservations "
                "(reservation_id, tokens, calls, cost_usd, "
                " tokens_settled, calls_settled, cost_settled, unknown_settle) "
                "VALUES (?, ?, ?, ?, 0, 0, 0, 0)",
                (rid, want_tokens, want_calls, format(want_cost, "f")),
            )
            conn.execute("COMMIT")
            return rid
        finally:
            conn.close()

    def settle(self, reservation_id: str, actual_usage: dict[str, Any] | None) -> bool:
        """Settle named axes; return True iff a persisted change was made.

        ``None`` -> unknown usage: record the attempt, keep the reservation held,
        return False (nothing released). Unknown id -> ``UnknownReservation``.
        Re-settling a settled axis with the same value -> idempotent no-op (False);
        with a different value -> ``SettlementConflict``.
        """
        if actual_usage is not None:
            self._validate_usage(actual_usage)

        conn = connect(self._db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT tokens, calls, cost_usd, "
                "tokens_settled, calls_settled, cost_settled "
                "FROM reservations WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                raise UnknownReservation(reservation_id)

            if actual_usage is None:
                # Persist the "attempted, usage unknown" fact; reservation stays held.
                conn.execute(
                    "UPDATE reservations SET unknown_settle=1 WHERE reservation_id=?",
                    (reservation_id,),
                )
                conn.execute("COMMIT")
                return False

            new = {
                "tokens": int(row["tokens"]),
                "calls": int(row["calls"]),
                "cost_usd": Decimal(row["cost_usd"]),
            }
            settled = {
                "tokens": int(row["tokens_settled"]),
                "calls": int(row["calls_settled"]),
                "cost_usd": int(row["cost_settled"]),
            }
            changed = False
            for axis in AXES:
                if axis not in actual_usage:
                    continue
                actual = (
                    _money(actual_usage[axis], f"usage.{axis}")
                    if axis == "cost_usd"
                    else _count(actual_usage[axis], f"usage.{axis}")
                )
                if settled[axis]:
                    if new[axis] != actual:
                        conn.execute("ROLLBACK")
                        raise SettlementConflict(
                            f"{axis} already settled as {new[axis]!r}; "
                            f"conflicting re-settle {actual!r}"
                        )
                    continue  # idempotent same-value retry
                new[axis] = actual  # held := actual used (release the unused part)
                settled[axis] = 1
                changed = True
            if not changed:
                conn.execute("ROLLBACK")
                return False
            conn.execute(
                "UPDATE reservations SET tokens=?, calls=?, cost_usd=?, "
                "tokens_settled=?, calls_settled=?, cost_settled=? WHERE reservation_id=?",
                (
                    new["tokens"],
                    new["calls"],
                    format(new["cost_usd"], "f"),
                    settled["tokens"],
                    settled["calls"],
                    settled["cost_usd"],
                    reservation_id,
                ),
            )
            conn.execute("COMMIT")
            return True
        finally:
            conn.close()


__all__ = [
    "BudgetInputError",
    "BudgetLedger",
    "Held",
    "SettlementConflict",
    "UnknownReservation",
]
