# Memory and Context Design (D2)

- **Status:** DRAFT — PENDING HUMAN REVIEW. B-authored synthesis; the C-owned
  layered/compression/re-injection design is **not yet merged** and is marked as such.
- **Owner of this document:** B (D2 architecture pack)
- **Requirement owners cited:** C (FR-03, INV-05, NFR-03), E (FR-05, NFR-09), D (NFR-09).
- **Related:** `architecture-blueprint.md` §2/§5, `runtime-policy-catalog.md`,
  `trace-matrix.md`, `risk-list.md`, ADR-003.

> This document records the **existing** upstream memory/reflection paths plus the
> evidence/audit/context boundaries EGTA already has, and it records the **C-owned**
> layered/compression/re-injection design as a dependency with open confirmation
> points. It does **not** invent or freeze C's design. Where a decision belongs to C,
> it is marked "source: C — PENDING" and tracked in `risk-list.md`.

## 1. Upstream memory and reflection (as it exists today)

The upstream baseline (`tradingagents/`, SHA `9fa1196`, v0.7.1) ships a memory
subpackage that EGTA has **not** replaced:

| Path | Responsibility (observed) | Relevant requirement |
|---|---|---|
| `tradingagents/memory/log.py` | Append-only decision log entries for past runs | FR-03 (reflection input), FR-05 (replay context) |
| `tradingagents/memory/reflection.py` | `Reflector` turns a settled decision's outcome into a 2–4 sentence lesson, explicitly **compact enough to be re-injected into future agent prompts without bloating the context window** | FR-03, NFR-03 (quality), context budget |
| `tradingagents/memory/settlement.py` | Settles past decisions after the holding window; computes alpha vs a benchmark and records a reflection | FR-03, FR-05 |
| `tradingagents/memory/__init__.py` | Package surface | — |

The upstream `Reflector` prompt already states the compaction intent (a lesson is
"compact enough to be re-injected into future agent prompts without bloating the
context window"). That sentence is the closest existing anchor to the C-owned
layering/compression idea, but upstream does not implement a layered store, a
summarizer, or a re-injection budget — those remain **C's design**.

## 2. Evidence, audit and context boundaries EGTA already has

EGTA adds deterministic boundaries the upstream memory path must respect:

- **Evidence pack (A, merged — FR-01/INV-02).** Every analysis output carries an
  immutable `EvidencePack` (source, publication time, fetch time, content hash, claim
  refs). Memory/reflection text is **not** evidence: it cannot substitute for a pack,
  and it cannot carry a `published_at` after `as_of`. The time filter
  (`src/egta/evidence/time_policy.py`) is the single implementation of INV-02.
- **Audit event stream (E, merged — FR-05/NFR-09).** `RunEvent` (append-only,
  hash-chained) is the replayable record. Reflections and memory reads/writes are
  observable through the run phases; the evaluation module replays events and must not
  require the LLM to reconstruct state (see `src/egta/evaluation/replay.py`).
- **Risk authority boundary (D, ADR-003 — FR-04/INV-01).** Memory text is untrusted
  input. A reflection or recalled "lesson" cannot grant a rule exemption, raise a
  limit, choose a policy version, or authorize a ledger write. The deterministic
  `RiskGate` re-checks every proposal from scratch.
- **Secret boundary (INV-07).** Memory entries and reflections must not persist secrets;
  they pass the same secret-scan discipline as prompts and exports.

## 3. The C-owned layered / compression / re-injection design (source: C — PENDING)

The blueprint's deliberation + data flow assume C's context assembly exists. The
following is **C's design space**, recorded here so the architecture pack names the
dependency without pre-empting it. None of it is merged; each item lists its source
and an open confirmation point.

| Aspect | Proposed direction (C — PENDING) | Source | Open confirmation point |
|---|---|---|---|
| Layered memory | Separate short-term (current run), episodic (recent settled decisions), semantic (distilled lessons) layers | C / FR-03 | Layer boundaries, TTL, and what each layer may feed into prompts — owner C |
| Compression | Summarize older episodes into the semantic layer to bound token growth | C / NFR-02 (token median −25%) | Summarizer identity, determinism, and whether compression is LLM-backed (then it is a budgeted external call, INV-03) |
| Re-injection | Inject a bounded, ranked selection of lessons into the next run's prompt, under a token budget | C / NFR-02, FR-03 | Ranking rule, token budget, and interaction with the budget governor's `max_total_tokens` — owner C + B |
| Untrusted-text isolation | External text cannot change rules/permissions (INV-05) | C + permission gateway | Where the isolation gate sits relative to the memory store — owner C/D |

**Architectural constraints this design must satisfy (already decided):**

1. Any LLM-backed compression or summarization is an **external model call** and must
   pass through the budget governor (INV-03) — it is not exempt because it is "memory".
2. Re-injection must respect the run's `max_total_tokens` (NFR-01); the budget governor
   is the admission authority, not the memory layer.
3. Memory text is untrusted LLM-authored input; it cannot authorize risk/ledger actions
   (ADR-003) or change tool permissions (INV-05).
4. Replay (E) must reconstruct a run without depending on re-running the reflection LLM;
   reflections are recorded, not recomputed during replay.

## 4. ADR-002 status

There is **no ADR-002** in the repository today (`docs/architecture/adr/` contains only
`001-modular-extension.md` and `003-risk-authority.md`). The layering/compression
decision, when C freezes it, should become **ADR-002** with C as owner. Until then,
this section records the intent and this file is the link point; it is **not** an
approved memory architecture.

## 5. Gaps and owner actions

- **C:** publish the layered/compression/re-injection design (target ADR-002) and the
  FR-03 deliberation spec; confirm how re-injection shares the token budget.
- **B:** wire the budget governor so any summarizer call is reserved first (INV-03);
  align `RunSpec.limits` with governor limits in `app`.
- **E:** ensure replay treats reflections as recorded inputs, not recomputed output
  (NFR-09 / FR-05 replay).
- **D:** confirm the INV-05 isolation gate placement relative to the memory store.
