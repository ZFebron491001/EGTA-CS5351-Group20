# ADR-001 — Modular extension over the upstream baseline

- **Status:** DRAFT (proposed for D2; PENDING HUMAN APPROVAL)
- **Date:** 2026-11-22
- **Owner:** B (blueprint / ADR-001 per `execution_plan_261111.md` §7.3)
- **Related:** FR-02, INV-03, NFR-01/02/04; ADR-003 (risk authority); invariants;
  `docs/architecture/architecture-blueprint.md`

> Scope of this ADR (per `execution_plan` §4.2/§4.3): the *architecture decision* —
> how EGTA extends `TauricResearch/TradingAgents` (baseline SHA `9fa1196`,
  v0.7.1) into a testable, parallelizable, safety-bounded system. It is NOT the risk
> policy (that is ADR-003 / `risk-policy.md`) nor the per-module contracts (§5.1).

## Context

The upstream repository ships a LangGraph multi-agent pipeline and a Typer CLI. The
course requires five independently-owned modules (evidence, budget, deliberation,
risk gate, evaluation) plus shared contracts, delivered in parallel by five members,
under strong invariants (INV-01…INV-07) and a test-first governance regime (GATE-01).

The problem: how much do we change the upstream? Options range from editing the
existing agents/prompts in place to a full microservice split. Each has different
costs for testability, safety boundaries, and parallel collaboration.

## Decision drivers

- Existing upstream tests must keep passing; the baseline stays reproducible (NFR-08).
- Each rule (evidence time filter, budget admission, risk) must live in exactly one
  place and be independently testable offline.
- Five members need non-overlapping, individually ownable areas.
- Safety invariants need a narrow, auditable boundary (no LLM waiving risk, no
  budget bypass).

## Candidates (scored per `execution_plan` §4.2, 1–5, design-time judgement)

Weights: deliverability 25%, test/trace 25%, safety 20%, parallel-collab 15%,
upstream-compat 15%.

| Option | Deliver | Test | Safety | Collab | Compat | Weighted | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| A — edit existing agents/prompts in place | 5 | 2 | 2 | 2 | 4 | 3.05 | rejected: coupling & permission boundaries hard to verify |
| B — keep baseline as a modular monolith + contracts/adapters | 4 | 5 | 5 | 4 | 4 | 4.45 | **chosen** |
| C — microservices + message bus | 2 | 4 | 4 | 5 | 3 | 3.50 | rejected: ops/distributed-state cost exceeds course value |

## Decision

Adopt **Option B**: keep `tradingagents/` and `cli/` intact, and add the five EGTA
modules under `src/egta/` (`evidence/`, `budget/`, `deliberation/`, `risk_gate/`,
`evaluation/`) plus support components (`contracts/`, `app/`, `adapters/`). Each rule
has one implementation directory; a rule is never duplicated across modules
(`architecture-blueprint.md` §1). Modules depend only on `contracts` and injected
ports; cross-module calls use the frozen §5.1 interfaces.

Consequences we accept:

- We keep a hybrid packaging layout (`tradingagents`/`cli` at repo root, `src/egta`
  under `src/`), discovered via `packages.find where=[".", "src"]`.
- The budget governor, not the LLM, is the admission authority for external calls
  (INV-03). The deterministic risk gate, not a risk-debate agent, is the ledger
  authority (INV-01).
- Cross-module state is limited to the paper ledger (D, transactional SQLite) and the
  append-only audit/event log (E).

## Consequences — what this buys, what it costs

- **Buys:** offline testability per module first (the approved specs), one place per
  rule, independent ownership, a small auditable boundary.
- **Costs:** we must build and prove a **single unified model gateway** so no model
  call bypasses the governor (tool binding, structured fallback, retries,
  interruption). Until that is wired and verified, budget governance is proven only at
  the governor layer, not end-to-end (see blueprint §4/§9).

## When to revisit (reopening conditions)

Re-evaluate Option C (microservices) only if a real requirement appears for
multi-tenant isolation, independent scaling, or process-level isolation. If S1 finds
the upstream offers no narrow extension point, prefer a locally-scoped adapter ADR
rather than escalating to microservices (`execution_plan` §4.2).

## Status of the supporting work (traceable)

- Evidence contracts (types) — merged, PR #21.
- Budget spec — merged, PR #22.
- Budget governor implementation — in review, PR #45.
- Unified model gateway, tool binding, structured fallback, zero-budget transport,
  sent-then-interrupt — **pending** (no implementation yet).
