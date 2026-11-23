# Risk List (D2)

- **Status:** DRAFT — PENDING HUMAN REVIEW. B-authored risk register for the D2 pack.
- **Owner of this document:** B (D2 architecture pack); each risk has an `Owner` and a
  `Close condition` (what evidence removes it).
- **Related:** `docs/architecture/threat-model.md` (attack surface, T-* threats),
  `docs/debt-register.md` (process/technical debt), `risk-policy.md` (financial rule
  thresholds), `invariants.md`, `architecture-blueprint.md` §9, `evaluation-table.md` §4.

> Scope: architecture/integration risks that affect whether the blueprint's guarantees
> hold. Financial-parameter risk (thresholds) is governed in `risk-policy.md`; this list
> cross-references it and does not re-decide it. Threat-model attack risks (T-*) are
> referenced, not duplicated.

## 1. Risk register

| ID | Risk | Impact | Owner | Mitigation (current / planned) | Close condition |
|---|---|---|---|---|---|
| R1 | **Model-admission bypass**: a model call reaches the provider without a budget reservation (tool binding, structured-output fallback, retry path) | INV-03 violated; unbounded spend; FR-02/NFR-01 fail | B | Governor is the single admit/refuse authority (#45 merged, 4/4 cases). No gateway exists yet, so no call path is currently wired — but the guarantee is **governor-layer only**. Planned: single gateway that routes every call through `reserve`/`settle`; no bypass tool. Ref threat-model T-* | Gateway built with a single admission choke point; `trace-FR-02-admission.md` bypass tests (tool binding / fallback / retry) green in CI |
| R2 | **Timeout / unknown usage**: provider returns no usage, times out, or is interrupted mid-call | Reservation must stay held (not refunded); unknown cost must not show as 0 | B | Governor keeps hold on `settle(id, None)`; unknown-usage frozen case passes; `_exact_add` prevents sub-cent over-admit. Gateway interruption handling **not built** | sent-then-interrupt + unknown-usage end-to-end test green (NFR-04/FR-02 acceptance) |
| R3 | **Unified runner integration**: `src/egta/app/` and `src/egta/adapters/` do not exist; no single run wires evidence→budget→deliberation→risk→evaluation | End-to-end guarantees (G1 three routes) unproven; module-level green ≠ system green; E's over-budget e2e route still N/A | B | Modules individually merged and tested. Planned: runner owns wiring, one admission point, one ledger authority | Runner built; `tools/e2e_g1.py` over-budget route demonstrated through the gateway; NFR-04 injection suite green |
| R4 | **Context-injection boundary**: untrusted external text (evidence, memory/reflection, tool output) could change rules or tool permissions | INV-05 violated; LLM manipulation of risk/budget | C (+D permission gateway) | Deterministic rules (ADR-003) reject text-driven exemptions; risk gate re-checks from scratch. Deliberation isolation gate **not built**; memory design (ADR-002) pending | C deliberation + permission gateway built; injection test set (NFR-05, INV-05) green |
| R5 | **Unfinished experimental validation**: NFR-02 (token −25%, latency −20%), NFR-03 (entailment ≥90%), NFR-06 coverage, NFR-08 3-run determinism, paired FR-05 reports not produced | Quality/performance/perf claims unsubstantiated; **GATE-04 semantic gate is not even wired** so it cannot judge a real change | E (+B, C) | Module suites green; CI has 10 required checks (GATE-01/02/03 + regression). **GATE-04 has no CI job** and GATE-06 is review-gated. No paired experiment or coverage report committed | 30×3 paired report; blind-scored entailment set; coverage report (business ≥85%, safety-branch 100%); 3 identical clean-env runs; GATE-04 semantic job wired + reverse-proof |
| R6 | **Deliberation module absent** (C): `src/egta/deliberation/` not built; FR-03 unverified; blueprint data flow assumes it | FR-03 fails; proposal provenance (claim/evidence/counterargument) missing; INV-05 exposure | C | Blueprint flags it as target-only; contract `AdvisoryProposal` defined | FR-03 30 phase-transition fixtures green; proposal fields hold claim/evidence/counterargument |
| R7 | **Budget ledger crash recovery**: reopen after process kill unverified (cross-process durability) | Could double-count or lose a hold across restarts; NFR-04 restart path | B | SQLite WAL + `BEGIN IMMEDIATE`; single persisted limit set. Reopen-after-kill **untested** | restart test: kill mid-reserve/settle, reopen, hold/absent-call invariants preserved |
| R8 | **`RunSpec.limits` ↔ governor `limits` drift**: two representations of the budget limit | Wrong limit enforced; NFR-01/FR-02 mismatch once wired | B | Governor persists one authoritative limit set; alignment deferred to `app` wiring | single shared limit type; app passes `RunSpec.limits` into governor; test asserts equality |
| R9 | **Permission/approval enforcement gap**: GATE-02 `check-permissions` and GATE-01 `check-approval` **are** wired required checks, but GATE-06 (AI-use log) is review-gated only and GATE-04 (semantic) is not wired; `.opencode/rules.md` present (human-maintained), `Prompt.md` merged #46 | An AI-use-log or semantic omission could merge without a deterministic check; NFR-05/NFR-07 exposure | D (+E) | `check_permissions`/`check_approval`/`governance` are required checks with reverse-proof (#48). GATE-04/GATE-06 rely on human review | GATE-06 as a diff-aware CI check (or recorded human-review confirmation) + GATE-04 semantic job wired, each with reverse-proof |
| R10 | **Stale verification docs**: `final-verification.md` still shows "budget N/A"; older drafts show evidence "in review" | Reviewers may rely on outdated status; GATE-01/GATE-03 evidence 口径 inconsistent | B (this pack) / E | This D2 pack supersedes the stale lines (see `evaluation-logbook.md` §3) | final-verification.md updated to post-#45 status; CI per-suite gate is the live source |

## 2. Threat-model cross-reference (do not duplicate)

`docs/architecture/threat-model.md` enumerates the attack threats (prompt injection,
forge/replay, unauthorized ledger write, secret leakage, DoS via budget, etc.) with
mitigations and residual risk. The mapping from this register to the threat model:

- R1/R2 ↔ budget-DoS / admission-bypass threats.
- R4 ↔ prompt-injection / rule-escape threats (INV-05).
- Ledger tamper threats (INV-01/04/06) are covered by D's merged risk gate; residual
  risk is a local process with SQLite write access (outside the app trust boundary,
  documented in ADR-003).

## 3. Debt-register cross-reference

Open process/technical debt that bears on this pack (see `docs/debt-register.md`):

- `DEBT-FR01-CI` — FR-01 evidence suite CI gating status (owner E; affects NFR-07).
- `DEBT-V3-SEM-1/2/3`, `DEBT-V3-NFR06` — replay/audit/coverage follow-ups (owner E).
- `winner/composite` scoring remains a separate open debt (owner E).

## 4. Register summary

- Open risks: R1–R10 (all six required areas covered: model-admission bypass R1,
  timeout/unknown-usage R2, runner integration R3, context-injection R4, unfinished
  experimental validation R5).
- No risk in this list is claimed closed; each has an explicit close condition tied to
  committed evidence, not to intent.
