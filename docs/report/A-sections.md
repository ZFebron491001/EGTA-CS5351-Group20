# D6 Report — A sections (DRAFT for compilation; not submitted as final)

> Scope: A = Evidence Pack / Requirements Engineering (FR-01, INV-02, NFR-10; D1 lead
> compiler). Draft only, gathered from verified repo state (main `7cc5680`; evidence spec
> **37** (pack 33 + precedence 4), time-policy **13**, risk_gate **139**, requirements
> checker **24**, registry **38** entries, **31** fixtures; A PRs #4, #9, #13, #15,
> #25, #30, #31, #39, #42, #43, #51, #57, #58 (closed superseded: #24, #27, #44); reviews
> of #42/#54/#56). Numbers are real; where an A-owned item
> is intentionally deferred it is stated explicitly, not claimed done.

This draft provides A's material for **§3 (Requirements Engineering)**, **§6
(Implementation & Integration — evidence slice)**, and **§9 (A personal reflection)**.
It is compilation material; the lead editor merges it into the root `Report.md`.

## 3. Requirements Engineering (A lead compiler, D1)

### 3.1 Stakeholders, goal decomposition and scope

The analysis user, the five developer-supervisors, an independent reviewer and the course
assessor are the primary stakeholders; upstream TradingAgents maintainers and data/model
vendors are external constraint sources. Goal decomposition followed *trustworthy advice
→ evidence, deliberation, risk control* and *affordable operation → budget, latency* and
*reviewable implementation → traceability, permissions, sessions, regression*. The
machine-readable PRD (`docs/req/prd.yaml`) records vision, problem, stakeholders,
objectives, scope, use cases, assumptions, constraints, MoSCoW prioritisation, and a
requirement index that references — never duplicates — the requirement text in
`docs/req/requirements.yaml` (the single source of truth). The schema
(`docs/req/req-schema.json`, JSON Schema 2020-12) validates every entry's required
fields, enums and threshold types; a semantic checker (`tools/check_requirements.py`)
additionally verifies ID uniqueness, reference resolvability, and that every Must has a
verification and owner.

### 3.2 The requirement registry (38 entries, all owner-confirmed)

The registry holds exactly **38** entries: FR-01…05, NFR-01…10, INV-01…07, GOV-01…09
(mapping D1–D9), GATE-01…06 (the six blocking gates) and SUB-01. Every entry is
`status: confirmed_by_owner` — A compiled the skeleton and transcribed only owner-supplied
acceptance criteria, without inventing any criteria on an owner's behalf (a shared-owner
row stays `draft_from_plan` until every co-owner confirms; no half-row is flipped). A's
own three requirements are:

| ID | Type / Priority | Fit criterion (metric · operator · threshold) |
|---|---|---|
| **FR-01** Evidence Pack | functional · Must | `evidence_field_and_citation_completeness_rate` ≥ 100 % — every analysis emits a pack with source_uri, published_at, fetched_at, content hash, and claim→evidence citations traceable to data |
| **INV-02** Point-in-time admissibility | invariant · Must | `future_items_admitted` = 0 — no evidence with `published_at > as_of`; date-only/day values on the as_of UTC date are excluded with `FUTURE_DATA` (unverifiable), never silently admitted |
| **NFR-10** Requirement hygiene | governance · Must | `unclosed_must_requirements_at_commit` = 0 — a requirement change updates rules, architecture, tests and trace within the same sprint |

### 3.3 Ambiguity resolution (conservative, recorded)

The plan's §2.2 ambiguities were resolved conservatively and consistently in the PRD and
registry rather than by verbal waiver: (i) "N meaningful requirements" → at least 5 FRs +
5 NFRs (the registry delivers 5 FRs and 10 NFRs); (ii) D1's PRD-and-registry dual mention
→ `prd.yaml` references `requirements.yaml` by ID to avoid duplicated truth; (iii) D2's
blueprint-vs-root-directory tension → one authoritative body plus a root entry link; (v)
D5 "from scratch" vs "extend baseline" → build new implementation from a pinned upstream
version, preserving provenance, never re-implementing TradingAgents to fake from-scratch.
Each choice is recorded with its trade-off in the PRD, not left implicit.

### 3.4 MoSCoW and traceability

Must: the five FRs, all NFRs except NFR-02, D1–D9, five sessions, six gates, branch
protection, comparison video. Should: NFR-02 optimisation targets, broader model-stability
experiments. Could: a web report, a second model provider. Won't (this round): live
trading, RL training, multi-tenant, Kubernetes, guaranteed returns. The registry carries a
`by_type`/`by_component`/`by_owner` index and a trace-to-tests mapping; the D1 checker
(`tools/check_requirements.py`, **24** unit tests) enforces schema + semantic invariants so
a Must with no verification, a dangling ID, or a non-zero invariant threshold fails CI.

## 6. Implementation & Integration — evidence slice (FR-01 / INV-02)

The evidence module (`src/egta/evidence/`) delivers FR-01 and INV-02 through four files:
`time_policy.py` (INV-02 point-in-time admissibility), `pack.py` (`build_pack`,
`validate_claims`, `InvalidCitation`), `hashing.py` (a canonical pack hasher), and
`__init__.py` (public API). `build_pack` performs admission, raw→`EvidenceItem` field
mapping, dedupe by `(source_uri, publication instant, content_hash)`, caller-supplied
conflict grouping, integrity checking via `sha256(excerpt) != content_hash`, provider-error
exclusion, cache-always-stale, and INV-02 time filtering via `time_policy.is_admissible`.
Classification precedence is **integrity → staleness → time → dedupe**, so a tampered cache
item is `INTEGRITY_VIOLATION` (audit-correct), a future cache item is `STALE_DATA` (still
excluded, so INV-02 `future_items_admitted == 0` holds), and a future non-cache item is
`FUTURE_DATA`. `validate_claims` fails closed on a dangling full `<run_id>-<case_local_id>`
citation via `InvalidCitation` carrying `ReasonCode.INVALID_CITATION`.

