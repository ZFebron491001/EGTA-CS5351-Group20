# Runtime Policy Catalog (D2)

- **Status:** DRAFT — PENDING HUMAN REVIEW. B-authored index over existing policies.
- **Owner of this document:** B (D2 architecture pack).
- **Rule owners:** budget (B / FR-02, NFR-01, INV-03); evidence time (A / FR-01,
  INV-02); risk (D / FR-04, INV-01/04/06, NFR-04); permissions (D / NFR-05, INV-05,
  INV-07); audit (E / FR-05, NFR-09); governance gates (E+D).
- **Sources of truth (do not duplicate, cite here):**
  `docs/architecture/invariants.md`, `docs/architecture/risk-policy.md`,
  `docs/architecture/permission-model.md`, `docs/architecture/adr/003-risk-authority.md`,
  `docs/architecture/threat-model.md`, `docs/req/requirements.yaml`,
  `execution_plan_261111.md` §4.4/§5.1.

> This catalog lists runtime rules **by requirement ID** with their source, the code
> location that enforces them, the fail-closed result, and the verification status.
> It is an index, not a second source of truth: where a threshold is PENDING in
> `risk-policy.md`, it stays PENDING here.

## 1. Budget / admission rules (B)

| Req ID | Rule | Source | Runtime enforcement | Failure result | Verification status |
|---|---|---|---|---|---|
| FR-02 | Global admission before any external call; insufficient → stop/degrade with reason + consumption | requirements.yaml FR-02 | `BudgetGovernor.reserve` (`src/egta/budget/__init__.py` → `ledger.py`) | `BudgetDenied` (no send); governor never sends → provider requests = 0 | Governor layer: **4/4 frozen cases pass (#22/#45)**. End-to-end gateway path **PENDING** (`trace-FR-02-admission.md`) |
| NFR-01 | Triple constraint `max_total_tokens` / `max_cost_usd` / `max_calls`, frozen to the run record | requirements.yaml NFR-01 | `BudgetLedger` limits (one persisted set per DB) | refuse admit when HOLD+request exceeds any axis | governance/limits persistence covered; `RunSpec.limits` ↔ governor `limits` alignment **PENDING** |
| INV-03 | Every external model call first obtains a reservation | invariants.md INV-03 | gateway must call `reserve` first (gateway **not built**) | refused call never starts inference | governor enforced; **gateway wiring PENDING** |

Money rule (B): all cost values are `Decimal`; comparison uses exact addition under a
widened local context so a sub-cent over-request (e.g. `1 + 1E-29 > 1`) is refused
(`ledger.py:_exact_add`). Boundary probe (cost cap $1.00): exactly $1.00 admitted, a
further `1E-29` refused — verified locally and via CI.

## 2. Evidence time rules (A)

| Req ID | Rule | Source | Runtime enforcement | Failure result | Verification status |
|---|---|---|---|---|---|
| FR-01 | Every output carries an evidence pack (source, publish/fetch time, content hash, claim refs) | requirements.yaml FR-01 | `src/egta/evidence/pack.py` (merged #43) | missing/incomplete pack → not traceable | FR-01 pack suite **merged**; field/citation completeness per `trace-FR-01-evidence*.md` |
| INV-02 | Data published after `as_of` is not used | invariants.md INV-02; evidence-contracts.md | `src/egta/evidence/time_policy.py` | item excluded, `availability="unavailable"`, `reason_code="FUTURE_DATA"` (never `INVALID_TIME`) | 13 test functions over fixtures E-01..E-31 (merged) |

Time rule detail (A, merged): date-only on the **same** UTC date as `as_of` is
excluded with `FUTURE_DATA`; admitted only when strictly earlier. Exact timestamp
equality (`published_at == as_of`, tz-aware) is admitted. This is not re-implemented in
budget or risk.

## 3. Risk / ledger rules (D)

| Req ID | Rule | Source | Runtime enforcement | Failure result | Verification status |
|---|---|---|---|---|---|
| FR-04 | Suggestion forms a paper order only after passing deterministic checks; every rejection reason shown | requirements.yaml FR-04 | `RiskGate.evaluate_and_commit` (`src/egta/risk_gate/service.py`) | `REJECTED`/`BLOCKED`/`REVIEW` with structured reason; no ledger change | risk_gate suite **139 passed** (merged) |
| INV-01 | Unapproved proposal cannot change the paper ledger | invariants.md INV-01 | private ledger writer; fixed signature, no bypass param | rollback; `BLOCKED`; security event | `T-RISK-ACT-*`/`FND-*`/`EVD-*`/`SEC-*` (merged) |
| INV-04 | Same proposal → only one ledger change | invariants.md INV-04 | unique `proposal_hash` idempotency store; `BEGIN IMMEDIATE` | duplicate returns stored verdict; no second trade | `T-RISK-IDM-*`/`ATM-*` (merged) |
| INV-06 | Execution + verdict + audit committed atomically | invariants.md INV-06 | one SQLite transaction; in-DB outbox | rollback all; `BLOCKED`/`AUDIT_UNAVAILABLE` | crash subprocess tests (merged) |
| NFR-04 | No duplicate orders across timeout/429/crash; 30s tool / 90s LLM / 300s run timeouts | requirements.yaml NFR-04 | risk_gate + timeouts (gateway timeouts **PENDING**) | `BLOCKED`/`INCOMPLETE`, failure not masked | risk-side restart tests; gateway/timeout path **PENDING** |

Risk thresholds (`max_position_pct` 0.20, `max_order_pct` 0.10) are PLAN-SPECIFIED in
`risk-policy.md`; `price_freshness_seconds`, `fee_bps`, `slippage_bps`, base currency
and policy hash remain **PENDING** and must safe-reject when unset. Money is `Decimal`
only (no `float()` in a money path). Full reason/status mapping: `risk-policy.md` §5.

## 4. Permission and secret rules (D / NFR-05 / INV-05 / INV-07)

| Req ID | Rule | Source | Runtime enforcement | Failure result | Verification status |
|---|---|---|---|---|---|
| NFR-05 | ≥50 security cases; 0 unauthorized access, 0 secret-scan positives, 0 injection escapes | requirements.yaml NFR-05 | `permission-model.md` policy + `tools/check_permissions.py` | refuse; security incident; rotate | permission checkers offline-tested; CI wiring E-owned |
| INV-05 | External text cannot change rules/tool permissions | invariants.md INV-05 | permission gateway + deterministic rule (C/D) | injection blocked | depends on C deliberation + gateway (**PENDING**) |
| INV-07 | Secrets never in prompts/reports/commits/verdicts/outbox/exports | invariants.md INV-07 | field allowlist; redaction; secret scan | block export/commit; rotate | D field tests (merged); per-member log discipline |

The runtime `RiskGate` has **zero** tools: no LLM, no broker, no network, no file
writes outside its SQLite database (`permission-model.md` §4).

## 5. Audit / event rules (E)

| Req ID | Rule | Source | Runtime enforcement | Failure result | Verification status |
|---|---|---|---|---|---|
| FR-05 | Compare baseline/enhanced/ablations; replay events; trace to reqs/tests | requirements.yaml FR-05 | `src/egta/evaluation/` (`replay.py`, `report.py`) | incomplete pairs shown incomplete, not a win | E2 suite **28 passed**; paired experiment **PENDING** |
| NFR-09 | Every phase emits run_id/phase/status/duration/reason; ledger change linked to verdict + proposal hash; unknown cost ≠ 0 | requirements.yaml NFR-09 | `RunEvent` (contracts/events.py); evaluation checks | gap recorded; fail-closed | event schema/completeness tests (merged) |

## 6. Governance gate rules (E+D; runtime-of-CI, not runtime-of-app)

| Req ID | Rule | Source | Enforcement | Failure result | Verification status |
|---|---|---|---|---|---|
| GATE-01 | Two-phase test-first PRs; approval record binds test hash/req/approver/commit | requirements.yaml GATE-01 | `tools/check_approval.py` + CI `check-approval` job | fail closed (APPROVAL_PENDING / TEST_DRIFT / …) | **6 gates wired**; reverse-proof recorded |
| GATE-02 | Static/security on every commit; sensitive paths need review | requirements.yaml GATE-02 | ruff, `check_permissions.py`, CI | reject PR | wired |
| GATE-03/04/05/06 | Schema / semantic / regression / AI-use log gates | requirements.yaml | CI jobs | reject PR | wired (see `evaluation-logbook.md`) |

See `docs/verification/reverse-blocking-test.md` and `docs/evidence/FR-04/gate-reverse-proof.txt`
for the reverse-blocking evidence that each gate actually blocks.
