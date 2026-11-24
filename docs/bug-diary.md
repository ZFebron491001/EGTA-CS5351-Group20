# Bug Diary

Significant defects found during FR-04 / D3 / D4 work. Each entry records the symptom,
reproduction, classification, root cause, fix, regression and remaining gap. Minor style
issues are omitted.

## BUG-01 — risk-gate outbox hash rejected by contracts.audit

- **Symptom:** E's review of #20 found that `risk_gate` outbox events would be rejected by
  `contracts.audit.verify_payload` / replay. Stored and recomputed hashes differed
  (`618df15d…` vs `a159cae7…` for the same event).
- **Reproduction:** construct a `RunEvent` from the persisted outbox row; call E's real
  `contracts.audit.verify_payload`. The risk-gate timestamp rendered as `+00:00`, while
  Pydantic JSON and the shared canonicaliser render UTC as `...Z`.
- **Classification:** cross-module contract / audit integrity defect (blocking).
- **Root cause:** local `payload_hash` canonicalisation was not byte-compatible with
  `contracts.audit`; the hash was internally deterministic but not mutually verifiable.
- **Fix:** `6bad169` — hash and store the outbox timestamp in the shared `Z` form; use the
  same sorted compact JSON projection. No test expectations changed.
- **Regression:** #20 re-verified with the real contracts code; stored == recomputed; full
  risk_gate 139 stayed green. Evidence: `docs/evidence/FR-04/impl-green.txt`.
- **Invariant/gap:** INV-06 and NFR-09. Residual: final integration should import the
  shared event type rather than keep a local adapter.

## BUG-02 — date-only evidence pack crashes canonicalisation

- **Symptom:** A's E-07 test (`test_pack_hash_matches_risk_gate_canonical[E-07]`) raised
  `TypeError: cannot canonicalize <class 'datetime.date'>`; the risk gate would classify a
  legitimate date-only pack as `INTEGRITY_VIOLATION`.
- **Reproduction:** construct a pack whose `published_at` is `date(2026, 10, 1)` and call
  `egta.risk_gate.canonical.recompute_evidence_hash`.
- **Classification:** A→D interface / audit false rejection.
- **Root cause:** `_normalize` handled `datetime` but not its `date` parent; the E-07
  fixture deliberately keeps day precision.
- **Fix:** `95d6bb9` (PR #38) — add a `date` branch **after** the `datetime` branch and
  render `YYYY-MM-DD`; test-first regression `276a020` added to EVD-05. Full risk_gate
  remained 139.
- **Regression:** E-07 equality now compares date-only and ISO-string packs; A independently
  recomputed the per-file hash/aggregate (`eae1f93c…`, `f3c45de2…`). Evidence:
  `docs/evidence/FR-04/date-only-canonical-fix.txt`.
- **Invariant/gap:** INV-02/FR-04. No remaining D-side gap; the record was re-signed by A.

## BUG-03 — GATE-01 false TEST_DRIFT on a normal implementation PR

- **Symptom:** reverse-proof normal control #49 (only an allowed `src/egta/risk_gate/` file)
  failed `check-approval (GATE-01)` even though the approved tests were unchanged.
- **Reproduction:** `tools/check_approval.py` with `--implementation-base` set to the
  FR-04 record's old `test_content_commit` (`276a020`), after later test merges.
- **Classification:** CI gate false positive (not a product bug).
- **Root cause:** E3 used the record's test commit as the implementation base; later test
  changes (pack, precedence, budget) appeared as `TEST_DRIFT` against the risk-gate record.
- **Fix:** #50 (`0fef55b`) — use the PR base for implementation PRs; a test/spec PR whose
  record commit is not in base is N/A; an applicable missing record fails closed.
- **Regression:** #48 failure control still fails governance/check-permissions/
  check-approval; #49 normal control passes all 10 required checks. Evidence:
  `docs/evidence/FR-04/gate-reverse-proof.txt`.
- **Invariant/gap:** GATE-01. Residual: CI-only and some tools/contracts paths remain
  human/code-owner-reviewed.

## BUG-04 — base evidence cutoff fixture mismatch

- **Symptom:** EVD-05 expected `REVIEW/EVIDENCE_MISSING` but the base fixture used
  `cutoff_offset=-600s` while `make_evidence` defaults to `-30s`.
- **Reproduction:** run the approved risk-gate suite against the base pack and inspect the
  cutoff/price-time relationship.
- **Classification:** test fixture / expected-outcome defect.
- **Root cause:** the base pack and the test fixture used different cutoff conventions; the
  expected outcome was therefore not discriminating.
- **Fix:** `d5cf2ea` — one-line base cutoff alignment to `-30s`; no expected outcome or
  count change.
- **Regression:** PR #17 merge `b245bdb`; 139 tests green; approval record re-bound by A.
- **Invariant/gap:** INV-02/FR-04. None remaining.

## BUG-05 — evidence approval routing pointed at a stale record

- **Symptom:** A's #43 implementation failed `check-approval (GATE-01)` with a record
  problem even though its own tests were approved; the evidence directory was routed to
  the old `test-hash-FR-01-evidence.txt` record, which lacked the new reviewed-head binding.
- **Reproduction:** run `check_approval` on a PR changing `test/offline/evidence/` or
  `src/egta/evidence/`; the old evidence record has no reviewed head and a stale base.
- **Classification:** CI routing / approval-record coverage defect.
- **Root cause:** the initial CI map treated the whole evidence directory as one record;
  the new pack/precedence records were not selected, and the old record was not repaired.
- **Fix:** #47 split per-file evidence routing and added the FR-02 budget record; #50 fixed
  the implementation-base semantics. A repaired the old record separately.
- **Regression:** #43 merged `dfb7a3f`; #44 was superseded by #51; pack/precedence records
  are now checked independently. Evidence: `docs/evidence/FR-04/gate-reverse-proof.txt`.
- **Invariant/gap:** GATE-01/GATE-03. Residual: tools/contracts paths are still not fully
  automated and remain a human/code-owner review boundary.

## BUG-06 — GATE-02 build-e role still rejected FR-02 integration docs

- **Symptom:** after #68 added `test/offline/integration/` to the build-e role detector,
  #67's `check-permissions (GATE-02)` still failed with `PATH_NOT_ALLOWED` for the three
  FR-02 docs under `docs/req/`.
- **Reproduction:** run `tools/check_permissions.py --role build-e` on the #67 diff
  (`base 804bdfb`, `head e1b0f62`); the integration test paths pass, but
  `docs/req/acceptance-FR-02-integration.md`, `spec-FR-02-gateway.md` and
  `trace-FR-02-gateway.md` are outside the build-e allowlist.
- **Classification:** GATE-02 policy/allowlist gap, not a product or test-content bug.
- **Root cause:** #68 fixed the role inference and the FR-02-integration approval record,
  but the three FR-02 spec/trace/acceptance docs were still not in the build-e writable
  scope. A single role must cover both the integration tests and their module docs.
- **Fix:** add the three exact FR-02 integration docs to `ALLOWED_PREFIXES["build-e"]` in
  `tools/check_permissions.py`; rerun the checker on #67. No test/CI/approval content is
  changed.
- **Regression:** `check_permissions` on #67 returns `OK: no permission violations`;
  governance remains 38 passed; ruff clean. #67 must be re-synced after this fix.
- **Invariant/gap:** GATE-02 / FR-02. Residual: `docs/req/` is not a general build-e
  writable path; only the named FR-02 integration docs are allowed.
