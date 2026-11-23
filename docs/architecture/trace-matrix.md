# Trace Matrix (D2)

- **Status:** DRAFT — PENDING HUMAN REVIEW. B-authored traceability matrix.
- **Registry of record:** `docs/req/requirements.yaml` (38 IDs, all `confirmed_by_owner`).
  This matrix has **exactly one row per registry ID**; the set must equal the registry
  set (verified: 38 = 38, 0 dup, 0 missing, 0 extra — see §2).
- **Owner of this document:** B (D2 architecture pack). Per-ID owners as in the registry.
- **Related:** `evaluation-table.md`, `evaluation-logbook.md`, `runtime-policy-catalog.md`,
  `docs/req/trace-*.md`, `docs/approvals/`.

> Legend — Status: **green** = implementation + tests/evidence merged and passing in CI;
> **partial** = merged but an end-to-end/paired item is still pending; **doc/process** =
> a governance/submission deliverable evidenced by the actual artefact or human review;
> **gap** = no implementation/test yet (owner + acceptance stated). Financial thresholds
> remain PENDING per `risk-policy.md` and are not marked green by this matrix.

## 1. Trace matrix (one row per requirement ID)

| Req ID | Acceptance / registry ref | Impl / governance location | Test / evidence | Status |
|---|---|---|---|---|
| FR-01 | E1; evidence+citation completeness 100% (`fit_criterion`) | `src/egta/contracts/evidence.py`, `src/egta/evidence/pack.py`,`time_policy.py`,`hashing.py` | `test/offline/evidence/` (pack 37) ; `docs/req/trace-FR-01-evidence*.md`; `docs/evidence/FR-01/` | green |
| FR-02 | E2; calls-without-reserve = 0 | `src/egta/budget/ledger.py`,`__init__.py` (governor) | `test/offline/budget/` (4/4); CI per-suite `passed=4 expected=4` | partial (governor green; gateway path pending, owner B) |
| FR-03 | E3; 30 fixtures obey phase transitions | — (C: `src/egta/deliberation/` absent) | none yet | **gap** — owner C; acceptance: 30 phase-transition fixtures (claim/evidence/counterargument), ≤2 challenge rounds, negatives for skipped phases/unsupported/injected |
| FR-04 | E4; illegal executed = 0 of 100 | `src/egta/risk_gate/` (`service.py`,`rules.py`,`ledger.py`,`policy.py`) | `test/offline/risk_gate/` (139); `docs/evidence/FR-04/` | green (thresholds PENDING in `risk-policy.md`) |
| FR-05 | E5; 30 scenarios → paired reports; replay retains state | `src/egta/evaluation/` (`replay.py`,`report.py`,`metrics.py`,`sink.py`); `src/egta/contracts/` (events/audit) | `test/offline/evaluation/` (28); `test/offline/contracts/` (288); `docs/req/trace-FR-05-contracts.md` | partial (contracts/eval green; paired experiment pending, owner E+B) |
| NFR-01 | budget triple constraint; ≤80000 tokens; no over-admit | `src/egta/budget/ledger.py` (limits, `_exact_add`) | budget suite (4); cost-boundary probe (`evaluation-logbook.md` L-08) | partial (governor enforced; `RunSpec.limits`↔governor alignment pending, owner B) |
| NFR-02 | token median −25%, latency −20% | memory/compression design (C, pending) | none | **gap** — owner E+B; acceptance: 30×3 paired p50/p95 report |
| NFR-03 | entailment ≥90%, citation 100%, support drop ≤5pp | evidence kinds + deliberation (C) | none (no blind-scored set) | **gap** — owner E+C; acceptance: two-scorer blind entailment report |
| NFR-04 | 0 duplicate orders over 100 injections; 30/90/300s timeouts | `src/egta/risk_gate/` (risk side); gateway timeouts absent | `test/offline/risk_gate/test_atomicity_concurrency.py`,`_crash_child.py` | partial (risk restart green; gateway timeout path absent, owner B) |
| NFR-05 | security set ≥50; 0 unauth/secret/injection | `docs/architecture/permission-model.md`, `tools/check_permissions.py` | `test/offline/governance/test_permissions.py`; CI `check-permissions (GATE-02)` (wired, required); reverse-proof #48 shows it **fails** on a bad change | partial — checker **is CI-wired (GATE-02 required)**; the ≥50 security-case set and 0-injection evidence across the full runtime surface remain to be assembled (owner D+E, acceptance: security set green) |
| NFR-06 | 0 cross-module violations; coverage ≥85%/100% | `tools/` static check; module layout | `test/offline/governance/test_spec_manifest.py`; (coverage report absent) | partial (static check; coverage evidence pending, owner E) |
| NFR-07 | 100% changes approved-test + AI-use log | `tools/check_approval.py`; `docs/ai-use-log*.yaml` | CI `check-approval`; `docs/approvals/` | doc/process (gate wired; per-member logs) |
| NFR-08 | 3 identical clean-env offline runs | offline test isolation | this pack's single run: upstream 1412 passed, 1 skipped; 3-run proof absent | partial (single run evidenced; 3-run reproducibility pending, owner E) |
| NFR-09 | run_id/phase/status/duration/reason; unknown cost ≠ 0 | `src/egta/contracts/events.py`,`audit.py` | `test/offline/contracts/test_events.py`,`test_audit.py` (part of 288) | green |
| NFR-10 | no open Must at commit; req change sync | `docs/req/requirements.yaml` + review process | 38/38 `confirmed_by_owner`; review memos | doc/process (enforced by GATE-03 + human review) |
| INV-01 | unauthorized ledger mutations = 0 | `src/egta/risk_gate/service.py` (no bypass param) | `test/offline/risk_gate/test_security_boundaries.py`,`test_actions_quantities.py` | green |
| INV-02 | future items admitted = 0 | `src/egta/evidence/time_policy.py` | `test/offline/evidence/test_time_policy.py` (fixtures E-01..E-31) | green |
| INV-03 | calls without reservation = 0 | `src/egta/budget/__init__.py` (governor); gateway pending | `test/offline/budget/test_admission.py`,`test_reservation_holds.py` | partial (governor green; gateway pending, owner B) |
| INV-04 | duplicate ledger changes = 0 | `src/egta/risk_gate/ledger.py` (unique hash, `BEGIN IMMEDIATE`) | `test/offline/risk_gate/test_identity_idempotency.py` | green |
| INV-05 | external text rule changes = 0 | permission gateway (D) + deliberation isolation (C, absent) | `test/offline/governance/test_permissions.py` (checker); injection set absent | **gap** — owner C+D; acceptance: injection/tool-privilege set green |
| INV-06 | non-atomic commits = 0 | `src/egta/risk_gate/ledger.py` (single tx + outbox) | `test/offline/risk_gate/test_atomicity_concurrency.py`, `_crash_child.py` | green |
| INV-07 | secret leaks = 0 | field allowlist (`risk_gate`), redaction, scan | `test/offline/risk_gate/test_security_boundaries.py`; secret scan | green (D field level; per-member logs remain a duty) |
| GOV-01 | D1; 38 full-field requirements | `docs/req/requirements.yaml`, `req-schema.json`, `tools/check_requirements.py` | `test/offline/requirements/` (24); `docs/approvals/test-hash-D1-check-requirements.txt` | green |
| GOV-02 | D2; `d2_artefact_sections_present >= 11` (the 11 items: blueprint, ADR, invariants, trace matrix, memory, permission, runtime policy, candidate evaluation, evaluation logbook, risk list, option ledger) | `docs/architecture/` pack; the GOV-02 item→file mapping table is in the root `architecture-blueprint.md` §"D2 artefact set" | human review of `docs/architecture/` against the 11-item list | doc/process — **this PR supplies ten of the eleven items as new/updated files**; the remaining items reference existing on-main documents (invariants, permission-model, ADR-003, risk-policy) per the root entry mapping |
| GOV-03 | D3; root AGENTS + 5 items | `AGENTS.md`, `permission-model.md`, `docs/code-governance/mcp-tool-manifest.md` | human review; AGENTS §9 map | doc/process |
| GOV-04 | D4; 4 artefacts | `docs/review-memo.md`(ref), `docs/debt-register.md`, bug diary, verification-constraints | debt register; verification docs | doc/process (review memo/bug diary status per E) |
| GOV-05 | D5; 5 complete transcripts | `transcripts/` | `transcripts/INDEX.md` | partial (A,B,D,E present; C pending — see INDEX) |
| GOV-06 | D6; Report.md 5 reflections | `docs/report/`, `Report.md` (target) | report sections | partial (A/D/E drafts; final Report.md assembly pending) |
| GOV-07 | D7; `gates_blocking_verified eq 6` — the six-gate governance taxonomy (GATE-01..06) is the acceptance scope; repository has real history, CI/CD blocking, branch protection, README | `.github/workflows/ci.yml` (`protect-main` has **10 required checks**), branch protection | `docs/verification/reverse-blocking-test.md`, `docs/evidence/FR-04/gate-reverse-proof.txt` | partial — acceptance is scoped to the **six-gate taxonomy (GATE-01..06)**. `protect-main` configures **10 required checks**; the #48 failure control proves **3** block by failure (`governance`/GATE-03, `check-permissions`/GATE-02, `check-approval`/GATE-01) and #49 shows all 10 pass on a clean change. GATE-04 and GATE-06 are not CI status checks (see those rows); their blocking acceptance remains unverified. |
| GOV-08 | D8; src/ + test/offline + test/live | `src/`, `test/offline/`, `test/live/` | directory presence; upstream provenance kept | doc/process |
| GOV-09 | D9; root Prompt.md plan-first gates | `Prompt.md` (merged #46) | human review of `Prompt.md` | doc/process |
| GATE-01 | two-phase PR + hash-bound approval | `tools/check_approval.py`, CI `check-approval` | `test/offline/governance/test_approval.py`; reverse-proof | green |
| GATE-02 | static/security per commit; sensitive-path review | `ruff`, `check_permissions.py`, CI | `test/offline/governance/test_permissions.py`; CI `check-permissions (GATE-02)` required; reverse-proof #48 shows failure | green (wired as required check) |
| GATE-03 | schema validation on PRs | `tools/check_requirements.py`, CI `governance`/schema | `test/offline/requirements/` (24); CI `governance (exact 38)` required; reverse-proof #48 failure | green (wired as required check) |
| GATE-04 | semantic re-invocation on prompt/model/context change | **no CI semantic job exists** (`ci.yml` has no semantic gate) | none in CI | **gap / review-gated** — not a status check; no reverse-proof. Owner E; acceptance: wiring a semantic job that blocks on threshold failure, with a reverse-proof |
| GATE-05 | regression: full offline passes | CI `offline-tests`/`tests` matrix (required) | per-suite gates; upstream 1412; normal control #49 all-green | green (required checks; not individually fault-injected) |
| GATE-06 | `ai_log_missing eq 0` — every code/test/script/prompt change carries this PR's AI-use record; acceptance: an intentional missing-AI-log PR is blocked by CI | **not a CI status check** — currently enforced by **human review (D/A)** per the `ci.yml` GATE-06 comment | `docs/ai-use-log*.yaml` (per-member logs) | **review-gated / pending verification** — blocking is done by human review today; **CI blocking of a missing AI-use record is still unverified**. Registry acceptance (a missing-AI-log PR must be CI-blocked) is retained as the open target. Owner E+D; acceptance: a diff-aware AI-use-log CI job that blocks a missing-log PR, plus a reverse-proof |
| SUB-01 | ZIP + separate 10-min video; no secrets | submission package (external) | secret scan + ZIP inspection (external) | doc/process (delivery-time; owner A/E) |

## 2. Set-equality verification (matrix vs registry)

Method: extract IDs from `docs/req/requirements.yaml` (`- id:` lines) and the Req ID
column above, compare as sets.

```
registry IDs  : 38
matrix rows   : 38
duplicates    : 0
missing (in registry, not matrix): 0
extra   (in matrix, not registry): 0
```

Registry IDs (in order): FR-01 FR-02 FR-03 FR-04 FR-05 NFR-01..NFR-10 INV-01..INV-07
GOV-01..GOV-09 GATE-01..GATE-06 SUB-01. All present exactly once above.

## 3. Gaps needing C/D/E evidence (explicit, with owner + acceptance)

| Req ID | Owner | What is missing | Acceptance condition to flip to green |
|---|---|---|---|
| gap · FR-03 | C | `src/egta/deliberation/` absent | 30 phase-transition fixtures pass (claim/evidence/counterargument, ≤2 challenge rounds, negatives) |
| gap · NFR-02 | E+B | no paired token/latency experiment | 30×3 paired report: token median −25%, latency −20%, p50/p95 |
| gap · NFR-03 | E+C | no blind-scored entailment set | entailment ≥90%, valid-citation 100%, support drop ≤5pp |
| gap · INV-05 | C+D | no deliberation isolation gate / injection set | injection + tool-privilege test set green (NFR-05) |
| gap · NFR-05 | D+E | permission checker **is** CI-wired (GATE-02); still missing the ≥50 security-case set and 0-injection evidence across the full runtime surface | full security set green (≥50 cases, 0 unauth/secret/injection) |
| gap · GOV-07 | E+D | 10 required checks configured, but reverse-proof covers only 3 (GATE-01/02/03); GATE-04 and GATE-06 are not status checks, so their blocking acceptance is unverified | Reverse-proof for each of the six-gate taxonomy (GATE-01..06) blocking, or per-gate justification recorded as human review |
| gap · GATE-04 | E | no CI semantic job exists; not a status check, no reverse-proof | A semantic CI job that blocks on threshold failure, plus a reverse-proof |
| gap · GATE-06 | E+D | AI-use log is review-gated today; CI blocking of a missing AI-use record is unverified | A diff-aware AI-use-log CI job that blocks an intentional missing-log PR, plus a reverse-proof (registry acceptance retained) |
| gap · NFR-06 | E | no committed coverage report | business ≥85%, safety-branch 100% coverage artefact |
| gap · NFR-08 | E | no 3-run clean-env determinism proof | 3 identical offline runs logged |
| gap · FR-02/INV-03/NFR-01/NFR-04 (B) | B | gateway/runner not built (end-to-end admission + timeout path) | `trace-FR-02-admission.md` acceptance items green in CI |
| gap · GOV-04 | E | review memo / bug diary status confirmation | D4 four artefacts confirmed present |
| gap · GOV-05 | C | C transcript missing | C main transcript + annotations + INDEX row |
| gap · GOV-06 | E (assembly) | final `Report.md` not assembled | 5 reflections + weights in one `Report.md` |
| gap · SUB-01 | A/E | submission ZIP + video (delivery-time) | secret scan + ZIP inspection |
