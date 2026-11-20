# Trace — FR-05 contracts (test-first spec)

Requirement-to-test trace for the `RunEvent` and `ExperimentManifest` contracts.
This is the **spec/test** artifact only; implementation is delivered separately
via an implementation PR that must descend from this spec's merge commit.

## Requirement mapping

| Requirement | Statement (summary) | Covered by |
|---|---|---|
| FR-05 | Comparison & Audit Report: structured, replayable events and controlled-experiment manifest that make baseline vs enhanced comparable. | `test_events.py`, `test_manifest.py` |
| NFR-08 | Reproducibility: hash-chained append-only events, offline deterministic checks, fixed input snapshot/manifest identity. | hash-chain + tamper tests; manifest hash-field tests |
| NFR-09 | Observability: every event carries `run_id`, `phase`, `status`, `metrics`, `reason_code`. | `RunEvent` field/status/reason_code tests |

## Test files

| File | Purpose |
|---|---|
| `test/offline/contracts/__init__.py` | package marker |
| `test/offline/contracts/conftest.py` | adds repo `src/` to `sys.path` so `egta.contracts` imports without packaging it |
| `test/offline/contracts/test_events.py` | `RunEvent` fields, hash/format rejection, timezone, extra-field, reason_code, hash-chain tamper |
| `test/offline/contracts/test_manifest.py` | `ExperimentManifest` required variants (B0/B1), hash fields, timezone, rubric behavior |

## Test-first status (RED by design)

This spec branch carries **tests only** — no `src/egta/contracts/` implementation.
On this branch the tests fail at import (`ModuleNotFoundError: egta.contracts`).
**That red is the intended signal** that implementation has not yet been
accepted. The spec must not be masked with `xfail`/`skip`; a `--collect-only`
run is used to prove the tests are collectable, and full green is expected only
after the implementation PR (descending from this spec) lands.

## Coverage of negative cases

See the negative examples enumerated in the Spec PR body (including which are
new this round, e.g. sequence gap, duplicate `event_id`, replay determinism,
non-finite/NaN metrics, incompatible experiment configuration, illegal
variant/rubric configuration). Where current behavior is permissive (e.g.
`metrics_rubric` accepts `{}`), the test asserts the **current** behavior
explicitly and the gap is tracked as debt rather than hidden.

## Approval

- Approval authority: **D (@ZFebron491001)** under GATE-01.
- Author (@jianmin2004) must not self-review.
- Approval binds to the test content hash in
  `docs/approvals/test-hash-FR-05-contracts.txt`.
