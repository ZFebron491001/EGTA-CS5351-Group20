# Option Ledger (D2)

- **Status:** DRAFT — PENDING HUMAN REVIEW. Records key architecture options, their
  decision status, the reasons, and the ADR/PR that carries them.
- **Owner of this document:** B (D2 architecture pack).
- **Related:** `docs/architecture/adr/001-modular-extension.md` (ADR-001),
  `docs/architecture/adr/003-risk-authority.md` (ADR-003),
  `docs/architecture/architecture-blueprint.md`, `docs/architecture/memory-design.md`,
  `docs/architecture/risk-list.md`.

> A "decision status" is one of: **ADOPTED** (decided and implemented/fully specified),
> **PROPOSED** (decided direction, PENDING human approval), **DEFERRED** (not decided;
> recorded, owner to confirm), **REJECTED** (considered and dropped). This ledger keeps
> the **true** state — it does not promote a PROPOSED decision to ADOPTED.

## 1. Decisions

| ID | Option / decision | Status | Rationale | Carrier (ADR / PR) |
|---|---|---|---|---|
| OL-01 | **A/B/C extension shape** — (A) edit upstream agents in place; (B) modular monolith + contracts/adapters; (C) microservices + bus | **PROPOSED** (B chosen) | Weighted score (deliver 25 / test 25 / safety 20 / collab 15 / compat 15): A 3.05, **B 4.45**, C 3.50. B keeps upstream intact, gives one-place-per-rule testability, clean ownership, narrow auditable boundary | **ADR-001**; scoring retained from `execution_plan` §4.2 |
| OL-02 | **Keep upstream `tradingagents/`+`cli/` as baseline; add `src/egta/` modules** | **PROPOSED** | Preserves NFR-08 reproducibility; five members get non-overlapping modules; hybrid packaging `where=[".","src"]` | ADR-001; pyproject `packages.find` |
| OL-03 | **Budget governor is the admission authority; not the LLM; governor does not send** | **PROPOSED** (implemented, PENDING approval) | INV-03: every external call reserved first; deterministic; merged #45 with 4/4 frozen cases | ADR-001; PR #22 (spec), PR #45 (impl) |
| OL-04 | **Deterministic RiskGate is the sole ledger authority; risk-debate agent is advisory only** | **PROPOSED** (implemented, PENDING approval) | LLM output is untrusted; atomic verdict+ledger+audit (INV-01/04/06); fail-closed | **ADR-003**; merged D risk gate |
| OL-05 | **Model gateway as the single admission choke point** (tool binding / structured fallback / retry all routed through `reserve`) | **DEFERRED** (design intent) | Avoids any bypass (R1); needs a unified gateway that does not exist yet | blueprint §2, `trace-FR-02-admission.md`; **not built** |
| OL-06 | **Layered / compression / re-injection memory design** | **DEFERRED** (owner C) | Bounds token growth (NFR-02), re-injects lessons; must respect INV-03 (budgeted summarizer) and INV-05 | `memory-design.md`; **target ADR-002, no ADR yet** |
| OL-07 | **Unified runner in `src/egta/app/` owning end-to-end wiring** | **DEFERRED** (design intent) | One place wires evidence→budget→deliberation→risk→evaluation; enables G1 e2e | blueprint §2, R3; **not built** |
| OL-08 | **Microservices + message bus** | **REJECTED** | Ops/distributed-state cost exceeds course value; no multi-tenant/scaling requirement | ADR-001 (re-open only on real requirement) |
| OL-09 | **Editing upstream agents/prompts in place** | **REJECTED** | Coupling & permission boundaries hard to verify; blurs module ownership | ADR-001 |
| OL-10 | **Money as `Decimal` only; no `float()` in money paths; widened-precision exact add** | **PROPOSED** (implemented) | Prevents silent float drift and sub-cent over-admit (e.g. `1+1E-29`); merged governor `_exact_add` | ADR-003; `src/egta/budget/ledger.py`, `risk-policy.md` §2 |
| OL-11 | **Idempotency by `proposal_hash` unique key + `BEGIN IMMEDIATE`** | **PROPOSED** (implemented) | INV-04: duplicate returns stored verdict, never a second trade | ADR-003; merged D risk gate |
| OL-12 | **Shared `ReasonCode` enum for refusals (incl. `BUDGET_DENIED`)** | **PROPOSED** (implemented) | Single vocabulary across budget/risk/evaluation; `StrEnum` keeps serialized value stable | PR #45 revision (`__init__.py`); `egta.contracts.events` |
| OL-13 | **Two-phase test-first PRs with hash-bound approval records** | **PROPOSED** (enforced by CI) | GATE-01: spec PR merged before impl PR; approval binds test hash/req/approver/commit | `tools/check_approval.py`, CI `check-approval`, `docs/approvals/` |

## 2. How the ledger is kept honest

- ADOPTED would require a recorded human approval and merged implementation. None of
  OL-01/02/03/04/10/11/12/13 is marked ADOPTED here because the D2 pack itself is a
  draft under human review and the ADRs remain PROPOSED/PENDING.
- DEFERRED options (OL-05/06/07) are tracked as risks R1/R4/R3 in `risk-list.md`; their
  close conditions mirror the acceptance items in `trace-FR-02-admission.md` and
  `memory-design.md`.
- REJECTED options (OL-08/09) carry their re-open conditions in ADR-001 ("When to
  revisit"), so a future requirement can revive them explicitly rather than silently.
