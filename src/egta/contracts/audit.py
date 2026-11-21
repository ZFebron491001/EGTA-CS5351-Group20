"""Public audit contract (implements the approved FR-05 spec).

# Implements: FR-05, NFR-08, NFR-09

Defines the typed exceptions (``AuditContractError`` base), the 12-field
``Receipt``, the ``AuditSink``/``AuditReader`` protocols, the free functions
``recompute_payload_hash`` / ``verify_payload`` / ``verify_chain`` /
``dedupe_events``, and a real ``SqliteAuditSink`` (fail-closed, idempotent,
cross-run-unique). Definitions: docs/req/contracts-summary.md §1.

Tamper-evidence: ``verify_chain`` proves internal consistency (payload binding,
gap-free ``(run_id, sequence)``, ``prev_event_hash`` links) and, given an
``anchor`` (external trusted tip), detects tail truncation / whole-chain
replacement. The chain alone is not authenticity against a log-rewriting
attacker; an external anchor is required for that.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from egta.contracts.events import RunEvent


class AuditContractError(Exception):
    """Base for all audit-contract failures."""


class ChainBroken(AuditContractError):
    """A chain link, sequence, genesis, or anchor-tip check failed."""

    def __init__(self, run_id: str, expected_sequence: int, actual_sequence: int, reason: str):
        self.run_id = run_id
        self.expected_sequence = expected_sequence
        self.actual_sequence = actual_sequence
        self.reason = reason
        super().__init__(
            f"ChainBroken(run_id={run_id!r}, expected={expected_sequence}, "
            f"actual={actual_sequence}, reason={reason!r})"
        )


class DuplicateConflict(AuditContractError):
    """Same (run_id, event_id) seen with different content."""

    def __init__(self, run_id: str, event_id: str,
                 existing_payload_hash: str, incoming_payload_hash: str):
        self.run_id = run_id
        self.event_id = event_id
        self.existing_payload_hash = existing_payload_hash
        self.incoming_payload_hash = incoming_payload_hash
        super().__init__(
            f"DuplicateConflict(run_id={run_id!r}, event_id={event_id!r})"
        )


class PayloadMismatch(AuditContractError):
    """A recomputed payload hash does not match the stored one."""

    def __init__(self, run_id: str, event_id: str,
                 stored_payload_hash: str, recomputed_payload_hash: str):
        self.run_id = run_id
        self.event_id = event_id
        self.stored_payload_hash = stored_payload_hash
        self.recomputed_payload_hash = recomputed_payload_hash
        super().__init__(
            f"PayloadMismatch(run_id={run_id!r}, event_id={event_id!r})"
        )


class AuditUnavailable(AuditContractError):
    """The audit store/anchor could not be written (fail-closed)."""

    def __init__(self, run_id: str, operation: str, cause: str):
        self.run_id = run_id
        self.operation = operation
        self.cause = cause
        super().__init__(
            f"AuditUnavailable(run_id={run_id!r}, operation={operation!r}, cause={cause!r})"
        )


class Receipt(BaseModel):
    """Proof of a persisted append; exactly twelve fields."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    receipt_id: str
    run_id: str
    event_id: str
    sequence: int
    payload_hash: str
    prev_event_hash: str
    chain_tip_hash: str
    persisted_at: datetime
    store_id: str
    transaction_id: str
    idempotency_key: str


