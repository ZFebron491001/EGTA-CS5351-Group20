# Evaluation Table (D2)

- **Status:** DRAFT — results below were re-run by B on 2026-11-23 against
  `origin/main` `68fb4f3` merged into `docs/B-d2-architecture`. Where a result is
  environment-dependent it says so. Stale values in older verification docs are
  superseded by the rows here (see `evaluation-logbook.md`).
- **Owner of this document:** B (D2 architecture pack). Per-requirement owners are in
  the `Owner` column; B only aggregates and attributes.
- **Environment:** Python 3.12 venv at `/home/cosine/.venvs/cs5351-egta-b1`,
  `PYTHONPATH=src`, `jsonschema==4.26.0` installed (declared dev dep, was missing from
  this venv). CI installs `.[dev]`.

> Command convention: run from repo root with `PYTHONPATH=src`. The budget/contracts/
> evaluation suites use `-m spec`; `risk_gate`/`requirements` use the default marker
> filter (`-m "not integration and not spec"` is excluded automatically by addopts).

## 1. Acceptance criteria by requirement / quality attribute

| Requirement / QA | Acceptance criterion (from `requirements.yaml`) | Test command / case | Evidence location | Current result |
|---|---|---|---|---|
| FR-01 Evidence Pack | evidence-field & citation completeness = 100% on fixed scenarios | `pytest -m spec test/offline/evidence -q` | `docs/req/trace-FR-01-evidence*.md`, `docs/evidence/FR-01/` | **37 passed, 13 deselected** (merged #43) |
| FR-02 Budgeted Run | calls executed without prior reserve = 0 | `pytest -m spec test/offline/budget -q` (4 cases) | `docs/req/trace-FR-02-budget-reservation.md`, `…-admission.md` | **4 passed** (merged #22/#45); end-to-end gateway **PENDING** |
| FR-03 Structured Deliberation | 30 fixtures obey phase transitions | `pytest -m spec test/offline/deliberation` | (no module yet) | **PENDING — C, `src/egta/deliberation/` absent** |
| FR-04 Risk Gate + Ledger | illegal suggestions executed = 0 (of 100 cases) | `pytest test/offline/risk_gate -q` | `docs/evidence/FR-04/` | **139 passed** (merged) |
| FR-05 Comparison & Audit | 30 fixed scenarios → paired reports; replay retains terminal state | `pytest -m spec test/offline/evaluation -q` + contracts | `docs/req/trace-FR-05-contracts.md` | E2 **28 passed**; contracts **288 passed**; paired experiment **PENDING** |
| NFR-01 Budget triple constraint | max_total_tokens ≤ 80000; no over-budget admission | budget spec + stress | `src/egta/budget/ledger.py` | governor enforced; `RunSpec.limits` ↔ governor alignment **PENDING** |
| NFR-02 Token/latency reduction | token median −25%, latency −20% | paired 30×3 experiment | (no report) | **PENDING — experiment not run** |
| NFR-03 Evidence entailment | entailment ≥90%, citation validity 100%, support drop ≤5pp | human-scored set | (no report) | **PENDING — needs blind-scored set** |
| NFR-04 No duplicates under injection | duplicate paper orders = 0 across 100 injections | risk restart/timeout tests | `docs/evidence/FR-04/` | risk-side restart tests (merged); gateway timeout path **PENDING** |
| NFR-05 Security set ≥50 | unauthorized = 0, secret-scan = 0, injection escapes = 0 | permission/malicious/scan | `tools/check_permissions.py`, `permission-model.md`, CI `check-permissions (GATE-02)` | checker **is CI-wired (GATE-02 required, reverse-proof #48)**; ≥50-case set + 0-injection across full runtime surface **PENDING (D+E)** |
| NFR-06 Boundaries & coverage | cross-module violations 0; business coverage ≥85%; safety-branch 100% | `tools/` static + coverage | (coverage report) | static check wired; **coverage evidence PENDING (E)** |
| NFR-07 Governed changes | 100% code changes have approved tests + AI-use log + negative test | CI/PR + `check_approval` | `docs/ai-use-log*.yaml` | gate wired; per-member logs tracked |
| NFR-08 Determinism | 3 identical offline runs in clean env | network-blocked offline run | this table §2 | upstream **1412 passed, 1 skipped**; 3-run reproducibility **PENDING** |
| NFR-09 Event completeness | unknown cost never shown as 0 | contracts/events + evaluation | `test/offline/contracts` | contracts **288 passed** |
| NFR-10 Requirement change sync | no open Must at commit | registry diff + review | `docs/req/requirements.yaml` | 38/38 confirmed_by_owner; enforcement is process |
| INV-01…07 | see `invariants.md` | risk/budget/evidence suites | `docs/evidence/` | INV-01/04/06 (risk 139), INV-02 (evidence), INV-03 (budget 4) covered; INV-05 (C) **PENDING** |

## 2. Suite results (re-run 2026-11-23, this worktree)

| Suite | Command | Result |
|---|---|---|
| contracts (full dir) | `pytest -m spec test/offline/contracts -q` | **288 passed** |
| evaluation (E2) | `pytest -m spec test/offline/evaluation -q` | **28 passed** |
| risk_gate | `pytest test/offline/risk_gate -q` | **139 passed** |
| **budget (FR-02)** | `pytest -m spec test/offline/budget -q` | **4 passed** (4/4 frozen) |
| evidence (FR-01/INV-02) | `pytest -m spec test/offline/evidence -q` | **37 passed, 13 deselected** |
| requirements (D1 checker) | `pytest test/offline/requirements -q` | **24 passed** (needs `jsonschema`) |
| upstream | `pytest tests -q` | **1412 passed, 1 skipped, 1 deselected** |
| static lint | `ruff check .` | **All checks passed** |

### Budget cost-boundary probe (B, exact money)

With `max_cost_usd = 1.00`: a request of exactly `1.00` is **admitted**; a further
`1E-29` USD request is **refused** (`BudgetDenied`, `reason_code="BUDGET_DENIED"`).
Verified locally and by the merged governor's `_exact_add` widened-precision comparison.

## 3. Module-level e2e (E, `tools/e2e_g1.py`) — truthful scope

E's G1 driver demonstrates **normal approved** and **declined/stale** routes. The
**over-budget** route was **N/A when E ran it** (budget not yet implemented at that
time). Since #45 merged, the governor exists, but the **end-to-end over-budget route
through the gateway is still not demonstrated** (gateway/runner not built). This is a
documented gap, owner B — see `risk-list.md` R1/R3 and `evaluation-logbook.md`.

## 4. What is NOT yet validated (explicit gaps)

| Item | Owner | Why it is open | Acceptance condition |
|---|---|---|---|
| Unified runner + gateway zero-budget / fallback / interrupt paths | B | `src/egta/app`, `src/egta/adapters` not built | `trace-FR-02-admission.md` acceptance items green in CI |
| Paired baseline/enhanced experiment (NFR-02/FR-05) | E+B | experiment not run | 30×3 paired report committed |
| Human evidence-scoring (NFR-03) | E+C | no blind-scored set | entailment ≥90%, citation 100% |
| Deliberation module (FR-03) | C | module absent | 30 phase-transition fixtures pass |
| Coverage evidence (NFR-06) | E | no committed coverage report | business ≥85%, safety-branch 100% |
| Gateway timeout / 429 / crash injections (NFR-04) | B | gateway absent | 100-injection zero-duplicate report |
| Reproducible 3-run offline determinism proof (NFR-08) | E | single run recorded | 3 identical clean-env runs logged |
