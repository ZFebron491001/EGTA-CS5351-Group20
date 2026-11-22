# Trace — FR-01 classification-precedence spec (test-first)

Requirement-to-test trace for `test/offline/evidence/test_pack_precedence.py`
(this spec PR). It is **test/spec only — no implementation**; the implementation
lands in the descendant FR-01 impl PR (which must descend from this spec's merge
commit per GATE-01).

## What this branch is / is not

- **Is**: 4 additive pack-level cases that pin the *classification precedence*
  among exclusion causes. The frozen pack spec `test_pack.py`
  (`test-hash-FR-01-pack.txt`, `actual_cases: 33`) does not cover these.
- **Is not**: the 33 frozen cases; any `src/` change; any implementation.
- **RED by design**: `pytest -m spec test/offline/evidence/test_pack_precedence.py`
  → 4 errors (`ImportError: cannot import name 'InvalidCitation' from 'egta.evidence'`
  / `egta.evidence.pack` absent), no xfail/skip.

## Contract-level decision (not implementation-defined)

The precedence **integrity → staleness → time → dedupe** is a contract-level
decision, recorded in `docs/req/trace-FR-01-evidence-impl.md` and the frozen
E-26 rule ("`source_type == 'cache'` is always stale"). It is not "whatever the
implementation does": the tests below assert the decision explicitly.

| Test function | Covers | Input | Expected |
|---|---|---|---|
| `test_tampered_cache_is_integrity_not_stale` | FR-01 / T04 audit | cache item, sha256(excerpt)!=content_hash | INTEGRITY_VIOLATION / unavailable |
| `test_well_formed_cache_still_stale` | INV-02 / E-26 (control) | clean cache item | STALE_DATA / stale |
| `test_future_cache_is_stale_not_future_data` | precedence | cache item, published_at after as_of | STALE_DATA / stale |
| `test_future_non_cache_is_future_data` | INV-02 (control) | non-cache item, future (E-16) | FUTURE_DATA / unavailable |

## Approval

- On D approval: fill `reviewed_pr_head`, `merge_commit`, `approved_by` in
  `docs/approvals/test-hash-FR-01-precedence.txt`.
- The impl PR's CI evidence gate reads expected = 33 (frozen record) + 4 (this
  record) = 37 for the `evidence` suite.
