# G3 readiness — E side (gap sheet)

Snapshot: `main` `6830926c44e7a16bae0cac1992f43a6aac8b26f6`, 2026-11-22T11:40Z.
Status reflects live `gh api` + `git ls-tree` at this time. Owners use the A–E map.

## Gap table

| Artifact | Owner | Status | Blocker |
|---|---|---|---|
| **D1** requirement registry (`docs/req/prd.yaml`, `requirements.yaml`, `req-schema.json`) + `tools/check_requirements.py` | A | **MISSING** | open PRs #9 (registry), #15 (prd+schema), #30 (checker spec), #31 (checker impl) — none merged; `requirements.yaml` absent on main |
| **D2** architecture blueprint (`docs/architecture/architecture-blueprint.md`) | B | **MISSING** | not delivered (no PR yet) |
| **D3** AGENTS/permissions/human-only/.opencode/.agent | D (+E wire) | **PARTIAL** | #29 (AGENTS.md + `tools/check_permissions.py`/`check_approval.py` + permission-model) **open**, not merged; `.opencode/`, `.agent/`, `.opencode/rules.md`, `.opencode/permissions.jsonc` absent |
| **D4** review-memo / debt-register / bug-diary / verification-constraints | E (+all) | **PARTIAL** | `debt-register.md` present; `docs/review-memo.md`, `docs/bug-diary.md`, `docs/code-governance/verification-constraints.md` missing |
| **D5** five main sessions + annotations | A/B/C/D/E | **PARTIAL** | E via #28 (raw+full md+annotations, E=PENDING acceptance); A/B/C/D sessions PENDING; `transcripts/` not on main |
| **D6** `Report.md` | E assembly | **MISSING** | reserved for the separate report day |
| **D7** CI / 门禁 / branch protection / CODEOWNERS | E | **DONE** | 7 required checks active (#11); reverse-proof #32/#33 evidence |
| **D8** `src/` + `test/` per module | A–E | **PARTIAL** | contracts/E2/risk_gate/evidence present; **budget** missing (#22 spec-only); deliberation C not present |
| **D9** root static `Prompt.md` | C | **MISSING** | not delivered |
| AI-use logs → final commit | A/B/C/D/E | **PARTIAL** | E finalized (#28); B/D fragments present (`ai-use-log-*-fragment.yaml`); **C: none** |
| **Six gates** wired into CI | E (+D) | **PARTIAL** | only `offline-tests` gate active; permission/approval (needs #29), schema (needs A D1), ai-log (review-time), semantic (needs C runner) are **follow-up E3** |
| Labels + ZIP export (no secrets) | E (D verifies) | **NOT STARTED** | later (freeze step) |
| CODEOWNERS enforcement (`require_code_owner_review`) | D (Admin) | **OPEN** | ruleset currently has code-owner review off; D decides |

## E can close now vs blocked on others
- **E can close now:** E4 verification evidence (#34), offline gate + reverse-proof
  (#32/#33), E's D5 part (#28), debt-register + E AI-use entries, `tools/e2e_g1.py`.
- **Blocked on A:** D1 registry + `check_requirements.py` (#9/#15/#30/#31) → also
  unblocks the **schema/gate** and `check_approval`'s `--registry`.
- **Blocked on B:** D2 blueprint; FR-02 budget implementation (#22 spec) → budget
  suite goes live; FR-01 pack (#25).
- **Blocked on C:** D9 `Prompt.md`; D5 C session; semantic runner for GATE-04.
- **Blocked on D:** #29 checkers merge → wire GATE-01/02; D3 `.opencode`/`.agent`
  policy files; code-owner-review toggle.
- **Blocked on all:** five main sessions; final AI-use to the freeze commit;
  `Report.md`; labels + ZIP.
