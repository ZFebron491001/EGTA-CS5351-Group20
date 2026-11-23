# Evaluation Logbook (D2)

- **Status:** DRAFT — PENDING HUMAN REVIEW. Append-only chronological log of
  **verification events**. Each row records when/what/where/how, with a SHA or PR and
  a real command result. This logbook does not claim more than the cited evidence.
- **Owner of this document:** B (D2 architecture pack); each event is attributed.
- **Related:** `evaluation-table.md` (the current-state summary), `docs/evidence/`,
  `docs/verification/final-verification.md`, `docs/verification/g3-readiness.md`,
  `docs/verification/reverse-blocking-test.md`.

> Rule: an event is only listed if there is a recorded command + result (from CI, a
> committed evidence file, or a local run whose source is stated). "Local" means the
> evidence exists only in a worktree/session, not (yet) as a committed file.

## 1. Chronological verification events

| # | Date | Event | PR / SHA | Command / action | Result | Evidence |
|---|---|---|---|---|---|---|
| L-01 | 2026-11-21 | Upstream offline baseline | `9fa1196` (v0.7.1 baseline) | `~/.venvs/cs5351-egta-b1/bin/python -m pytest tests -m "not integration"` (Python 3.12.16, pytest 9.2.0) | 1412 passed, 1 skipped, 1 deselected | `docs/evidence/FR-02/upstream-offline-baseline.md` at local commit **`57cd5f2`** (branch `docs/B-baseline`; **local-only, not on main**) |
| L-02 | 2026-11 | Structured-output fallback probe (local gateway) | `57cd5f2` (local) | NormalizedChatOpenAI + `httpx.MockTransport`; allowance 2/1/0 | transport 2/1/0 | `docs/evidence/FR-02/structured-fallback-probe.md` (**local/B**) |
| L-03 | 2026-11 | FR-02 budget spec frozen (RED) | #22 (`a47c29c`) | `pytest -m spec test/offline/budget` | 4 collected, 4 failed (expected RED; `egta.budget` absent) | `test/offline/budget/`, `docs/req/trace-FR-02-*.md` |
| L-04a | 2026-11 | FR-01 evidence contracts (types + specs) | #21 (merged `141547a`) | `pytest -m spec test/offline/contracts/test_evidence_contracts.py` | FR-01 evidence-contract tests pass after `EvidenceItem`/`EvidencePack` types land | `docs/req/trace-FR-01-evidence-contracts.md`, `docs/approvals/test-hash-FR-01-contracts.txt` |
| L-04b | 2026-11 | FR-05 contracts + E2 evaluation | #18 (merged `10ee52d`) | `pytest -m spec test/offline/contracts` (7-file gate) + `pytest -m spec test/offline/evaluation` | contracts 223 / E2 28 green | `docs/verification/final-verification.md` §1 |
| L-05 | 2026-11 | E4 final verification | #34 (`71cd638`) | contracts 223; full dir 288; E2 28; risk 139; upstream 1412 | all pass; **budget N/A at that time** | `docs/verification/final-verification.md` |
| L-06 | 2026-11 | G3/E3 reverse-blocking (required checks) | #33, #48/#49/#50; `docs/evidence/FR-04/gate-reverse-proof.txt` | failure control PR #48 (injected faults) + normal control PR #49 | `protect-main` has **10 required checks**; #48 shows **3** block by failure (`governance`, `check-permissions`, `check-approval`); #49 shows all 10 pass. GATE-04/GATE-06 are not status checks. | `docs/verification/reverse-blocking-test.md` |
| L-07 | 2026-11-23 | **FR-02 budget governor merged** | **#45 (`eafaff4`)** | CI `offline spec suites` per-suite gate | **budget: passed=4 expected=4 -> OK** | CI run on PR #45 head `968999b`; `docs/approvals/test-hash-FR-02-budget.txt` |
| L-08 | 2026-11-23 | #45 revision (shared ReasonCode + decimal narrowing) | #45 `968999b` | mypy (2 err → 0), ruff, 4 frozen cases, cost probe | mypy clean, ruff clean, 4 passed, $1.00 admit / +1E-29 refuse | PR #45 CI; local mypy via uvx |
| L-09 | 2026-11-23 | D2 re-run in this worktree | `docs/B-d2-architecture` @ `origin/main` `68fb4f3` | budget 4, risk 139, E2 28, contracts 288, evidence 37(+13 desel), requirements 24, upstream 1412/1/1, ruff clean | all pass | this file §2; `evaluation-table.md` §2 |

## 2. D2 re-run raw results (this worktree, 2026-11-23)

Environment: `/home/cosine/.venvs/cs5351-egta-b1` Python 3.12, `PYTHONPATH=src`,
`jsonschema==4.26.0` installed locally (declared dev dep, absent by default in this
venv — the requirements suite needs it; CI installs `.[dev]`).

```
pytest -m spec test/offline/budget -q          -> 4 passed
pytest test/offline/risk_gate -q               -> 139 passed
pytest -m spec test/offline/evaluation -q       -> 28 passed
pytest -m spec test/offline/contracts -q        -> 288 passed
pytest -m spec test/offline/evidence -q         -> 37 passed, 13 deselected
pytest test/offline/requirements -q             -> 24 passed   (with jsonschema)
pytest tests -q                                 -> 1412 passed, 1 skipped, 1 deselected
ruff check .                                    -> All checks passed
```

Budget cost-boundary probe (exact money, `max_cost_usd=1.00`):
exactly `1.00` → `Reservation` (admitted); additional `1E-29` → `BudgetDenied`
(`reason_code="BUDGET_DENIED"`).

## 3. Status corrections to older verification docs (truthful supersession)

| Older claim | Source | Corrected status (supersedes) |
|---|---|---|
| "FR-02 budget: N/A — no `src/egta/budget`" | `final-verification.md` §1 (L-05) | **Superseded by L-07/L-09:** `src/egta/budget` merged (#45); budget suite **4 passed**. End-to-end gateway path still pending. |
| "over-budget route: N/A — budget not implemented" | e2e G1 (L-05) | **Partially superseded:** the governor now exists, but the **end-to-end over-budget route through the gateway is still not demonstrated** (gateway not built). Remains a gap (owner B). |
| Evidence "in review, PR #43" | older blueprint drafts | **Superseded:** PR #43 **merged** (`7c3fbd4`). |

## 4. Evidence that exists only locally (not yet committed)

- L-01/L-02 baseline + fallback probe: recorded in `docs/evidence/FR-02/` on the
  `docs/B-baseline` branch (`57cd5f2`), **not on `main`** at time of writing. Source:
  B local branch. Treat as supplementary, not K-gated evidence.
- L-08 mypy run: ad-hoc via `uvx` (project does not vendor mypy); the CI gate does not
  run mypy. Recorded here for completeness; mypy is not a project gate.
