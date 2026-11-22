# Final verification — E (G3 evidence)

§0 Header
- Date (UTC): 2026-11-22 (re-run on synced head)
- run HEAD: `71cd6381406d8625d3e78a62292b39640fe53b55` (PR #34 final head, synced to main `81f25f5`; prior runs on `ab0fc0b` from main `4d4b98d`, and snapshot `6830926`)
- (old snapshot `6830926` results retained below as historical context)
- Env: conda `egta` · Python 3.12.16 · pytest 9.2.0 · ruff 0.17.6 · mypy 2.4.1

## 1. Offline suites (real output)
| Suite | Command | Result |
|---|---|---|
| FR-05 contracts — **7-file gate** | `pytest -m spec test/offline/contracts/{test_comparison,test_events,test_audit,test_replay,test_evaluation_result,test_manifest,test_metrics_serialization}.py -q` | **223 passed** |
| contracts — **full directory** | `pytest -m spec test/offline/contracts -q` | **288 passed** (incl. FR-01 `test_evidence_contracts.py`, now importable after #21) |
| E2 evaluation | `pytest -m spec test/offline/evaluation -q` | **28 passed** |
| FR-04 risk gate | `pytest test/offline/risk_gate -q` | **139 passed** |
| FR-02 budget | `pytest -m spec test/offline/budget -q` | **N/A — no `src/egta/budget`** (FR-02 spec-only, #22); `0 tests collected`; NOT skip-green |
| upstream | `pytest -q` | **1412 passed, 1 skipped, 1 deselected** |

**Note (truthful, updated on synced head):** the CI gate isolates FR-05's **7 explicit files** (→ 223). The **full directory now also collects green (288)** because FR-01 `test_evidence_contracts.py` imports `EvidenceItem` from `egta.contracts`, which is implemented after #21. (On the older snapshot `6830926` the full directory errored at collection for that FR-01 import; that gap is now closed.)

## 2. Quality gates
- `ruff check .` → **All checks passed!** (exit 0)
- `mypy src/egta` → **Success: no issues found in 21 source files**

## 3. CI — 7 required checks (final head `71cd638` @ main `81f25f5` — 7/7 success; the 10-check set incl. E3 gates applies only after #40 merges into main)
```
tests (py3.11)=success | tests (py3.12, America/New_York)=success | tests (py3.13)=success
tests (py3.14)=success | clean-install smoke=success | ruff (strict, full repo)=success
offline spec suites (per-suite gate)=success
```

## 4. Three-way end-to-end (module-level; G1)
Driver: `tools/e2e_g1.py` (real `compare_runs` + `evaluation` + real `RiskGate` +
`risk_gate.ledger`; temp SQLite; fixed clock `2026-01-02T15:00Z`; no network; the
typed inputs are built by the test-only dataclasses in `test/offline/risk_gate/fakes.py`,
which contain no logic). Actual output:

```
normal      | compare=COMPLETE | verdict=APPROVED | version 1->2 | entries +1 | cash 10000.00->9899.90 | OK
declined    | verdict=REJECTED | version 1->1 | entries +0 | cash 10000.00->10000.00 | OK
declined-2  | verdict=REJECTED | version 1->1 | entries +0 | cash 10000.00->10000.00 | OK
over-budget | N/A — budget module not implemented (FR-02 spec-only, #22); contract expects BudgetDenied / MISSING_USAGE; documented gap, owner B, pending FR-02 implementation
```

| Scenario | Comparison | Risk verdict | portfolio_version | ledger entries | cash |
|---|---|---|---|---|---|
| normal | COMPLETE | APPROVED | 1 → 2 | +1 | 10000.00 → 9899.90 |
| declined (oversized: qty 100 @ 100.00 ≫ 10% NAV) | — | REJECTED | 1 → 1 | +0 | unchanged |
| declined-2 (stale caller portfolio version) | — | REJECTED | unchanged | +0 | unchanged |
| over-budget | — | N/A (budget not implemented) | — | — | — |

**Scope of this e2e (truthful):** only the **decline/stale** paths and the **normal approved** path are demonstrated at the module level; the **over-budget** path is **NOT** demonstrated (budget not implemented). This does **not** claim all three G1 routes (normal / declined / over-budget) are complete — over-budget remains a documented gap (owner B). The `declined-2` (stale caller portfolio version) path is now **asserted** in the driver (version unchanged / 0 entries / cash unchanged), so a regression there exits non-zero.

**CLI gap (documented):** there is **no unified `egta` CLI/runner** on `main`; this
e2e drives the modules directly (`compare_runs` → `evaluation` → `RiskGate` →
`ledger`). End-to-end *through one CLI* is a documented gap, not a failure.

## 5. Reverse-blocking evidence (G3)
- **#32** `reverse-proof/blocking-test` — a deliberate-fault PR. Observed: `offline
  spec suites` **FAIL** (contracts record 222 vs actual 223) and `ruff` **FAIL** (F401,
  unused `import json`); `mergeStateStatus=BLOCKED`. Run `45007539491`
  (`offline` job 137162364592, `ruff` job 137162364293). Branch retained (not merged).
- **#33** `docs/verification/reverse-blocking-test.md` — the written evidence doc.

## 6. Known gaps / non-claims
- No unified `egta` CLI/runner (modules exist, not wired) — e2e is module-level (§4).
- Budget not implemented (`src/egta/budget` absent) — FR-02 spec-only (#22); N/A.
- Full `test/offline/contracts` dir **now passes (288)** on the synced head (FR-01 `EvidenceItem` implemented via #21); the CI gate still isolates FR-05's 7 files (223) so FR-01 cannot contaminate that count.
- Six-gate: only the `offline-tests` gate is wired; permission/approval (#29
  `tools/check_*.py`), schema, ai-log and semantic checks are **follow-up E3** work.
