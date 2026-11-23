# Trace — FR-01 classification-precedence spec (test-first)

Requirement-to-test trace for `test/offline/evidence/test_pack_precedence.py`
(this spec PR). It is **test/spec only — no implementation**; the implementation
lands in the descendant FR-01 impl PR (which must descend from this spec's merge
commit per GATE-01).

## What this branch is / is not

- **Is**: 4 additive pack-level cases that pin the *classification precedence*
  among exclusion causes. The frozen pack spec `test_pack.py`
  (`test-hash-FR-01-pack.txt`, `actual_cases: 33`) and its trace
  `docs/req/trace-FR-01-pack.md` do not cover these.
- **Is not**: the 33 frozen cases; any `src/` change; any implementation.
- **RED by design**: `pytest -m spec test/offline/evidence/test_pack_precedence.py`
  → 4 errors (`ImportError: cannot import name 'InvalidCitation' from 'egta.evidence'`
  / `egta.evidence.pack` absent), no xfail/skip.

## Contract-level decision (not implementation-defined)

Classification runs **integrity → staleness → time → dedupe**, first match wins.
The cache step rests on the E-26 rule already frozen in
`docs/req/trace-FR-01-pack.md` ("`source_type == "cache"` is always stale
(`STALE_DATA`/`stale`); no freshness threshold"). This spec makes the *ordering*
of that rule against integrity and time explicit; it is not "whatever the
implementation does" — the tests below assert it.

## Precedence and INV-02 reconciliation

INV-02 freezes: a date-only/day value on the same UTC date is excluded with
`FUTURE_DATA`, never `INVALID_TIME`, and `future_items_admitted == 0`. The cache
rule does not violate INV-02:

- A **future-dated cache** item is still **excluded** (never admitted), so the
  INV-02 metric `future_items_admitted == 0` still holds. It is reported as
  `STALE_DATA` rather than `FUTURE_DATA` because the cache check is a
  broader/stronger reason (off-line cache is unverifiable regardless of its
  date), and it runs before the time filter. `STALE_DATA` and `FUTURE_DATA` are
  both `availability != available`; the reason code differs but the item is not
  admitted either way.
- A **future non-cache** item is excluded with `FUTURE_DATA`, exactly as INV-02
  requires (control case).
- INV-02's own time-policy suite (`test_time_policy.py`) and the frozen pack
  cases (E-16 FUTURE_DATA, E-17 EVIDENCE_MISSING) are unchanged and still pass.

INTEGRITY before staleness: a tampered cache item (excerpt hash mismatch) is
`INTEGRITY_VIOLATION`, not `STALE_DATA`. Integrity is the most specific,
audit-critical cause (FR-01/T04); downgrading a tampered item to a generic
"stale" would hide tampering.

## Test function → requirement mapping

| Test function | Covers | Input | Expected |
|---|---|---|---|
| `test_tampered_cache_is_integrity_not_stale` | FR-01 (audit/T04), INV-02 (excluded) | cache item, sha256(excerpt)!=content_hash | INTEGRITY_VIOLATION / unavailable |
| `test_well_formed_cache_still_stale` | FR-01, E-26 rule (control) | clean cache item | STALE_DATA / stale |
| `test_future_cache_is_stale_not_future_data` | INV-02 (future not admitted), precedence | cache item, published_at after as_of | STALE_DATA / stale |
| `test_future_non_cache_is_future_data` | INV-02 (control) | non-cache item, future (E-16) | FUTURE_DATA / unavailable |

## Approval

- On D approval: fill `reviewed_pr_head`, `merge_commit`, `approved_by` in
  `docs/approvals/test-hash-FR-01-precedence.txt`.
- The descendant impl PR's CI evidence gate reads expected = 33 (frozen record) +
  4 (this record) = 37 for the `evidence` suite, via `RECORDS:` (not hardcoded).
