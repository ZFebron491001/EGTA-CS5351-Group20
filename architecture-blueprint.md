# Architecture Blueprint (entry)

The single D2 blueprint body lives at:

- **[`docs/architecture/architecture-blueprint.md`](docs/architecture/architecture-blueprint.md)**

This root file is the entry link required by `execution_plan_261111.md` §8.1
(the body is under `docs/architecture/`; this file only points to it — do not
maintain a second full copy here). The link target was verified with a **local
link check**; it is not yet covered by a CI job.

## D2 artefact set (GOV-02)

GOV-02 names **eleven** D2 artefacts. The table maps each named item to the actual
file (or section) that satisfies it, and states whether **this PR** adds it, it was
**already on main**, or it remains a **gap**.

| # | GOV-02 item | Actual file / section | Origin |
|---|---|---|---|
| 1 | Blueprint | `docs/architecture/architecture-blueprint.md` (body); root `architecture-blueprint.md` (entry) | **this PR** (body updated; entry extended) |
| 2 | ADR | `docs/architecture/adr/001-modular-extension.md` (ADR-001); `docs/architecture/adr/003-risk-authority.md` (ADR-003) | ADR-001 **this PR** (updated) / ADR-003 **on main** |
| 3 | Invariants | `docs/architecture/invariants.md` | **on main** (D-owned; other owners append) |
| 4 | Trace matrix | `docs/architecture/trace-matrix.md` | **this PR** (new) |
| 5 | Memory | `docs/architecture/memory-design.md` | **this PR** (new; C design PENDING) |
| 6 | Permission | `docs/architecture/permission-model.md` | **on main** (D-owned) |
| 7 | Runtime policy | `docs/architecture/runtime-policy-catalog.md` (catalog) over `risk-policy.md` | **this PR** (new catalog) / `risk-policy.md` **on main** |
| 8 | Candidate evaluation | `docs/architecture/evaluation-table.md` | **this PR** (new) |
| 9 | Evaluation logbook | `docs/architecture/evaluation-logbook.md` | **this PR** (new) |
| 10 | Risk list | `docs/architecture/risk-list.md` | **this PR** (new) |
| 11 | Option ledger | `docs/architecture/option-ledger.md` | **this PR** (new) |

Remaining gaps (see `docs/architecture/trace-matrix.md` §3): the memory layering /
compression design (item 5) is C-owned and **not yet decided** (no ADR-002); the
runtime policy catalog (item 7) indexes thresholds that `risk-policy.md` still marks
PENDING; trace-matrix rows for FR-03/INV-05 (C) and end-to-end budget gateway (B) are
gaps, not green.

Supporting artefacts referenced but not part of the 11: `threat-model.md`,
`docs/req/evidence-contracts.md`, `docs/debt-register.md`.
