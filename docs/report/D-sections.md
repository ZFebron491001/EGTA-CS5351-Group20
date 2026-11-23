# D6 Report — D sections (DRAFT for compilation; not submitted as final)

> Scope: D = FR-04 deterministic risk gate + paper ledger, NFR-05, INV-01/04/06/07,
> D3 governance/permissions, D4 verification, D5 evidence. Draft from verified repo
> state (main `e797138`; risk_gate **139**, governance **38**, 10 required checks;
> D5 main/appendix transcripts and the D log on main). Numbers are real. Where a
> deliverable is deferred, it is stated as deferred, not claimed complete.

## 4. Architecture — a deterministic risk authority inside a modular monolith

### 4.1 The authority problem

TradingAgents produces free-text analysis and a rating through an LLM graph. A rating is
advice, not an execution authorization. Upstream also has risk-debate agents, but a debate
is still natural-language advice: it can be persuaded by a prompt, and it cannot provide a
transactional boundary around a paper ledger. The architecture therefore separates two
layers that are easy to conflate: the **runtime analysis/advice agent** and the
**deterministic risk authority**. The first may propose; only the second may authorize a
ledger mutation. This is the central quality-attribute decision for D's work (ADR-003):
security and auditability outrank availability and fluency. If the evidence, policy,
budget or audit sink is unavailable, the gate fails closed rather than inventing a
successful trade.

The boundary is also a module boundary. `src/egta/risk_gate/` owns the rules, policy,
ledger and verdict service; it has no LLM client, no broker, no network client and no
file-write path outside its SQLite database. Other modules may consume `RiskVerdict`, but
they cannot write the ledger directly. The Runtime RiskGate has zero MCP tools. A model
cannot "explain away" a rule, and a prompt cannot change a policy threshold or the
concentration cap.

### 4.2 Deterministic rules, policy and fail-closed behaviour

The gate accepts only `BUY`, `SELL` and `HOLD`; `HOLD` is a valid no-trade suggestion only
when it carries a valid evidence pack, otherwise it becomes `REVIEW/EVIDENCE_MISSING`.
The policy is paper-only and long-only: cash may not go negative, positions may not go
short, quantities are integer shares, and execution uses explicit fee and slippage
parameters. The plan-specified 20% BUY concentration cap and 10% BUY/SELL notional cap are
implemented as rules, but they are not promoted to approved product defaults. Freshness,
fee, slippage, base currency, quantization and policy version remain explicitly PENDING;
an unconfigured or incompatible policy is rejected as `BLOCKED/INCOMPATIBLE_STATE`. This
is deliberate: a missing product decision must not silently become a permissive default.

The invariant register is the second half of the design. **INV-01** says an unapproved
proposal must not change the ledger. **INV-04** says the same proposal produces one ledger
change. **INV-06** says the ledger and its audit record commit atomically. **INV-07** keeps
secrets out of prompts, reports, commits and session exports. **INV-02** (owned by A)
keeps future-dated evidence out of the pack. The gate is the enforcement point for
INV-01/04/06; the permission model and secret scanning support INV-07; the evidence module
supports INV-02. None of these are policy suggestions: a failure returns a structured
verdict and leaves the ledger unchanged.

### 4.3 One transaction, one proposal, one audit event

The ledger is SQLite. `evaluate_and_commit` opens a `BEGIN IMMEDIATE` transaction, re-reads
the portfolio version inside the transaction, checks the proposal hash and expiry, applies
the deterministic rules, and writes the verdict, ledger entry, portfolio update and outbox
event in the same transaction. A stale caller snapshot whose proposal version matches the
database is `REJECTED/STALE_PORTFOLIO`; a proposal that loses a concurrent portfolio-version
race is rejected with the distinct stale-portfolio status and produces no ledger write.
The proposal hash is the idempotency key: a duplicate proposal returns the already
committed result rather than charging twice. `UNIQUE(proposal_hash)` is intentionally a
single column because the hash covers the run id and the formal proposal content; it is at
least as strict as `(run_id, proposal_hash)`.

