# Contracts Summary — spec definitions for FR-05 audit & evaluation

This is the **spec definition** of the public audit/evaluation contracts. The
tests on this branch import these types; the implementation
(`src/egta/contracts/{events,audit,evaluation,manifest}.py`) is delivered in the
implementation PR. On this spec branch the imports raise `ModuleNotFoundError` =
**RED by design** (test-first). No `src/` file exists here.

Definitions follow **D's** specification (final round) and **B's** confirmations.
`PENDING (D)` / `PENDING (B)` mark items not yet frozen.

---

## 1. `egta.contracts.audit`

### Exceptions — base `AuditContractError(Exception)`
```python
class AuditContractError(Exception): ...
class ChainBroken(AuditContractError):        # (run_id, expected_sequence, actual_sequence, reason)
class DuplicateConflict(AuditContractError):  # (run_id, event_id, existing_payload_hash, incoming_payload_hash)
class PayloadMismatch(AuditContractError):    # (run_id, event_id, stored_payload_hash, recomputed_payload_hash)
class AuditUnavailable(AuditContractError):   # (run_id, operation, cause)
```
Each exposes those attributes in that order.

### `Receipt` — exactly 12 fields (D)
`schema_version, receipt_id, run_id, event_id, sequence, payload_hash,
prev_event_hash, chain_tip_hash, persisted_at, store_id, transaction_id,
idempotency_key`. `extra="forbid"`; typed (e.g. `sequence: int`, `persisted_at:
datetime` tz-aware); a 13th field is rejected.

### Sink / Reader — Option A (D item 3)
```python
class AuditSink(Protocol):
    def append(self, event: RunEvent) -> Receipt: ...
    def read(self, run_id: str) -> AuditReader: ...

class AuditReader(Protocol):
    def read(self, run_id: str) -> list[RunEvent]: ...   # sorted by (run_id, sequence)
```
- `append`: same `(run_id, event_id)` + identical content → existing `Receipt`
  (idempotent); same `(run_id, event_id)` + different content → `DuplicateConflict`;
  storage failure → `AuditUnavailable` **fail-closed** (no partial write, no silent
  success).
- Cross-run: same `event_id` under a **different** `run_id` is **not** a conflict
  (identity is `(run_id, event_id)`).
- `read(run_id)` returns only that run's events, sorted by `sequence`.

### Free functions
```python
def recompute_payload_hash(event: RunEvent) -> str  # canonical JSON, exclude payload_hash, sha256 hex
def verify_payload(event: RunEvent) -> None          # PayloadMismatch on divergence
def dedupe_events(events) -> list[RunEvent]          # identical (run_id,event_id)+content -> one (keep order/first); diff content -> DuplicateConflict
def verify_chain(events, *, anchor: str | None = None) -> None
```
`verify_chain`: empty list OK; genesis `prev_event_hash == ""`; **sequence
gap-free from 0**; each `prev_event_hash == previous payload_hash`; payload
binding per event; `anchor` = trusted tip hash → tip mismatch (or last_sequence <
expected) → `ChainBroken` (**tail truncation** / whole-chain replacement).
Ordering keys: `(run_id, sequence)` and `(run_id, event_id)`.

---

## 2. `egta.contracts.evaluation`

### Status & reasons (status, never exception)
```python
class CompletionStatus(StrEnum):   # COMPLETE, INCOMPLETE, BLOCKED, REVIEW, FAILED
class IncompleteReason(StrEnum):
    MANIFEST_MISMATCH, SNAPSHOT_MISMATCH, MODEL_MISMATCH, PROMPT_MISMATCH,
    CODE_MISMATCH, POLICY_MISMATCH, MISSING_RESULT
    # MISSING_USAGE: PENDING (D) — reserved placeholder; not frozen.
```

### `EvaluationResult` (§5.1 complete — D item 2)
Typed fields:
- `run_pair_id: str`, `case_id: str`, `variant: str`
- `manifest_hash: str` (**required**; mismatch ⇒ INCOMPLETE/MANIFEST_MISMATCH)
- `completion_status: CompletionStatus`
- `incomplete_reason: IncompleteReason | None` — **INCOMPLETE must have a reason;
  COMPLETE must be None** (validated)
- `metrics: dict[str, float]` (typed, default `{}`)
- `quality_labels: list[str]` (typed, default `[]`)
- `failures: list[str]` (typed, default `[]`)
- `winner: str | None`, `baseline_win: bool`, `enhanced_win: bool`