### 6.1 The module-boundary constraint and the hasher port

`pack_hash` must equal what the risk gate recomputes, or the gate rejects the pack as
`INTEGRITY_VIOLATION`. Importing `egta.risk_gate.canonical` from production
`egta.evidence` is a forbidden cross-module import (AGENTS.md §3, NFR-06). The first
attempt moved the canonical helper into `egta/contracts/` and edited `risk_gate/` and CI —
which the GATE-02 permission checker correctly rejected: role `build-a` may only write
`src/egta/evidence/`, `test/offline/evidence/`, `test/live/test_data_provider.py`,
`docs/req/`, `docs/evidence/FR-01/`, the A AI-use fragment and `tools/check_requirements.py`.
The honest fix stayed inside A's boundary: `egta/evidence/hashing.py` reproduces the risk
gate's canonical form **byte-for-byte**, injected into `build_pack(hasher=…)` (default =
the local hasher). The A→D equality is not asserted but *proven* by the spec test
`test_pack_hash_matches_risk_gate_canonical`, which imports `risk_gate.canonical` **in the
test** (tests may reference other modules) and checks equality over E-01/E-07/E-22/E-23. If
the risk gate ever changes its canonical form, that test fails and both sides must move
together. This is a real instance of an architecture test overruling a first
implementation choice.

### 6.2 Test-first evidence and precedence

The FR-01 pack spec (33 cases, `test_pack.py`, approved by D, PRs #25/#42) fixes the
observable behaviour before implementation; `TEST_DRIFT` and record binding are enforced by
the GATE-01 checker. A later security/audit precedence question — whether a tampered cache
item should be INTEGRITY or STALE — was split into a **separate** test-first spec PR #44
(superseded by #51 after a force-push locked #44) with its own approval record
(`actual_cases: 4`), so implementation and the new tests never land in one commit. Frozen
`test_pack.py` hash is unchanged (`75fc9d…`).

### 6.3 Verification evidence (real, on main)

- evidence spec: **37 passed** (33 pack + 4 precedence); time-policy: **13 passed**.
- risk_gate consume: **139 passed** (A→D canonical equality intact).
- requirements checker: **24 passed**; registry: **38** entries, all confirmed.
- live data-provider test (`test/live/test_data_provider.py`): **4 skipped** offline,
  **4 passed** with `EGTA_LIVE_DATA=1` against real Yahoo Finance data (bar date not
  future, `sha256(excerpt)==content_hash`, INV-02 admissible, `build_pack` well-formed).
- `tools/check_permissions.py --role build-a` → OK on every A PR.

### 6.4 Limitations (honest)

The evidence module validates data *admissibility* and *integrity*; it does not judge
whether a claim is financially *correct*. Pre-training knowledge of future events cannot be
removed by date filtering, so historical backtests are exploratory, not free of
look-ahead. The live test is skipped by default (offline CI must stay network-free, NFR-08);
its green live run is environment-specific, not a CI gate.

## 9. Reflection — A (61016736 Du Yuxiang)

*(300–500 words; for §9 of the final Report.)*

My work centred on three things: the D1 requirements engineering, the FR-01 evidence pack,
and the discipline of the human-in-the-loop gates. Compiling the 38-entry registry taught
me that "machine-readable" is not the same as "good requirement": YAML that parses can
still hide a dangling ID or a Must without a verification, which is why the semantic checker
matters as much as the schema. I learned to transcribe owners' criteria exactly and to leave
a shared-owner row as draft rather than invent an acceptance criterion on someone else's
behalf — a small habit that prevented several false "confirmed" states.

The most instructive episode was the FR-01 implementation. My first attempt satisfied D's
"no cross-module import" request by moving the canonical hash helper into `contracts/` and
editing `risk_gate/` and CI. It passed the tests I was watching — and then the permission
gate blocked it: as role A I was never allowed to touch those files. The lesson was that a
checker I had dismissed as "bureaucracy" was the thing keeping the module boundary honest.
The redesign — a byte-identical local hasher injected through a port, with equality proven
only in a test — was smaller, stayed in scope, and was truer to the architecture. I would
not have found it by "fixing the surface"; I found it by reading why the gate failed.

The other recurring theme was that I was frequently an approver, not the author. I reviewed
#42, #54 and #56, and I twice chose to unblock the pipeline by merging or verifying
*other people's* work only after an independent approval existed — never self-approving,
and never minting an approval I could not justify. Several rounds of rework came from my
own tendency to patch the reported symptom; the turnaround only came when I audited the
whole PR (dangling references, INV-02 reconciliation, permission scope) instead of the
three lines D had listed. If I did this again, I would run `check_permissions` and the
gate's real script locally *before* opening a PR every time.

Finally, the budget/risk/evidence interfaces were where I learned the most about
integration: FR-01 is only useful if the risk gate can consume its hash unchanged, and the
`A→D` equality test — a plain assertion that the two modules agree byte-for-byte — became
the clearest proof that "the modules integrate" rather than "each passes its own tests".
