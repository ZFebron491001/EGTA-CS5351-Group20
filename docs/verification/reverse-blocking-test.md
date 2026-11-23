# Reverse blocking test — branch protection (`protect-main`)

**Purpose (G3/E3 evidence):** prove the `protect-main` required checks actually
**block** a merge on failure, and **pass** on a clean in-scope change. Throwaway
PRs were used as controls; the failure control must **never** be merged, and its
branch is kept as evidence.

> **Updated per D review (#33):** the previous version referenced the closed
> throwaway PR #32 and "7 required checks". `protect-main` now has **10 required
> checks** (three new gates added: `governance (exact 38)`,
> `check-permissions (GATE-02)`, `check-approval (GATE-01)`). The reverse proof is
> now recorded against the controls below.

## Current required checks on `protect-main` (10)
| # | Check | Added by |
|---|---|---|
| 1 | `offline spec suites (per-suite gate)` | E3 (pre-existing gate set) |
| 2 | `ruff (strict, full repo)` | E3 |
| 3 | `tests (py3.11)` | E3 |
| 4 | `tests (py3.12, America/New_York)` | E3 |
| 5 | `tests (py3.13)` | E3 |
| 6 | `tests (py3.14)` | E3 |
| 7 | `clean-install smoke` | E3 |
| 8 | **`governance (exact 38)`** | E3 six-gate wiring (#40) |
| 9 | **`check-permissions (GATE-02)`** | E3 six-gate wiring (#40) |
| 10 | **`check-approval (GATE-01)`** | E3 six-gate wiring (#40) |

## Failure control — PR **#48** (CLOSED, not merged)
- **PR:** #48 — “[reverse-proof] DO NOT MERGE - gate failure cases”
- **Head:** `86b11dd`; **base:** `main`
- **State:** `mergeStateStatus = BLOCKED`, `mergeable = MERGEABLE` (blocked by
  **failing required checks + pending review**, not by conflict). **Not merged; closed.**
- **Injected faults (deliberate):** changes that violate the three new gates.
- **Observed check results** (head `86b11dd`):
  | Check | Result |
  |---|---|
  | `governance (exact 38)` | **failure** |
  | `check-permissions (GATE-02)` | **failure** |
  | `check-approval (GATE-01)` | **failure** |
  | the other 7 (offline/ruff/4×tests/smoke) | success |

  → A change that violates governance / permissions / approval **cannot be merged**.

## Normal control — PR **#49** (CLOSED, not merged)
- **PR:** #49 — “[reverse-proof] DO NOT MERGE - normal in-scope pass”
- **Head:** `bf5068e`; **base:** `main`
- **State:** `mergeStateStatus = BLOCKED`, `mergeable = MERGEABLE`,
  `reviewDecision = REVIEW_REQUIRED` — blocked **only by review**, **not** by any check.
- **Observed check results** (head `bf5068e`): **all 10 required checks success**
  (`governance`, `check-permissions`, `check-approval`, offline, ruff, 4×tests, smoke).

  → A clean, in-scope change passes every required check; only human review
  remains as the gate. Confirms the gates are **not** blanket-failing.

## GATE-01 false-positive fix — PR **#50** (MERGED)
- **PR:** #50 — “fix(CI): use PR base for GATE-01 approval checks”, **merged** as
  `0fef55b` (2026-11-23T06:44:04Z).
- On the failure control the first run surfaced a **false `TEST_DRIFT`** in
  `check-approval (GATE-01)` (it compared against the wrong base when a test-file
  diff was present). #50 corrected GATE-01 to use the **PR base**; after that the
  normal control (#49) reports GATE-01 = success, so #49's 10/10 is the
  post-fix authoritative normal run.

## Budget gating status (updated)
- **#47 added the FR-02 budget approval record**
  (`docs/approvals/test-hash-FR-02-budget.txt`, `actual_cases: 4`), so the
  pre-wired `offline-tests` budget branch now has a count record.
- **Remaining activation dependency = #45** (implementation `src/egta/budget`).
  Until #45 merges, the budget suite is still `N/A` (module dir absent); after
  #45 + the #47 record, the budget gate **enforces** the 4 cases.
- Correction to the previous wording: the budget suite is **no longer
  un-gated-by-design**; it is **record-ready (#47) and awaiting the #45 module**.

## Findings / blind spots (recorded, not fixed here)
1. **No GATE-06 (AI-use log) required check.** `protect-main` has the 10 checks
   above but **no** status check that a code/test change carries an AI-use log
   entry → GATE-06 is enforced by **review** today, not by a required check.
2. **Budget activation pending #45** (see above); record is in place.

## Cleanup / non-contamination
- No changes were made to `main`, to approved tests, or to the contract bundles.
- The injected faults exist **only** on the throwaway branches / PRs #48 and #49
  (both closed, **not merged**). They are retained as evidence, not deleted.
