# EGTA OpenCode Operating Rules

Owner: D. Human-maintained. Policy only; runtime enforcement is not verified.

## Role allowlist

Use the role assigned by a human and the approved work package. Read only
relevant requirements, contracts, source, and approved tests. A write must be
permitted by both the work package and the repository allowlist.

| Role | Writable scope |
|---|---|
| Plan | Assigned plan drafts only. |
| Build-A | Evidence, approved evidence tests, D1 registry/checker, assigned FR-01 docs and A's log. |
| Build-B | Budget, app, approved adapters, their approved tests, assigned architecture/FR-02 docs and B's log. |
| Build-C | Deliberation, prompts, assigned root Prompt.md, approved tests, FR-03 docs and C's log. |
| Build-D | RiskGate, approved RiskGate tests and synthetic security fixtures, D governance checkers/docs, FR-04 evidence and D's log. |
| Build-E | Evaluation, assigned evaluation/integration tests, FR-05 evidence and E's log. |
| Verify | Assigned review and evidence reports; explicitly authorized test drafts only. No production edits or approvals. |

Use the exact paths in the permission model and tools/check_permissions.py.
Shared contracts are protected; changes require a separate B-led review with
producer and consumer involvement. Do not edit another member's unassigned
files or log. Stop if the documents and checker disagree.

## Human gates and protected files

Only humans may maintain .opencode/rules.md and executor permissions, approve
tests or ADRs, record approvals, or change CI, CODEOWNERS, and branch protection.
Agents may draft proposals but cannot apply them to these protected files.
Require human plan approval before writing the spec, independent test approval
and merge before implementation, and separate authorization for independent
verification. Do not change frozen tests or gate policy to make CI pass.

## Git and remote operations

Read-only local Git inspection is allowed within scope. An agent may create a
local commit only with explicit human authorization for that PR. Humans perform
pushes, PR creation, review approvals, merges, and protection changes. Authors
do not self-approve. These restrictions apply through every tool and script.

## Credentials

Never read, print, copy, commit, or export real .env contents, API tokens, SSH
keys, GitHub or cloud credential files, or broker credentials. Do not dump
environment variables or use paths that escape the allowed workspace. Offline
work does not use the network. Use synthetic canaries; keep live credentials
inside the separately controlled runner.

## Approval-record exception

docs/approvals/ remains human-only. The designated human may record a real,
traceable independent review, preferably in a record-only PR with explicit
review. Any CI exception for this update is not agent authorization and waives
no other violation. Keep the test-content SHA, reviewed PR head, merge SHA,
and file hashes distinct where applicable. Never infer sign-off from green CI.

## Evidence

Stop and report an unapproved or failed gate. Record the exact command, commit,
exit code, and evidence location. Markdown, CI checks, and runtime permissions
are separate controls. Claim runtime enforcement only after a safe refusal
test in an isolated workspace.