def recompute_payload_hash(event: RunEvent) -> str:
    """Canonical SHA-256 (lowercase hex) of the event's content, excluding hash."""
    payload = event.model_dump(mode="json", exclude={"payload_hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_payload(event: RunEvent) -> None:
    """Raise ``PayloadMismatch`` if the stored hash is not the recomputed one."""
    recomputed = recompute_payload_hash(event)
    if recomputed != event.payload_hash:
        raise PayloadMismatch(event.run_id, event.event_id, event.payload_hash, recomputed)


def dedupe_events(events: list[RunEvent]) -> list[RunEvent]:
    """Collapse identical (run_id, event_id) to one; conflict -> DuplicateConflict.

    Preserves first-seen order.
    """
    seen: dict[tuple[str, str], str] = {}
    out: list[RunEvent] = []
    for event in events:
        content = recompute_payload_hash(event)
        key = (event.run_id, event.event_id)
        if key in seen:
            if seen[key] != content:
                raise DuplicateConflict(event.run_id, event.event_id, seen[key], content)
            continue
        seen[key] = content
        out.append(event)
    return out


def verify_chain(events: list[RunEvent], *, anchor: str | None = None) -> None:
    """Verify payload binding, gap-free sequence, links, and an optional anchor.

    Args:
        events: the run's events (any order).
        anchor: trusted external tip hash. If given and the chain's actual tip
            differs, tail truncation / whole-chain replacement is detected.

    Raises:
        DuplicateConflict, PayloadMismatch, ChainBroken.
    """
    if not events:
        return
    events = dedupe_events(events)
    ordered = sorted(events, key=lambda e: (e.run_id, e.sequence))
    run_id = ordered[0].run_id
    if ordered[0].prev_event_hash != "":
        raise ChainBroken(run_id, 0, ordered[0].sequence, "genesis prev_event_hash not empty")
    last = -1
    for event in ordered:
        if event.sequence != last + 1:
            raise ChainBroken(event.run_id, last + 1, event.sequence, "sequence gap")
        last = event.sequence
        verify_payload(event)
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if cur.prev_event_hash != prev.payload_hash:
            raise ChainBroken(cur.run_id, prev.sequence + 1, cur.sequence, "link broken")
    if anchor is not None and ordered[-1].payload_hash != anchor:
        raise ChainBroken(run_id, last, last, "tip != anchor (tail truncation)")


class AuditReader(Protocol):
    """Read one run's events, sorted by sequence."""

    def read(self, run_id: str) -> list[RunEvent]: ...


class AuditSink(Protocol):
    """Append receipts and open per-run readers (hybrid read API)."""

    def append(self, event: RunEvent) -> Receipt: ...

    def read(self, run_id: str) -> AuditReader: ...


class SqliteAuditReader:
    """``AuditReader`` backed by a SQLite audit store."""

    def __init__(self, conn: sqlite3.Connection, run_id: str):
        self._conn = conn
        self._run_id = run_id

    def read(self, run_id: str) -> list[RunEvent]:
        rows = self._conn.execute(
            "SELECT payload FROM events WHERE run_id = ? ORDER BY sequence ASC",
            (run_id,),
        ).fetchall()
        return [RunEvent.model_validate_json(r[0]) for r in rows]


class SqliteAuditSink:
    """Real, fail-closed SQLite audit sink.

    One transaction per ``append`` writes the event and its receipt atomically.
    UNIQUE(run_id, sequence) and UNIQUE(run_id, event_id) enforce the cross-run
    identity constraint ``(run_id, sequence)``/``(run_id, event_id)``. Identical
    re-append returns the existing ``Receipt`` (idempotent by ``idempotency_key``);
    different content under the same ``(run_id, event_id)`` raises
    ``DuplicateConflict``; any storage error raises ``AuditUnavailable`` and the
    transaction is rolled back (no partial write).
    """

    store_id = "sqlite"

    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                run_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (run_id, event_id),
                UNIQUE (run_id, sequence)
            );
            CREATE TABLE IF NOT EXISTS receipts (
                idempotency_key TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )

    def append(self, event: RunEvent) -> Receipt:
        content = recompute_payload_hash(event)
        key = f"{event.run_id}:{event.event_id}"
        try:
            with self._conn:  # transaction: commit on success, rollback on error
                row = self._conn.execute(
                    "SELECT content_hash, payload FROM receipts WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is not None:
                    existing_content, payload_json = row
                    if existing_content != content:
                        raise DuplicateConflict(
                            event.run_id, event.event_id, existing_content, content
                        )
                    return Receipt.model_validate_json(payload_json)

                receipt = Receipt(
                    schema_version="1.0",
                    receipt_id=f"rcpt-{event.run_id}-{event.event_id}",
                    run_id=event.run_id,
                    event_id=event.event_id,
                    sequence=event.sequence,
                    payload_hash=event.payload_hash,
                    prev_event_hash=event.prev_event_hash,
                    chain_tip_hash=content,
                    persisted_at=datetime.now(UTC),
                    store_id=self.store_id,
                    transaction_id=key,
                    idempotency_key=key,
                )
                self._conn.execute(
                    "INSERT INTO events (run_id, event_id, sequence, content_hash, payload) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (event.run_id, event.event_id, event.sequence, content,
                     event.model_dump_json()),
                )
                self._conn.execute(
                    "INSERT INTO receipts (idempotency_key, run_id, event_id, payload) "
                    "VALUES (?, ?, ?, ?)",
                    (key, event.run_id, event.event_id, receipt.model_dump_json()),
                )
                return receipt
        except AuditContractError:
            raise
        except sqlite3.Error as exc:
            raise AuditUnavailable(event.run_id, "append", str(exc)) from exc

    def read(self, run_id: str) -> AuditReader:
        return SqliteAuditReader(self._conn, run_id)