INCOMPLETE/BLOCKED/REVIEW/FAILED are **returned**, never raised; an INCOMPLETE
pair is **not counted as a win** (`baseline_win == enhanced_win == False`,
`winner is None`).

### `replay_events(events, *, anchor=None) -> ReplayState` (D item 1)
`ReplayState` full fields: `run_id: str`, `last_sequence: int`,
`chain_tip_hash: str`, `event_count: int`, `metrics: dict[str, float]`,
`events: list[RunEvent]` (ordered). Sorting by `(run_id, sequence)`,
dedupe by `(run_id, event_id)`, `anchor` applied (tip/last_sequence) → tail
truncation detected. Fully offline (no LLM/network).

### `compare_runs(baseline, enhanced, rubric) -> EvaluationResult` (D item 1)
**Typed inputs** (reject bare `dict`; accept `RunSummary`/`RunSpec`); `rubric`
is a typed ``QualityRubric``/``MetricDef`` set and **must be used** (assert it
influences scoring/verification). Comparability requires matching
`target_snapshot_id`, `model_config_hash`, `prompt_hash`, `code_hash`,
`policy_hash`. Any mismatch ⇒ INCOMPLETE with the specific reason
(SNAPSHOT/MODEL/PROMPT/CODE/POLICY_MISMATCH); a missing required variant/result
⇒ INCOMPLETE `MISSING_RESULT`. `manifest_hash` mismatch ⇒ INCOMPLETE
`MANIFEST_MISMATCH`. None of these count as a win.

---

## 3. `ExperimentManifest` (B confirmations)
- `variants`: **all four B0/B1/B2/B3** mandatory, each non-empty; unknown key
  (e.g. `B9`) rejected.
- `metrics_rubric: dict[str, MetricDef]` — `MetricDef` requires seven fields
  `metric, operator, threshold, verification, source, aggregation, unit`;
  `operator` in an allowed set (`eq,lte,gte,lt,gt`); `threshold` numeric; `unit`
  non-empty string.
- **`quality_rubric: QualityRubric`** — independent field at the same level as
  `metrics_rubric`. Fields: `levels: list[str]` (≥3), `double_blind: bool`,
  `third_party_adjudication: bool`, `llm_judge_assist: bool`.
- **`code_hash: str`** — the complete Git commit SHA of the current experiment
  run (40/64 hex). **`policy_hash: str`** — matches `RunSpec.policy_hash`
  (64-hex). (B3 intentionally disables the budget-optimization switch; the
  test/covenant distinguishes *pre-declared variant differences* from *unstated
  configuration drift* — i.e. a code/policy mismatch **between comparable arms**
  is INCOMPLETE, not a silent difference.)
- **`manifest_hash: str`** — required; the spec hash function:
  `sha256(canonical_json(manifest without manifest_hash))` (sort_keys, separators
  `(",",":")`), lowercase hex. A mismatch vs the run's recorded `manifest_hash`
  ⇒ INCOMPLETE/MANIFEST_MISMATCH.
- **PENDING (B):** if B later reverts `quality_rubric` to nested, adjust here and
  in tests. `MISSING_USAGE` in `IncompleteReason` = **PENDING (D)**.

## 4. `RunEvent` (immutability & strictness — F-05/F-14/F-20, D item 10)
- **Immutable/frozen:** `frozen=True`, `validate_assignment=True` (assignment
  after construction raises).
- `sequence`: strict `int`; negative, bool, or string rejected.
- `status`/reason consistency: `OK` **must not** carry a `reason_code`;
  `BLOCKED` **must** have one (validated). `schema_version`/contract-version
  field present and validated.
- `duration` (NFR-09): per-phase duration recorded (non-negative).
- Where a rule cannot be enforced yet, the test is marked `PENDING (D deferral)`.

## 5. `RunEvent.metrics` validation
JSON-safe only: non-finite floats (`NaN`,`±inf`), non-serializable objects,
`bytes`, and a non-dict `metrics` are rejected at construction (`ValidationError`).
Nested non-JSON (inside list/dict) also rejected.

---

## 6. Approval binding (corrected, D item 13)
- `docs/approvals/test-hash-FR-05-contracts.txt` records **only**
  `test_content_commit`, `aggregate_sha256`, and **`spec_bundle_sha256`**
  (tests + this summary + trace + spec-registry combined). Any change updates the
  bundle hash ⇒ re-review.
- Authoritative reviewed head = GitHub review `commit_id`; merge commit in the
  external registry/CI artifact/PR comment. **Do not push the approval file after
  approval.**