Audit is not a side effect that can fail later. The outbox event is written inside the same
transaction; if the audit or ledger write fails, the whole transaction rolls back and the
run is `BLOCKED/AUDIT_UNAVAILABLE`. Exactly one outbox event is emitted per stored verdict
at `Phase.RISK_GATE`. The audit consumer deduplicates by event id and verifies the payload
hash chain. This is the practical meaning of "no silent paper trade". The transaction
design is tested with duplicate requests, restart, crash and disk/write failure cases, not
only with happy-path unit tests.

### 4.4 Canonicalisation and the A→D interface

Risk identities are content-bound. The canonical form is sorted compact JSON, UTF-8,
Decimal as a fixed-point string, aware datetimes normalised to UTC, tuples as arrays, and
SHA-256 lowercase hex. The outbox payload hash is kept byte-compatible with
`contracts.audit`: Pydantic JSON renders UTC as `...Z`, so the risk gate stores and hashes
the same `Z` timestamp. E's review found the original `+00:00` form and showed that
`verify_payload`/replay would reject a legitimate risk event; the fix (`6bad169`) made the
stored and recomputed payload hashes identical and was re-verified against the contracts
on main.

A second cross-module issue appeared in A's FR-01 integration: E-07 keeps a date-only
`published_at`, and the canonicaliser initially raised `TypeError` for `datetime.date`.
The date-only regression (`276a020`) was RED, the minimal fix (`95d6bb9`, PR #38) added a
`date` branch **after** the `datetime` branch and rendered `YYYY-MM-DD`, and the full
risk-gate suite stayed at 139. A's implementation and the gate now agree on the hash for
date-only packs; the equality is proven by a real test that imports the risk helper, while
production `egta.evidence` does not import `egta.risk_gate`.

### 4.5 Paper policy is a demo policy, not an investment recommendation

The policy artefact states its own status: `PROPOSED — PENDING HUMAN APPROVAL`, product
version `DRAFT-NOT-FROZEN`. The 20%/10% caps are plan-specified rules, not approved
financial advice. Test fixtures use `price_freshness_seconds=240`, `fee_bps=10` and
`slippage_bps=0` only to make cases deterministic; those values are not product defaults.
The correct behaviour when the product values are not configured is to reject safely. The
gate is therefore complete as a deterministic mechanism, while the business policy remains
a documented, open debt (`DEBT-FR04-POLICY-APPROVAL`) rather than a hidden assumption.

## 5. Coding-agent governance — D3 permissions and the gates that make it real

### 5.1 AGENTS.md, Prompt.md and human-only rules

D3 is the governance layer around the coding agent, not a runtime financial component.
`AGENTS.md` is the read-order entry point; it states the module boundaries, the human
gates, the verification rules and the project covenant. The file deliberately says that
the repository has no `.opencode/` runtime enforcement at inspection time and that
`Prompt.md` is a separate C-owned artefact. The human-maintained `.opencode/rules.md`
(#53) records the role allowlist, human-only paths, Git/remote restrictions, credential
prohibitions, the approval-record exception and the evidence rules. It is marked
human-maintained; the agent did not write it. The permission model and MCP manifest are
policy artefacts and checker specifications, not proof of executor enforcement.

This distinction matters. A Markdown rule that says "do not push" is not enforcement; the
evidence is a tool refusing the action, or a CI job failing the PR. The project therefore
uses two layers: a written policy for human review, and independent checkers that read Git
history and hashes. The policy explains *why*; the checker produces *evidence*. D3 is
honest about the current state: the human rules exist, but runtime OpenCode enforcement is
not claimed until a real refusal is recorded.

### 5.2 Permission model and the two governance checkers

`tools/check_permissions.py` classifies a `base..head` diff by role. D's role may write the
risk gate, its approved tests, synthetic security fixtures, D governance docs and D
evidence; other modules, contracts, CI, CODEOWNERS, approval records, credentials and the
human-only `.opencode/rules.md` are protected. The checker also detects cross-module
private imports and credential-path references, and supports `--json` with stable reason
codes. The role model is not a suggestion: a `build-d` edit to the budget module returns
`PATH_NOT_ALLOWED`; a `.opencode/rules.md` edit returns `HUMAN_ONLY`.

`tools/check_approval.py` verifies the test-first chain from the approval record: required
fields, approver versus author, requirement registry membership, the approved test
content commit, per-file and aggregate hashes, reviewed-head ancestry, and test drift in
the implementation. A record that is missing a reviewed head, still PENDING, self-approved,
or bound to the wrong hash fails closed with a stable code. The checker does not trust PR
prose. This is the operational meaning of GATE-01: the implementation PR must descend from
an independently approved test baseline, and a post-approval test edit voids the approval.

### 5.3 From local checker to blocking CI

The checkers were merged in #29; E3 wired them into CI in #40/#47. The final `protect-main`
ruleset has **10 required checks**: the four Python-version test jobs (including a
non-UTC timezone), clean-install smoke, strict ruff, the per-suite offline gate,
`governance (exact 38)`, `check-permissions (GATE-02)` and `check-approval (GATE-01)`.
The offline gate reads the expected counts from approval records; a drift or a skip fails.
The governance job runs the 38 checker tests at an exact count. Check-approval uses the PR
base for implementation PRs, treats the test/spec PR as the approval event, and fails
closed when an applicable module has no record; PR #50 fixed a false `TEST_DRIFT` caused
by using an old record commit as the base.

The gate was tested in both directions. Failure control #48 deliberately added a contracts
path, a risk-gate test edit and an extra governance test; governance, check-permissions and
check-approval all failed and the PR was BLOCKED. Normal control #49 changed only an
allowed `src/egta/risk_gate/` file; all 10 required checks passed and only the review
requirement blocked it. Both throwaway PRs were closed without merge. This is stronger
evidence than a diagram: the required checks actually refuse the merge.

The honest limits are also recorded. CI-only changes and some tools/contracts paths remain
code-owner-reviewed rather than fully automated; an approval-record edit is a
human-authorized exception that must not be inferred from green CI; GATE-03/04/06 are not
fully automated status checks. The policy artefacts say this explicitly.

## 6. Implementation — the risk-gate slice

### 6.1 Modules and the deterministic path

`src/egta/risk_gate/` contains seven files: `models.py`, `policy.py`, `rules.py`,
`ledger.py`, `service.py`, `canonical.py` and `__init__.py` (1329 lines). `service.py`
orchestrates the transaction; `rules.py` is pure deterministic checks; `ledger.py` owns
SQLite and the outbox; `canonical.py` owns identity hashing; `policy.py` parses and
validates the policy; `models.py` defines the local contract types used by the tests.
Money is `Decimal` throughout; there is no float in the money path. The gate imports only
its own module and `egta.contracts`; it has no LLM, broker or network import.

The test baseline is 126 risk cases (119 behavioural + 7 static inspection), 11 manifest
meta-tests and 2 harness self-tests: **139** tests in total. The cases are split into
actions/quantities, funds/positions/costs, evidence/time/policy, identity/idempotency,
atomicity/concurrency and security boundaries. The red baseline was captured before
implementation; the harness self-check uses a satisfying stub and a violating stub to
prove the comparison harness itself is not vacuous. The approved test hash is bound in
`docs/approvals/test-hash-FR-04-risk-gate.txt`; the implementation PR did not modify the
frozen tests.

### 6.2 Date-only canonical fix and the test-first trail

The date-only work is a small but representative example of the project's process. A's
E-07 test exposed a `TypeError` in `recompute_evidence_hash`; the RED regression was
committed first (`276a020`), then the fix (`95d6bb9`) added a `date` branch after
`datetime`. The existing EVD-05 case gained a date-only assertion; the total risk-gate
count stayed 139. A independently recomputed the new per-file hash and aggregate, and the
record was re-signed (`eae1f93c…`, aggregate `f3c45de2…`); D did not self-sign the
approval. The `check_approval` tool verifies the record against the test commit and the
implementation head. The fix is small; the evidence chain around it is the point.

### 6.3 D5 evidence and operational traceability

D's work is also visible in the session record. The main FR-04 design session and its
post-archive continuation are exported as sanitized raw JSON and readable Markdown:
483 and 361 messages respectively, with a curated intervention index and a secret-pattern
scan of 0 hits. The raw export retains reasoning; the Markdown renders text, tool calls,
outputs and patches. The `transcripts/INDEX.md` D row is COMPLETE. This is not a summary of
what the agent wishes had happened; it is the actual tool trace, including the failed
tests, review corrections and human approval points.

## 7. Verification — what was actually measured

The D-side verification on the final main line is:

| Check | Result |
|---|---|
| `pytest test/offline/risk_gate -q` | **139 passed** (126 cases + 11 manifest + 2 harness) |
| `pytest test/offline/governance -q` | **38 passed** (32 behavioural + 6 manifest) |
| Required checks on `protect-main` | **10** (tests, smoke, ruff, offline, governance, check-permissions, check-approval) |
| #48 failure control | governance / check-permissions / check-approval failed; PR **BLOCKED** |
| #49 normal control | all 10 required checks passed; closed without merge |
| Coverage | **92%** total; `policy.py` 80% (100% security-branch coverage **not** claimed) |
| D4 verification | `DEBT-FR05-D4` closed via #18 (`10ee52d`), contracts 223 / E2 28 green; winner/composite remains separate debt |

The coverage limitation is deliberate and recorded. The uncovered `policy.py` branches are
defensive invalid-field combinations not represented in the approved 139-case baseline;
adding tests for them would change the approved baseline and requires a new approval. It is
recorded as follow-up debt instead of silently editing the frozen tests.

## 8. Maintenance, debt and limitations

The risk gate is complete as a mechanism, not as a production trading system. The
following limitations are carried into the submission evidence rather than hidden:

- **ADR-003 and risk policy are PROPOSED, not APPROVED.** Human approval of the versioned
  demo policy is deferred in `DEBT-FR04-POLICY-APPROVAL`. Freshness, fee, slippage, base
  currency, quantization, version/hash and effective window are not frozen. The gate
  rejects absent/incompatible policy; fixture values are not defaults.
- **Instrument identity is still a fixture gap.** `AdvisoryProposal` has no approved ticker
  field; tests use a test-only ticker. C/B must freeze the shared identity or the
  run_id→RunSpec.ticker rule before production integration.
- **Shared contracts are provisional.** The risk gate uses a local ReasonCode adapter for
  the frozen 13-value vocabulary and does not edit contracts. Final integration may import
  the shared enum; that is a contracts-owner decision.
- **Runtime permissions are policy, not proven enforcement.** `.opencode/rules.md`,
  `AGENTS.md` and the checkers are real artefacts; OpenCode runtime loading of a
  permissions file is not claimed. The CI checkers are the enforcement evidence.
- **CI gate scope is explicit.** CI-only changes and some tools/contracts paths remain
  human/code-owner-reviewed; GATE-03/04/06 are not all automated status checks. An
  approval-record edit is a human-authorized exception, not a green-CI inference.
- **External integration gaps remain.** FR-02 budget implementation/record activation, C's
  `Prompt.md`/FR-03 deliberation, and E's final total AI-use log assembly are outside D's
  module ownership; D does not claim them as complete.
- **D4/winner-composite.** The false-green debt is closed; the `winner/composite` scoring
  remains a separate open debt, so the report does not claim an "enhanced win".

These are not footnotes to be removed at submission. They define the boundary of what the
evidence supports.

## 9. Personal reflection — D (61017180 Zhang Fan)

*(300–500 words; for §9 of the final Report.)*

My work as D was to make the boundary between advice and execution real. The most important
lesson was that a deterministic gate is not a single function; it is a chain of evidence,
policy, transaction and permission decisions that must fail closed together. It is easy to
write a rule that rejects a negative quantity. It is much harder to guarantee that the
ledger and its audit event commit atomically, that a duplicate proposal cannot charge
twice, and that a stale portfolio version cannot authorize a trade. The 139-case baseline
forced me to confront those cases before writing the implementation; the failures were
useful, not embarrassing.

The second lesson was that cross-module compatibility is proven by executing the other
side, not by reading its docstring. E's audit review found that my outbox hash used
`+00:00` while the contracts canonicalised to `Z`; the event looked valid to my tests but
would have been rejected by replay. A's E-07 date-only pack exposed a second gap. Both
fixes were small, but both required a shared test and an honest update of the approval
record. The temptation to patch the test or the hash record was real; the human gates and
the independent reviewers are what stopped it. I now treat a hash record as a contract,
not paperwork.

The third lesson was about permissions. I initially thought of the permission checker as a
CI formality. When A's first evidence implementation crossed into `risk_gate` and
`contracts`, the checker caught it before I did. That changed how I design: the module
boundary and the role allowlist are part of the architecture, not an afterthought. The
same is true of the human-only rules; `.opencode/rules.md` is maintained by a human, and
the agent's job is to produce evidence, not to claim enforcement.

The reverse-proof exercise made the gates tangible. Deliberately breaking a governance
count, a path rule and a test hash, then watching the required checks refuse the merge,
was more convincing than any diagram. The normal control proved the gate is not simply red
for everything. I also learned to be precise about what is not done: ADR-003 is still
PROPOSED, product policy is deferred, the ticker identity is a fixture gap, and the budget
and Prompt/deliberation work belong to other owners. A good report is not one that hides
those gaps; it is one that makes them verifiable.

Finally, the human-in-the-loop process changed my working style. I stopped treating a
green local suite as completion and started asking which independent reviewer had signed
which exact commit, which required check had actually blocked a merge, and which evidence
would still be reproducible after the session ended. That habit — evidence before claims —
is the part of this project I will carry forward.

## Appendix D — evidence index

| Deliverable | Evidence |
|---|---|
| FR-04 tests | `test/offline/risk_gate/`; approval `docs/approvals/test-hash-FR-04-risk-gate.txt`; PR #17 merge `b245bdb`, #19 `0ab1c82` |
| FR-04 implementation | `src/egta/risk_gate/`; PR #20 merge `31d01cc`; evidence `docs/evidence/FR-04/impl-green.txt` |
| Date-only canonical | PR #38 merge `81f25f5`; evidence `docs/evidence/FR-04/date-only-canonical-fix.txt` |
| Governance checkers | `tools/check_permissions.py`, `tools/check_approval.py`; PR #29 merge `d375b7a` |
| D3 rules/AGENTS | `AGENTS.md`, `docs/architecture/permission-model.md`, `.opencode/rules.md` (#53) |
| Required checks/reverse proof | `docs/evidence/FR-04/gate-reverse-proof.txt`; #48/#49/#50 |
| D4 verification | `docs/debt-register.md`; #23 merge `df3d64e`; #18 merge `10ee52d` |
| ADR/policy | `docs/architecture/adr/003-risk-authority.md`, `docs/architecture/risk-policy.md`; #52; `DEBT-FR04-POLICY-APPROVAL` |
| D5 | `transcripts/61017180-Zhang-Fan.md`, `transcripts/appendix/61017180-Zhang-Fan-session2.md`, annotations; #60 merge `4677a11` |
| D closeout | #54 merge `e797138`; D fragment 11 sessions; `transcripts/INDEX.md` D row COMPLETE |
