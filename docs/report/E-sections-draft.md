# D6 Report — E sections (DRAFT for compilation; not submitted as final)

> Scope: E = Comparison / Audit events / CI-CD (FR-05, NFR-06–09). Draft only, gathered
> from verified repo state (main `141547a`; contracts 223 / E2 28 / risk_gate 139 / budget N/A
> verified at HEAD; E PRs #3/#8/#11/#12/#18). Numbers are real; §3 is explicitly not-completed.

## 1. Evaluation / Verification Methods (FR-05, NFR-08, NFR-09)

**FR-05 — Comparison & Audit Report.** FR-05 is delivered in two layers:
- **Contract layer** (`src/egta/contracts/{events,audit,evaluation,manifest}.py`): an
  immutable `RunEvent` with a SHA-256 hash chain (`payload_hash`/`prev_event_hash`), a
  12-field `Receipt`, and `compare_runs` producing an `EvaluationResult`. Comparison is
  **per-side** over observed metrics: a rubric metric absent on either side is
  `INCOMPLETE/MISSING_METRIC`; a threshold breach yields `REVIEW` with per-side
  `THRESHOLD_VIOLATION` failures; a comparable pair yields `COMPLETE`. The final
  `winner/composite` score is deliberately deferred (tracked debt) so the system
  cannot claim an unproven "enhanced win".
- **Evaluation layer** (`src/egta/evaluation/{replay,report,metrics,sink}.py`): offline
  `replay` reconstructs run state by `(run_id, sequence)` with dedupe and hash-chain +
  anchor verification; `report.pair_report` delegates to `compare_runs`; `metrics`
  aggregates with typed rubrics; `sink` is a real `SqliteAuditSink` (idempotent,
  conflict-detecting, fail-closed with rollback).

**NFR-08 — Reproducibility.** Offline suites run in a pinned environment (`egta`,
Python 3.12.16, pytest 9.2.0) with a fixed clock, no network, temp SQLite, and content
hashes (test aggregate + spec bundle). The audit log is hash-chained; the manifest
carries `manifest_hash` over a canonical JSON.

**NFR-09 — Observability.** Every `RunEvent` carries `run_id/sequence/phase/timestamp/
status/metrics/reason_code`; the risk gate writes an outbox event per verdict; unknown
cost/usage is represented explicitly (`MISSING_USAGE`) rather than as zero.

Verification evidence: contracts **223** / E2 **28** passed; risk_gate **139**;
upstream **1412**; ruff + mypy clean (see `docs/verification/final-verification.md`).

## 2. CI / Six-Gate Design

The CI is GitHub Actions. The implemented, **required** job is the offline gate:
- **`offline-tests` (per-suite gate):** each suite independently detects its module dir
  (`src/egta/{contracts,evaluation,risk_gate,budget}`) and gates on an **exact real-run
  passed count** (FR-05 **223**, E2 **28**, risk_gate **139**; budget **N/A** until
  FR-02) with any skip/xfail/error failing the job; FR-05 is isolated to 7 explicit files
  so other specs (e.g. FR-01 evidence) cannot contaminate its count. Counts are read from
  the approval records (`actual_cases`) — no hard-coded drift. 7 required status checks
  are active on `protect-main` (tests ×4 incl. a non-UTC TZ, clean-install smoke, ruff,
  offline gate), with strict up-to-date and non-author approval.

**Reverse-blocking proof (G3):** PR **#32** deliberately injected two faults — a count
mismatch (approval record 222 vs collected 223) and a ruff error (unused import) — and
both required checks **failed**, leaving the PR `mergeStateStatus=BLOCKED` (run
`45007539491`). Evidence preserved in #32/#33. This demonstrates the gate *blocks*, not
just reports.

**Six gates:** GATE-01 (test-first approval) and GATE-02 (static/security/permission) have
their checkers implemented in `tools/check_permissions.py` / `tools/check_approval.py`
(PR #29); wiring them into CI as `check-permissions`/`check-approval` jobs is the planned
follow-up E3 step (with `::notice:: N/A` while prerequisites like the D1 registry are
absent). GATE-03 (schema), GATE-04 (semantic), GATE-05 (regression) and GATE-06 (AI-use)
are enforced by review + the offline/regression suites at this stage; full CI wiring is
tracked in the G3 readiness sheet.

## 3. Control / Ablation Experiments

The controlled-experiment design is **pre-registered but not yet executed** in this code
line. `ExperimentManifest` fixes the four variants (B0 baseline, B1 enhanced, B2/B3
ablations), the shared snapshot, model/prompt/code/policy hashes, a typed
`metrics_rubric`, and an independent `quality_rubric`; `compare_runs` guarantees that
differing snapshots/hashes yield `INCOMPLETE` and are **not** counted as wins. The actual
baseline-vs-enhanced paired runs (quality, tokens, cost, latency) are scheduled for the
evaluation day and will be reported as paired distributions (p50/p95), with failure
samples counted per the failure-sample accounting (BLOCKED/INCOMPLETE/REVIEW excluded
from the success denominator but reported). **Status: pre-registration only / execution
unfinished.**

## 4. Process Indicators

- **Gate blocking times:** the offline gate blocked merges until exact counts matched;
  the reverse-proof (#32) confirmed it catches both a count drift and a lint error.
- **Correction rounds (false-green / review):** the E line closed several false-green
  escapes via D's reviews — #1 (impl-before-tests, GATE-01) → #3 spec → #8/#12 contract
  follow-ups (single-sided `MISSING_METRIC`, illegal-rubric `ValidationError`, operator
  boundaries, Option-Y threshold) → #18 v3 implementation. D↔E audit-interop gap
  (risk_gate `payload_hash` timestamp `+00:00` vs `Z`) was caught by E and fixed by D
  (#20), then re-verified byte-compatible against the real contracts.
- **Requirement changes:** FR-05 spec grew 199 → 208 → 213 → **223** cases as D's rulings
  were incorporated (single-sided missing, operators, Option-Y), with the counts, trace
  and hash records updated each round.
- **Approval discipline:** GATE-01 required test-before-implementation; the v2→v3 rebuild
  (`00a9695` after #12 merge `66f17b9`) restored a compliant ancestry; approved tests were
  never modified after approval.

## 5. E's Personal Reflection (~350 words)

Working role E, I learned that the hard part of an “agentic” project is not getting the
model to write code — it is making the code's claims *checkable*. My work centred on two
ideas from the course: that requirements must be executable, and that architecture is
enforced by boundaries a build can refuse to cross.

The first lesson was **test-first is a process, not a slogan**. On PR #1 I let the
implementation land before the tests; D correctly rejected it as a GATE-01 violation. The
fix wasn't a cosmetic reorder — it forced a separate spec PR, a frozen approval record
bound to a hash, and an implementation branch that provably descends from the approval
merge. From then on every change followed “test → approve → implement”, and the v3 rebuild
exists precisely to honour that lineage. I also learned to distrust a green suite: several
of my early tests were false-green (a threshold used as the metric, a single-sided missing
metric silently merged), and only D's adversarial review surfaced them. Good tests are
small, typed, and assert *behaviour*, not the presence of a key.

The second lesson was **interfaces are where trust is won or lost**. The D↔E audit gap —
risk_gate hashing timestamps as `+00:00` while the contracts canonicalise to `Z` — looked
trivial but would have made E's replay reject every legitimate risk event. Catching that
before merge, and then re-proving byte-compatibility against the real contracts, taught me
that cross-module contracts must be verified by *executing the other side's code*, not by
reading a docstring.

On CI, I came to see a gate's value in its *blocking*, not its reporting. Building the
reverse-proof PR — deliberately breaking a count and a lint rule and watching the required
checks refuse the merge — was the moment the six-gate design felt real rather than
diagrammatic. I also learned to be honest about blind spots (no AI-use status check, the
budget suite not yet wired) instead of claiming coverage I didn't have.

Finally, the human supervision the course requires changed how I work with the agent. The
agent is fast but over-eager; every commit, push and PR needed an explicit human gate, and
several times the right move was to stop and wait — for auth, for a review, for a ruling.
My contribution was less “writing code” and more curating evidence: hashes, approval
records, session transcripts, and a debt register that tells the truth about what is
still deferred. That discipline, I now believe, is the actual deliverable.
