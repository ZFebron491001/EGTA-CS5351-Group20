# Architecture Blueprint — Evidence-Governed TradingAgents (EGTA)

- **Status:** DRAFT — the **single D2 blueprint body** (B-owned). A draft for human
  review; concrete interfaces are governed by the approved contracts in `docs/req/`
  and the ADRs.
- **Source of truth for structure:** `execution_plan_261111.md` §4, §5, §8.1; the
  requirement registry `docs/req/requirements.yaml` (38 IDs).
- **Related:** FR-02 (B), INV-03, NFR-01/02/04; ADR-001, ADR-003; INV-01/02/04/06/07;
  `invariants.md`, `risk-policy.md`, `permission-model.md`, `runtime-policy-catalog.md`,
  `trace-matrix.md`, `evaluation-table.md`, `evaluation-logbook.md`, `risk-list.md`,
  `option-ledger.md`, `memory-design.md`.

> This is the single D2 blueprint body. The repository-root `architecture-blueprint.md`
> is an entry link to this file (see `execution_plan` §8.1). Keep the two in sync.

## 1. The chosen shape: a modular monolith with contracts + adapters

The system keeps the upstream `tradingagents` / `cli` packages and adds five
single-responsibility modules under `src/egta/` plus three support components
(`contracts`, `app`, `adapters`). One implementation directory per rule; a rule is
never duplicated across modules. The rationale and rejected alternatives, with the
A/B/C scoring, are in **ADR-001** (`docs/architecture/adr/001-modular-extension.md`)
and the decision record in **`option-ledger.md`**.

| Component | Owns | Must NOT own | Present in `src/egta/` today |
|---|---|---|---|
| `evidence` (A) | read allowed sources; emit immutable evidence pack | change risk config; fabricate publish time | **yes** — `time_policy.py`, `pack.py`, `hashing.py` |
| `budget` (B) | reserve/settle quotas; admit/refuse external calls | produce the investment decision | **yes** — `ledger.py`, `__init__.py` (governor) |
| `deliberation` (C) | propose/compare, cite evidence | execute; skip budget/risk gate | **no** — target only, C-owned, not yet merged |
| `risk_gate` (D) | sole risk authority; transactional paper ledger | call an LLM to waive a rule | **yes** — `service.py`, `rules.py`, `ledger.py`, `policy.py` |
| `evaluation` (E) | subscribe to events; score; audit report | rewrite decisions or raw logs | **yes** — `replay.py`, `metrics.py`, `report.py`, `sink.py` |
| `contracts` (B custodian) | shared schemas/types | business logic | **yes** — `events.py`, `evidence.py`, `audit.py`, `evaluation.py`, `manifest.py` |
| `app` / `adapters` (B) | entry wiring; upstream/model ports | another module's private state | **no** — runner + gateway + adapters are target only, not built |

## 2. Call graph: CLI → runner → gateway → budget admission → provider → risk/audit

