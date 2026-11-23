# FR-02 Gateway / Runner Integration — Acceptance Table (test-first)

- **Status:** DRAFT — test/spec only (no production implementation in this PR).
- **Owner:** B. Reviewer targets: **E** (interface / CI selector / status) and
  **C** (deliberation boundary).
- **Spec:** `docs/req/spec-FR-02-gateway.md`. Trace: `docs/req/trace-FR-02-gateway.md`.
- **Depends on:** #22 (budget spec, merged), #45 (governor, merged `eafaff4`),
  the RiskGate (D, FR-04), E's `SqliteAuditSink`/`SqliteAuditReader`.

## 1. Suites and counts (real, 2026-11-23, over `origin/main` `48c324f`)

| Suite | Path | Marker | Collected | Result (RED expected) |
|---|---|---|---|---|
| Governor (frozen #22) | `test/offline/budget` | `-m spec` | **4** | **4 passed** (unchanged; #22 count preserved) |
| Gateway adapter (new) | `test/offline/integration/test_gateway.py` | `-m spec` | 4 | 4 failed at `egta.adapters` (unbuilt) |
| Runner / CLI (new) | `test/offline/integration/test_runner_cli.py` | `-m spec` | 4 | 3 failed at `egta.app`, 1 at `egta.__main__` (unbuilt) |

Business assertions executed in the RED runs: **0** (all failures are lazy imports
inside test bodies; no business `assert` is reached).

## 2. Acceptance cases

| # | Case | Real modules | Faked | Pass condition | Status |
|---|---|---|---|---|---|
| 1a | ample budget reserve→send | governor | model transport | `[("reserve","Reservation"),("send","chat")]` | RED (adapter) |
| 1b | zero budget refuses, transport 0 | governor | model transport | raises `BudgetDeniedError`, reason `BUDGET_DENIED`; no send | RED (adapter) |
| 2 | bind_tools admits 0; bound send admits 1 | governor | model transport | bind `[]`; chain 1 reserve + 1 structured send | RED (adapter) |
| 3 | structured 400 → fallback re-admits (allowance 1) | governor | model transport | `Reservation, send structured, BudgetDenied`; transport 1 | RED (adapter) |
| R1 | normal run | governor + RiskGate + ledger + audit | provider reply | admission precedes send (one shared event seq); `APPROVED`; independent ledger read +1 entry & version+1; `result.run_id == proposal.run_id`; audit read by that run_id non-empty, all share it; `evidence_pack_hash == pack hash` | RED (runner) |
| R2 | risk reject run | RiskGate + ledger + audit | provider | known reject fixture (insufficient cash) → exact `REJECTED`/`POLICY_REJECTED` (verified standalone); `result.run_id == proposal.run_id`; ledger unchanged before/after; audit read by that run_id shows the reason | RED (runner) |
| R3 | budget deny run | governor + ledger + audit | provider (0 calls) | provider 0; `ReasonCode.BUDGET_DENIED`; `result.run_id == proposal.run_id`; ledger unchanged; audit read by that run_id has a **BUDGET_DENIED** event. Workflow terminal status **not** asserted (pending E). | RED (runner) |
| R4 | CLI offline entry | `egta.__main__` | spy observes dispatch | public CLI with `--db-path`/`--audit-path` calls `run_offline` with those params; exit 0 | RED (runner) |

## 3. Test file hashes (for non-author verification)

```
b7b5d318e3d59fc3bdf70d310e6e0a727dc5b8c7e9553ea07153ddd2371ad652  test/offline/integration/test_gateway.py
834619021090fcfdce58c2cc9859700aa2932e831760381a5b58b91857338609  test/offline/integration/test_runner_cli.py
08d72e600cb08251167dfd651fc5993318c94af3f5add5abacc9c18c90d2c0ce  test/offline/integration/conftest.py
124d9cba1af5b3a19290bbf60310182963b067e0356b244519911cf44781afb7  test/offline/integration/fakes_gateway.py
```

Frozen #22 files are **byte-identical** to the merged approval record
(`docs/approvals/test-hash-FR-02-budget.txt`):

```
bbf2f5d3db5ecf909027cc07a391fd9bc042fcd967548a2ff1ee94437020ec5c  test/offline/budget/conftest.py
04b7b87eed8c0a6712fd58ab1777de3ad04bfc05d979e3d5c65282ba7aa51de7  test/offline/budget/fakes.py
a1a012e09ee0cfc765ac297c05307e82c9dcd97f086417183bf20794e0bdc1d2  test/offline/budget/test_admission.py
06fabe6c32fee059421e242615868ab490ef02d30dc83479c2ef6d338fb64506  test/offline/budget/test_reservation_holds.py
```

## 4. Decisions for E / D before merge

1. **CI selector:** add a per-suite gate for `test/offline/integration/` (with its own
   `actual_cases` record), or route it under check-permissions `build-b` only? The
   #22 governor count (4) is preserved either way.
2. **Approval-record route:** a new `test-hash-FR-02-integration.txt`, or extend the
   existing FR-02 budget record? (This PR changes no production code, so it is a
   test/spec PR.)
3. **Implementation applicability:** the RED lands on `egta.adapters` / `egta.app` /
   `egta.__main__` (all unbuilt). Confirm the implementation round creates these.
4. **Workflow status (E):** R3 asserts membership in `CompletionStatus`; confirm the
   zero-budget terminal status is `INCOMPLETE` (or a dedicated governor status).
5. **Deliberation boundary (C):** confirm whether deliberation makes model calls
   outside the shared `get_llm()`; the runner uses a FIXED proposal fixture until C
   lands.
