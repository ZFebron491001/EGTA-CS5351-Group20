# Reverse blocking test — branch protection (`protect-main`)

**Purpose (G3/E3 evidence):** prove the `protect-main` required checks actually
**block** a merge on failure. A throwaway PR was created with deliberate faults;
it must **never** be merged and its branch is kept as evidence.

- **Reverse-proof PR:** #32 — “[reverse-proof] DO NOT MERGE - verify required checks block”
- **Branch (retained):** `reverse-proof/blocking-test` @ `ce44ea78a5684c00234374e94000fe39145c3a20`
- **Base:** `main` (`6830926` at the time)
- **Result:** `mergeStateStatus = BLOCKED`, `mergeable = MERGEABLE` (blocked by **failing required checks** + pending review, not by conflict). **Not merged; branch kept.**

## Injected faults
1. **Count mismatch (offline gate):** `docs/approvals/test-hash-FR-05-contracts.txt`
   `actual_cases: 223 → 222`. The `offline spec suites (per-suite gate)` reads the
   count from that record (F1 scheme 2) → expected 222 vs actual 223 → **FAIL**.
2. **Lint error (ruff):** `src/egta/evaluation/replay.py` gains an unused
   `import json` → `ruff (strict, full repo)` **F401 → FAIL**.

## Required checks observed (7 configured on `protect-main`)
| Check | Result (reverse-proof) |
|---|---|
| `offline spec suites (per-suite gate)` | **failure** |
| `ruff (strict, full repo)` | **failure** |
| `tests (py3.11/3.12(+NY)/3.13/3.14)` | success |
| `clean-install smoke` | success |

## Blocking evidence (actual CI, run `45007539491` on `ce44ea7`)
- **offline gate** — job `137162364592` → <https://github.com/ZFebron491001/EGTA-CS5351-Group20/actions/runs/45007539491/job/137162364592>
  ```
  contracts: collect-only=223 expected=222
  contracts: passed=223 expected=222 bad={} rc=0 -> FAIL
  ##[error]contracts: expected exactly 222 passed, no skip/xfail/error; got passed=223 bad={} rc=0
  offline gate failed: contracts
  ```
- **ruff** — job `137162364293` → <https://github.com/ZFebron491001/EGTA-CS5351-Group20/actions/runs/45007539491/job/137162364293>
  ```
  F401 [*] `json` imported but unused
    --> src/egta/evaluation/replay.py:14:8
  ```
- **PR state:** `headRefOid=ce44ea7`, `mergeStateStatus=BLOCKED`, `mergeable=MERGEABLE`, `reviewDecision=REVIEW_REQUIRED`.

→ A PR with a failing required check **cannot be merged** under strict up-to-date
protection. Protection is effective.

## Findings / blind spots (recorded, not fixed here)
1. **No GATE-06 (AI-use log) required check.** `protect-main` has the 7 checks above
   but **no** check that a code/test change carries an AI-use log entry → a
   GATE-06-less change would **not** be blocked by CI. (GATE-06 is enforced by
   review today, not by a status check.)
2. **Budget suite is not gated.** `offline-tests` runs contracts / evaluation /
   risk_gate only; `test/offline/budget` (FR-02) is **not** run → a budget
   regression would not be blocked. A budget suite is pre-wired in pending PR #23
   (N/A until `src/egta/budget` + its record exist), but is **not yet active**.
3. Reverse-proof PR #32 and branch `reverse-proof/blocking-test` are **kept** as
   evidence (not merged, not deleted).

## Cleanup / non-contamination
- No changes were made to `main`, to approved tests, or to the contract bundles.
- The injected faults exist **only** on `reverse-proof/blocking-test` and PR #32.