> **Target architecture — the unified runner and model gateway are not built yet.**
> The picture below is the intended wiring. The component that calls `reserve`/`settle`
> and the model provider is the **model gateway** (B) under `src/egta/adapters/`, driven
> by the **runner** (B) under `src/egta/app/`. The **governor does not send requests**;
> it only admits/refuses and tracks the hold. The governor (#45) and its four frozen
> cases (#22) are merged; the runner/gateway that actually drives these calls is
> **pending** (see §4 and `risk-list.md` R1/R3).

```mermaid
flowchart TD
    CLI["CLI (cli/main.py, cli/run.py)"] --> APP["unified runner (B)<br/>src/egta/app/ — target, not built"]
    APP --> EVD["evidence: build pack (A)<br/>src/egta/evidence/"]
    APP --> DELIB["deliberation: propose (C)<br/>src/egta/deliberation/ — target"]
    DELIB --> GW["model gateway / adapters (B)<br/>src/egta/adapters/model_gateway.py — target, not built"]

    GW -->|"1. reserve(call_spec)"| BUD["budget governor (B)<br/>src/egta/budget/ — merged #45"]
    BUD -->|"Reservation (admitted)"| GW
    BUD -->|"BudgetDenied (refused)"| GW
    GW -->|"2a. refused: return, NO send"| ZERO["provider requests = 0"]
    GW -->|"2b. admitted: send"| PROV["model provider (upstream LLM port)"]
    PROV -->|"3. response + actual usage"| GW
    GW -->|"4. settle(reservation_id, usage or None)"| BUD

    DELIB --> PROP["AdvisoryProposal (contracts)"]
    PROP --> RISK["risk_gate: evaluate_and_commit (D)"]
    RISK -->|approved| LEDGER["paper ledger (SQLite, transactional)"]
    RISK -->|refused/insufficient| RB["BLOCKED / REVIEW"]
    APP -. events .-> AUD["evaluation & audit (E)"]
    EVD -. events .-> AUD
    BUD -. events .-> AUD
    RISK -. events .-> AUD
```

Key rule (INV-03): **every external model call passes through the budget governor
before it is sent.** The **gateway** calls `reserve`; on `BudgetDenied` it returns
without contacting the provider (zero provider requests); on `Reservation` it sends
the request, then calls `settle` with the actual usage (or `None` when unknown, which
keeps the hold). A gateway that bypasses the governor — tool binding, a
structured-output fallback, a retry — must not exist; those paths are the pending
verification items in `trace-FR-02-admission.md` and the risks in `risk-list.md`.

### Data flow vs. control flow

- **Control flow (admission):** CLI → runner → gateway → governor `reserve` →
  (admit/refuse) → provider `send` → governor `settle`. The governor is the single
  gate for external calls; the risk gate is the single gate for ledger writes.
- **Data flow (evidence → proposal → verdict → audit):** evidence pack (A) →
  deliberation proposal (C) → risk verdict + ledger (D) → append-only audit events
  (E). Each hop carries a content hash; the audit stream reconstructs the run.

## 3. Module boundaries and the contracts they share

- Shared types live in `src/egta/contracts/` (B custodian; producer+consumer
  approval). The evidence types `RunSpec / EvidenceItem / EvidencePack` are
  implemented and merged (PR #21); the shared `ReasonCode` lives in
  `egta.contracts.events`; `RunEvent`/audit/evaluation types are E-authored (PR #18).
- Cross-module calls go through the frozen interface objects in `execution_plan`
  §5.1 — e.g. `BudgetGovernor.reserve(call_spec) -> Reservation | BudgetDenied` and
  `BudgetGovernor.settle(reservation_id, actual_usage_or_unknown) -> BudgetState`;
  `RiskGate.evaluate_and_commit(proposal, evidence_pack, current_portfolio) -> RiskVerdict`.
- A module never reads another module's database, private class, or env var
  (NFR-06 static architecture check; see `trace-matrix.md`).

## 4. Budget governance (FR-02 / INV-03) — status

The budget governor is B's component:

- **Spec (frozen, merged):** PR **#22** (`test/offline/budget/`,
  `docs/req/trace-FR-02-budget-reservation.md`, `…-admission.md`), merge `a47c29c`.
  Four approved cases: unknown-usage holds the token reservation; an unsettled
  reservation stays held; known low usage releases unused tokens; two concurrent
  callers competing for the last call slot yield exactly one `Reservation` and one
  `BudgetDenied`.
- **Implementation (merged):** PR **#45** (`src/egta/budget/__init__.py`,
  `ledger.py`), merge `eafaff4`. SQLite, atomic reserve across tokens/cost/calls;
  unknown usage keeps the hold; partial settlement; idempotent re-settle; exact money
  comparison (`Decimal` with widened local precision so a sub-cent over-request is
  caught); one persisted limit set per database; shared `ReasonCode.BUDGET_DENIED`.
  CI evidence: the four frozen cases pass and the per-suite gate reports
  `budget: passed=4 expected=4 -> OK` (see `evaluation-logbook.md`).
- **Still pending (not verified):** the **unified model gateway / runner** wiring that
  makes the tested governor drive admission itself — tool binding, structured-output
  fallback, zero-budget "0 requests reach transport", and sent-then-interrupted before
  usage. These are listed as acceptance items in `trace-FR-02-admission.md`; they are
  NOT claimed green here (see `risk-list.md` R1/R3).

## 5. Evidence and determinism (FR-01 / INV-02)

Three things, at three different states:

- **Public types (merged):** `RunSpec` / `EvidenceItem` / `EvidencePack` in
  `src/egta/contracts/evidence.py` (PR #21) represent the pack outcomes with day
  precision. They carry data; they do not filter, mint ids, or compare digests.
- **Time policy (merged, A):** `src/egta/evidence/time_policy.py` (PR #4) applies
  the UTC date boundary. Per the committed contract (`docs/req/evidence-contracts.md`,
  from D's second #4 review at fixture `19da73a`):
  - **date-only** (`time_granularity="day"`) on the **same** UTC date as `as_of` is
    **excluded** (`availability="unavailable"`, `reason_code="FUTURE_DATA"`, never
    `INVALID_TIME`); it is admitted only when **strictly earlier** than the `as_of`
    UTC date;
  - **exact timestamp equality** (`published_at == as_of`, timezone-aware) is
    **admitted** — a different case from the same-date date-only exclusion.
- **Pack implementation (merged, A):** building the immutable pack, `evidence_id`
  generation from `run_id` + local id, dedupe, and pack-time `content_hash`
  recompute → `INTEGRITY_VIOLATION` are **PR #43, merged** (`7c3fbd4`).

The budget and risk components consume the pack; neither re-implements the filter.

## 6. Risk authority and the paper ledger (FR-04 / INV-01/04/06)

`risk_gate` (D) is the sole authority that may change the paper ledger. It re-reads
the portfolio version, checks the proposal hash/expiry, evaluates the rules, and
writes the verdict, ledger entries, and outbox audit event in ONE SQLite transaction
(INV-06). Duplicate proposals return the stored verdict (INV-04). See
`docs/architecture/adr/003-risk-authority.md`, `risk-policy.md`, `invariants.md`, and
`runtime-policy-catalog.md`.

## 7. What is implemented vs pending (traceable)

| Area | Req IDs | Status | Where |
|---|---|---|---|
| Evidence public types (RunSpec/EvidenceItem/EvidencePack) | FR-01, INV-02 | **merged** | `src/egta/contracts/evidence.py` (PR #21) |
| Evidence time policy (UTC date boundary) | FR-01, INV-02 | merged (A) | `src/egta/evidence/time_policy.py` (PR #4) |
| Evidence pack build (ids/dedupe/pack hash) | FR-01, INV-02 | **merged** | `src/egta/evidence/pack.py` (PR #43, `7c3fbd4`) |
| Risk gate + ledger (D) | FR-04, INV-01/04/06 | merged (D) | `src/egta/risk_gate/` |
| Budget **spec** | FR-02, INV-03 | **merged** | `test/offline/budget/` (#22, `a47c29c`) |
| Budget **governor** | FR-02, INV-03 | **merged** | `src/egta/budget/` (#45, `eafaff4`) |
| Deliberation module (C) | FR-03, INV-05 | **pending** | `src/egta/deliberation/` (not built) |
| Unified model gateway + runner wiring | FR-02, INV-03 | **pending** | `src/egta/app/`, `src/egta/adapters/` (not built) |
| Evaluation & audit (E) | FR-05, NFR-08/09 | merged (E) | `src/egta/evaluation/` |

## 8. Non-negotiables that wire across modules

- INV-03 — every external model call first obtains a budget reservation; if refused,
  no new inference is started.
- INV-01/06 — only an approved, same-transaction risk verdict changes the ledger.
- INV-02 — no data published after `as_of` is used.
- INV-05 — untrusted external text cannot change rules or tool permissions (C + the
  permission gateway).
- INV-07 — secrets never enter prompts, reports, commits, or session exports.

## 9. Open items for the next revision

- Build and prove the **unified model gateway + runner** so no model call bypasses the
  governor (tool binding / structured fallback / retries / interruption). Until then,
  budget governance is proven at the governor layer (4/4 frozen cases), not end-to-end.
- Deliver the **C deliberation module** and its layered/compressed/re-injection context
  design (see `memory-design.md`); the blueprint's data flow assumes it exists.
- Cross-process crash recovery of the budget ledger (reopen after a kill) is unverified.
- Align `RunSpec.limits` keys with the budget governor's `limits` once wired in `app`.
- The paired baseline/enhanced experiment (NFR-02/NFR-03) has not been run; see
  `evaluation-table.md` and `risk-list.md` R5.
