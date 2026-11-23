# Review Memo

Purpose: a durable record of independent review decisions and evidence for PRs relevant to
D's work package (FR-04, D3, D4 verification). It is not a substitute for the GitHub review
or the protected approval records.

Decision vocabulary: **APPROVE**, **CHANGES REQUIRED**, **REJECT**. The author of a PR does
not approve it. D-authored PRs below record the independent A/E approval, not a D
self-approval.

## Review index

| PR / requirement | Reviewed head | Decision | Review focus | Evidence / merge |
|---|---|---|---|---|
| #2 / FR-04 test spec | review-response `9de822f`; later A-approved `510828a` | Changes required, then approved by A | B1–B6: reason codes, missing-evidence cases, parameterized freshness, harness self-check, hash record, classification | Historical approval in `docs/approvals/test-hash-FR-04-risk-gate.txt`; merge `11cfc96` |
| #15 / PRD + schema | `df13fdb` | **APPROVE** | 38-entry registry, `INV-07`→adapters, schema `exists`/boolean threshold, PRD by_type/by_component/by_owner | Merged `4d4b98d`; registry validates with 0 errors |
| #17 / FR-04 cutoff fixture | A-approved `1fd6d29` | Verified D-side test hash; A approved | One-line base cutoff fix; 139 count unchanged | Merge `b245bdb`; approval record re-bound |
| #20 / FR-04 implementation | A/E approved `5825a5d` | D author; independent A/E approval | Deterministic gate, ledger/outbox atomicity, D↔E hash compatibility, 139 tests | Merge `31d01cc`; `docs/evidence/FR-04/impl-green.txt` |
| #23 / DEBT-FR05-D4 + budget CI | `1dabad1` | **APPROVE** (D/A) | Closed false-green debt; 223/28/139 counts; budget N/A; #10 supersede | Merge `df3d64e` |
| #25 / FR-01 pack spec | `575845e` | Changes required, then **APPROVE** | Pack hash, full evidence IDs, `InvalidCitation`, E-22/E-26, date-only E-07, test hash binding | Merge `f9ca5d1`; record completed by #42 (`32532c0`) |
| #29 / D3 checkers + AGENTS | A/E approved `e66aed8` | D author; independent A/E approval | Permission/approval checkers, AGENTS entry point, 38 governance tests | Merge `d375b7a` |
| #37 / D closeout log | A/E approved `8f3cb41` | D author; independent A/E approval | Conflict resolution retaining closeout + later entries | Merge `6dc442f` |
| #38 / date-only canonical | A/E approved `474fed3` | D author; independent A/E approval | `datetime.date` normalisation, EVD-05 regression, approval-record rebind | Merge `81f25f5`; `docs/evidence/FR-04/date-only-canonical-fix.txt` |
| #40 / E3 CI wiring | reviewed at `6061c5b` | **CHANGES REQUIRED**; later merged after fixes | Role inference, evidence routing, tools/contracts scope, missing-record fail-closed | E3 jobs on main; follow-up #47/#50 |
| #43 / FR-01 implementation | `dfb7a3f` | **APPROVE** after #51 | Pack/validate implementation, A→D hash equality, CI evidence gate, no cross-module production import | Merge `dfb7a3f` |
| #45 / FR-02 budget implementation | `968999b` | **APPROVE** (D/E) | Reserved/settle, unknown usage hold, concurrency, persistence | Merge `eafaff4`; budget suite 4 passed |
| #46 / C Prompt.md | `43595d8` | Changes required, then **APPROVE** by D | Valid C AI-use YAML, read-vs-write conflict, D9 boundaries, current-main CI | Merge `68fb4f3` |
| #47 / evidence routing + budget record | `876b11b` | **APPROVE** | FR-01 pack/precedence/evidence routing, FR-02 record actual_cases 4 | Merge `320bf4d` |
| #50 / GATE-01 base fix | `4fd7bcc` | **APPROVE** (E) | PR base for implementation records; test/spec N/A; missing records fail closed | Merge `0fef55b`; reverse proof #48/#49 |
| #54 / D closeout evidence | A/E approved `181bc5c` | D author; independent A/E approval | Conflict resolution; both closeout and D5 entries retained | Merge `e797138` |
| #60 / D5 transcript | A/E approved `983b9c4` | D author; independent A/E approval | Raw/Markdown/annotations, 0 secret hits, D5 hashes | Merge `4677a11` |
| #61 / D report sections | A/E approved `99c4088` | D author; independent A/E approval | D sections + 475-word reflection + evidence index | Merge `a435640` |

## Notable review findings

- **#20 E review:** the outbox payload hash used `+00:00` while `contracts.audit`
  canonicalised UTC as `Z`; `verify_payload`/replay would reject a legitimate risk event.
  D fixed it in `6bad169`; the stored and recomputed hashes then matched. This was a
  security/audit finding, not a style issue.
- **#25 D review:** the original pack hash was caller-supplied, evidence IDs were local
  rather than full `<run_id>-<case>`, and E-26/E-22 semantics were not frozen. All were
  corrected before approval; E-07 later exposed the date-only canonical gap.
- **#40 D review:** the first E3 wiring had an evidence-directory single-record route and
  some fail-open/missing-record behaviour. #47 fixed the routing; #50 fixed the
  implementation-base false `TEST_DRIFT`.
- **#45/#50:** the normal reverse-proof control showed that using the old record commit as
  the implementation base falsely flagged later test merges as drift; #50 now uses the PR
  base and fails closed only for genuinely applicable missing records.

## Residual review risks

- C's FR-03 deliberation and transcript/report remain outside D's module ownership.
- B's D2 architecture package and C's FR-03/deliberation are external to D's module; D does not claim their completion.
- ADR-003/risk-policy remain PROPOSED/deferred (`DEBT-FR04-POLICY-APPROVAL`).
- CI-only, tools/ and some contracts paths remain human/code-owner-reviewed rather than
  fully automated gate paths.
