# G3 readiness — E side (gap sheet)

Snapshot: `main` `4d4b98d` (2026-11-22; re-synced).
Status reflects live `gh api` + `git ls-tree` at this time. Owners use the A–E map.

## Gap table

| Artifact | Owner | Status | Blocker |
|---|---|---|---|
| **D1** requirement registry (`docs/req/prd.yaml`, `requirements.yaml`, `req-schema.json`) + `tools/check_requirements.py` | A | **PARTIAL** | `requirements.yaml` **merged** (#9); `prd.yaml`/`req-schema.json` **merged** (#15, already in `main`); `check_requirements.py` (#30 spec/#31 impl) still **open** |
| **D2** architecture blueprint (`docs/architecture/architecture-blueprint.md`) | B | **MISSING** | not delivered (no PR yet) |
| **D3** AGENTS/permissions/human-only/.opencode/.agent | D (+E wire) | **PARTIAL** | #29 **merged** (AGENTS.md + `tools/check_permissions.py`/`check_approval.py` + permission-model present); `.opencode/`, `.agent/`, `.opencode/rules.md`, `.opencode/permissions.jsonc` still absent |
| **D4** review-memo / debt-register / bug-diary / verification-constraints | E (+all) | **PARTIAL** | `debt-register.md` present; `docs/review-memo.md`, `docs/bug-diary.md`, `docs/code-governance/verification-constraints.md` missing |
| **D5** five main sessions + annotations | A/B/C/D/E | **PARTIAL** | **#28 merged (`b0333cb`) → `transcripts/` on main**; E raw+full md+annotations present (accepted by A/D); A/B/C/D sessions still PENDING |
| **D6** `Report.md` | E assembly | **MISSING** | reserved for the separate report day |
| **D7** CI / 门禁 / branch protection / CODEOWNERS | E | **DONE** | 7 required checks active (#11); reverse-proof #32/#33 evidence |
| **D8** `src/` + `test/` per module | A–E | **PARTIAL** | contracts/E2/risk_gate/evidence present; **budget** missing (#22 spec-only); deliberation C not present |
| **D9** root static `Prompt.md` | C | **MISSING** | not delivered |
| AI-use logs → final commit | A/B/C/D/E | **PARTIAL** | E finalized (#28); B/D fragments present (`ai-use-log-*-fragment.yaml`); **C: none** |
| **Six gates** wired into CI | E (+D) | **PARTIAL** | `offline-tests` active; `tools/check_permissions.py`/`check_approval.py` **now available** (#29 merged) → wire as `check-permissions`/`check-approval` jobs in follow-up E3; schema/ai-log/semantic still follow-up |
| Labels + ZIP export (no secrets) | E (D verifies) | **NOT STARTED** | later (freeze step) |
| CODEOWNERS enforcement (`require_code_owner_review`) | D (Admin) | **OPEN** | ruleset currently has code-owner review off; D decides |

## E can close now vs blocked on others
- **E can close now:** E4 verification evidence (#34), offline gate + reverse-proof
  (#32/#33), E's D5 part (#28), debt-register + E AI-use entries, `tools/e2e_g1.py`.
- **Blocked on A:** `check_requirements.py` (#30 spec/#31 impl) → unblocks the **schema gate**. (`requirements.yaml` merged via #9; `prd.yaml`/`req-schema.json` merged via #15 — both already in `main`, so `check_approval --registry` has its file and the schema files exist.)
- **Blocked on B:** D2 blueprint; FR-02 budget implementation (#22 spec) → budget
  suite goes live; FR-01 pack (#25).
- **Blocked on C:** D9 `Prompt.md`; D5 C session; semantic runner for GATE-04.
- **Done by D:** #29 checkers **merged**. **Blocked on D still:** wire `check-permissions`/`check-approval` into CI (follow-up E3, E-led); create D3 `.opencode`/`.agent` policy files; code-owner-review toggle.
- **Blocked on all:** five main sessions; final AI-use to the freeze commit;
  `Report.md`; labels + ZIP.
