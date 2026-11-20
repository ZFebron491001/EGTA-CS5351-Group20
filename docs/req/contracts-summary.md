# Contracts Summary — spec definitions for FR-05 audit & evaluation

This document is the **spec definition** of the public audit/evaluation contracts.
The tests on this branch import these types; the **implementation** (`src/egta/
contracts/audit.py`, `src/egta/contracts/evaluation.py`) is delivered in the
implementation PR. On this spec branch those imports raise `ModuleNotFoundError`
= **RED by design** (test-first). No `src/` file exists here.

Definitions below follow **D's** specification (Batch B). Where a field/structure
is still subject to **B**'s confirmation, it is marked `PENDING (B)`; if B's reply
differs, B's wins and this document is adjusted.

---

## 1. `egta.contracts.audit`

### Exceptions — base `AuditContractError(Exception)`

All exceptions derive from `AuditContractError` and carry structured attributes
(signature per D):

```python
class AuditContractError(Exception): ...

class ChainBroken(AuditContractError):
    # ChainBroken(run_id, expected_sequence, actual_sequence, reason)
    run_id: str
    expected_sequence: int
    actual_sequence: int
    reason: str

class DuplicateConflict(AuditContractError):
    # DuplicateConflict(run_id, event_id, existing_payload_hash, incoming_payload_hash)
    run_id: str
    event_id: str
    existing_payload_hash: str
    incoming_payload_hash: str

class PayloadMismatch(AuditContractError):
    # PayloadMismatch(run_id, event_id, stored_payload_hash, recomputed_payload_hash)
    run_id: str
    event_id: str
    stored_payload_hash: str
    recomputed_payload_hash: str

class AuditUnavailable(AuditContractError):
    # AuditUnavailable(run_id, operation, cause)
    run_id: str
    operation: str
    cause: str
```

Constructors take exactly those positional args (in that order) and expose them
as the attributes above. Tests instantiate them positionally and read attributes
to confirm the signature.

### `Receipt` — 12 fields (per D)

```python
class Receipt(BaseModel):
    schema_version: str
    receipt_id: str
    run_id: str
    event_id: str
    sequence: int
    payload_hash: str
    prev_event_hash: str
    chain_tip_hash: str
    persisted_at: datetime          # tz-aware UTC
    store_id: str
    transaction_id: str
    idempotency_key: str
```

Exactly these twelve fields; `extra="forbid"` (a 13th field is rejected).

### `AuditSink`

```python
class AuditSink(Protocol):
    def append(self, event: RunEvent) -> Receipt: ...
    def read(self, run_id: str) -> "AuditReader": ...   # see AuditReader

class AuditReader(Protocol):
    def read(self, run_id: str) -> list[RunEvent]: ...
```

`append(event)`:
- same `event_id` **and** identical content already present → returns the
  **existing** `Receipt` (idempotent, no new entry).
- same `event_id`, **different** content → raises `DuplicateConflict`.
- storage/anchor cannot be written → raises `AuditUnavailable` (**fail closed**:
  no partial write, no silent success).

### Free functions

```python
def recompute_payload_hash(event: RunEvent) -> str
    # canonical JSON (sort_keys=True, separators=(",", ":")), exclude
    # "payload_hash", SHA-256 lowercase hex. Deterministic.

def verify_payload(event: RunEvent) -> None
    # raise PayloadMismatch(run_id, event_id, stored, recomputed) on divergence.

def dedupe_events(events: list[RunEvent]) -> list[RunEvent]
    # collapse identical event_id + identical content to one (keep first);
    # identical id + different content -> DuplicateConflict.

def verify_chain(events: list[RunEvent], *, anchor: str | None = None) -> None
    # genesis prev_event_hash == ""; sequence gap-free from 0;
    # each prev_event_hash == previous payload_hash; payload binding on each.
    # anchor = trusted tip hash (or expected last_sequence) from an external
    # reference; if the chain's actual tip != anchor tip (or last sequence <
    # expected), raise ChainBroken -> detects TAIL TRUNCATION and whole-chain
    # replacement against a trusted anchor.
```

**Ordering constraints (per D):** the only ordering keys are `(run_id, sequence)`
and `(run_id, event_id)`. `verify_chain` uses the anchor's **expected tip /
expected last_sequence** to detect truncation.

---

## 2. `egta.contracts.evaluation`

`incomplete` is a **status**, never an exception. Raising is explicitly wrong.

```python
class CompletionStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"
    REVIEW = "REVIEW"
    FAILED = "FAILED"

class IncompleteReason(StrEnum):
    MANIFEST_MISMATCH = "MANIFEST_MISMATCH"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    PROMPT_MISMATCH = "PROMPT_MISMATCH"
    CODE_MISMATCH = "CODE_MISMATCH"
    MISSING_RESULT = "MISSING_RESULT"
    # MISSING_USAGE: PENDING (D) — may be added to this enum; see D's text.

class EvaluationResult(BaseModel):
    ...
    completion_status: CompletionStatus
    incomplete_reason: IncompleteReason | None = None
    # ... (other result fields per implementation)
```

Rules:
- A manifest mismatch (snapshot/model/prompt; code/policy when available) yields
  `completion_status=INCOMPLETE` with the matching `incomplete_reason` — returned
  as data, **not raised**, and the pair is **not counted as a win**.
- `BLOCKED`/`REVIEW`/`FAILED` are statuses too, distinct from a valid `HOLD`.

---

## 3. `ExperimentManifest` rubric & variants (B's decisions)

- `variants` must contain **all four** `B0/B1/B2/B3`, each non-empty; unknown keys
  (e.g. `B9`) are rejected.
- `metrics_rubric: dict[str, MetricDef]` — each `MetricDef` requires seven fields:
  `metric, operator, threshold, verification, source, aggregation, unit`.
- `quality_rubric: QualityRubric` — **independent field** (PENDING (B): if B
  reverts to nested-in-metrics_rubric, adjust here and in tests). Fields:
  `levels: list[str]` (≥3), `double_blind: bool`,
  `third_party_adjudication: bool`, `llm_judge_assist: bool`.
- **code_hash / policy_hash:** `ExperimentManifest` currently has neither. The
  code/policy mismatch test is **PENDING (B)** pending B's confirmation on whether
  the manifest adds `code_hash`/`policy_hash`. Until then only snapshot/model/
  prompt mismatch are asserted.

## 4. RunEvent.metrics validation (target contract)

`metrics` values must be JSON-safe: non-finite floats (`NaN`, `±inf`) and
non-serializable objects are **rejected at construction** (`ValidationError`) by a
metrics validator (added in implementation). This replaces the earlier "pinned
current null behavior" tests.

---

## 5. Approval binding (corrected)

- `test_content_commit` + `aggregate_sha256` are the only commit/hash fields stored
  in `docs/approvals/test-hash-FR-05-contracts.txt`.
- The **authoritative reviewed head** is the GitHub review `commit_id`, not stored
  in the file.
- The **merge commit** is recorded in the external registry / CI artifact / PR
  comment.
- After approval, this file must not be pushed (stale-approval trap).
