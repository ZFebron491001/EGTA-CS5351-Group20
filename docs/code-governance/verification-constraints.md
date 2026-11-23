# Verification Constraints

- **Owner:** E (D4 compilation); D contributes the risk-gate/governance constraints and
  verifies the D-side evidence.
- **Scope:** the structural, regression and behavioural checks that make the EGTA
  implementation evidence reproducible. This file states the constraints; it is not a
  claim that every check is currently green on every branch.

## 1. Three verification layers

### Structural

- Module boundaries: a module may import `egta.contracts` and its own module; public
  extensions use the injected ports/contracts. `tools/check_permissions.py` checks role
  allowlists, protected paths, cross-module imports and credential references.
- Requirement traceability: `tools/check_requirements.py` validates the registry against
  `docs/req/req-schema.json` and checks ID uniqueness, references and Must coverage.
- Test-first ancestry: `tools/check_approval.py` verifies the approval record, approver
  identity, registry membership, test-content commit, per-file/aggregate hashes, reviewed
  head and implementation ancestry.
- CI must not be weakened to make a change pass; CI/CODEOWNERS/ruleset changes are human
  review paths.

### Regression

- Frozen upstream and offline suites must remain green; previously passing tests are not
  deleted or skipped.
- Offline suites are network-free and use fake ports/temp SQLite. Expected counts are
  exact: risk_gate **139**, governance **38**, contracts **223**, evaluation **28**,
  budget **4**, and evidence spec **37** (pack 33 + precedence 4; time-policy 13 is
  not-spec).
- Any skip, xfail, xpass or error fails the per-suite gate; a missing module directory may
  be N/A, but an implemented module with a missing approval record fails closed.
- The 10 required checks on `protect-main` are: tests (3.11/3.12-NY/3.13/3.14),
  clean-install smoke, strict ruff, offline per-suite gate, governance, check-permissions
  and check-approval.

### Behavioural

- FR-04: invalid quantity, insufficient funds, over-position, stale portfolio version,
  expired approval, duplicate proposal, audit failure and date-only evidence are all
  exercised; illegal suggestions executed = 0; duplicate ledger changes = 0.
- FR-01: future and undated evidence are excluded; a date-only value on the as-of UTC date
  is future/unavailable; a tampered item is integrity-rejected; the A→D pack hash equality
  is executed against the risk-gate canonical helper.
- FR-05/E2: comparison is per-side and missing metrics are `INCOMPLETE/MISSING_METRIC`;
  threshold breaches yield `REVIEW`; audit replay verifies hash chain and anchor.
- Budget: reserve/settle, unknown-usage hold, concurrency and persisted limits.
- Governance: 32 permission/approval cases plus 6 manifest meta-tests; failure controls
  prove the required checks block.

## 2. Required commands (current main expectations)

```bash
python -m pytest test/offline/risk_gate -q          # 139 passed
python -m pytest test/offline/governance -q         # 38 passed
python -m pytest -m spec test/offline/evidence -q   # 37 passed
python -m pytest -m "not spec" test/offline/evidence -q  # 13 passed, 37 deselected
python -m pytest -m spec test/offline/contracts -q  # FR-05 isolated files: 223
python -m pytest -m spec test/offline/evaluation -q # 28 passed
python -m pytest -m spec test/offline/budget -q     # 4 passed
python -m ruff check .
python -m mypy src/egta/risk_gate
python tools/check_permissions.py --repo . --base <base> --head <head> --role <role>
python tools/check_approval.py --repo . --record <record> \
  --implementation-base <base> --implementation-head <head> \
  --registry docs/req/requirements.yaml --author <login>
```

The CI per-suite gate is authoritative for the exact counts; local runs are evidence only
until the Actions run is attached.

## 3. Test-first and approval constraints

- A test/spec PR is independently reviewed and merged before the implementation PR.
- The implementation must descend from the approved test commit; a post-approval test
  content change voids the approval and requires a new test hash/review.
- The author/implementation agent does not approve the test baseline or the PR.
- Approval records are human-only: a missing/PENDING/self-approved/wrong-hash record is a
  failure, not a green-CI inference.
- D's date-only amendment (`276a020`, aggregate `f3c45de2…`) and the #17/#25/#43 records are
  examples; the record-only completion is separate from the GitHub review.

## 4. Offline/live and security constraints

- Offline CI must not use the network; live data/provider tests are skipped by default and
  run only in a controlled environment with `EGTA_LIVE_DATA=1`.
- Live credentials are injected by a controlled runner; they never enter the coding-agent
  log or the repository.
- RiskGate has no LLM, broker, network or arbitrary file-write path; the ledger/outbox is
  the only write boundary.
- Runtime `.opencode`/`.agent` enforcement is not claimed merely because a policy file
  exists; a real refusal test or CI blocker is required.

## 5. Coverage and honesty constraints

- FR-04 total line coverage is **92%**; `policy.py` is **80%**. The 100% security-branch
  coverage target is **not claimed**; uncovered defensive branches are follow-up debt.
- A failing or missing sample is reported, not deleted; `BLOCKED/INCOMPLETE/REVIEW` are not
  counted as successful trades or successful comparisons.
- An unconfigured/incompatible policy is rejected as `BLOCKED/INCOMPATIBLE_STATE`; fixture
  values (`freshness=240`, `fee_bps=10`, `slippage_bps=0`) are test-only, not product
  defaults.
- ADR-003 and the product risk policy remain PROPOSED; `DEBT-FR04-POLICY-APPROVAL` must be
  carried into submission evidence until a human approves the exact policy and hash.

## 6. Known residual boundaries

- CI-only changes and some tools/contracts paths remain human/code-owner-reviewed rather
  than fully automated by the checkers.
- GATE-03 schema, GATE-04 semantic and GATE-06 AI-use are not all expressed as required
  status checks; GATE-04 depends on C's semantic runner, and GATE-06 is review-enforced.
- C's FR-03 deliberation and transcript/report are outside D's module; D does not claim
  them. B's architecture/application package is B-owned.
- The final release checklist and submission ZIP/video are E's assembly, not proof that
  every upstream or external dependency is complete.
