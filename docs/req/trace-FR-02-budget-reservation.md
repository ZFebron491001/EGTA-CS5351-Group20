# Trace — FR-02 / INV-03 budget reservation (test-first spec)

Requirement-to-test trace for `test/offline/budget/test_reservation_holds.py`.
Focus: the 11/21 independent task "an interruption or an unknown-usage outcome must
not release a budget reservation early" (TimeLine Day 2 B; plan §7.3 B3).

**Spec/test only. No `src/` implementation.** The `governor_factory` fixture always
returns a factory; a behavioural test fails red when it CALLS that factory (the lazy
`from egta.budget import BudgetGovernor` inside it), so each case fails individually
and they are not skipped.

## Requirement basis

- §7.3 B3: "完成中断与未知 usage 测试，证明预留不会提前释放".
- §5.3 Budget ledger: "每次 reserve/settle 持久化；未知 usage 不释放预留".
- §7.3 delivery: "不得仅记录调用后的 token"; INV-03 "每次外部模型调用先获预算预留".
- Plan line 131: "usage 不明时保留预留额，不把额度提前返还".
- Day 2 gate G1: 正常 / 拒绝 / 超预算 three paths; this PR covers the denial stay-held
  path for unknown usage.

## Frozen entry points (§5.1)

    BudgetGovernor.reserve(call_spec) -> Reservation | BudgetDenied
    BudgetGovernor.settle(reservation_id, actual_usage_or_unknown) -> BudgetState

These two signatures are frozen by the plan. Everything else used by the tests
(`call_spec` shape, `Reservation` attributes, `BudgetState` shape, how "unknown"
is encoded, persistence backend) is NOT frozen; see "Open interface questions".

## Coverage

All three tests are governor-layer only (no HTTP, no fake governor). A refusal is
asserted ONLY as the contract type `BudgetDenied` (never `None` or a truthiness
guess); a grant is asserted POSITIVELY as the contract type `Reservation` (so
`None` or a wrong value cannot pass as a grant either).

| # | Test | Requirement | Scenario | Pass condition |
|---|---|---|---|---|
| 1 | `test_unknown_usage_holds_token_reservation_denies_one_token_followup` | FR-02, INV-03, §5.3 | Reserve the whole token axis; `settle(id, unknown)`; then ask for **1 token** | second `reserve` returns `BudgetDenied` (the held 1000 tokens were NOT refunded on unknown usage; even 1 token is denied) |
| 2 | `test_outstanding_unsettled_reservation_denies_one_token_followup` | FR-02, INV-03, §5.3 | Reserve the whole token axis; do NOT settle; ask for **1 token** | second `reserve` returns `BudgetDenied` (an outstanding reservation is not reusable) |
| 3 | `test_known_low_usage_releases_tokens_grants_one_token_followup` | FR-02, INV-03 | SAME limits; `settle(id, known 100 tokens)`; then ask for **1 token** | second `reserve` returns a `Reservation` (positive type assert): 900 free >= 1, proving the governor CAN grant when balance exists |

### Why only the token axis is tight (hand-check)

Limits (identical for every test): `max_total_tokens=1000`, `max_calls=5`,
`max_cost_usd=1.00`.

| Test | First call asks | Settled as | Tokens free after settle | Follow-up asks | Fits? | Expected |
|---|---|---|---|---|---|---|
| 1 (unknown) | 1000 tok, 1 call, $0.01 | unknown (held) | 1000 held, **0 free** | **1 tok** | no | **BudgetDenied** |
| 2 (outstanding) | 1000 tok, 1 call, $0.01 | not settled | 1000 held, **0 free** | **1 tok** | no | **BudgetDenied** |
| 3 (control) | 1000 tok, 1 call, $0.01 | known 100 tok | 900 free | **1 tok** | yes | **Reservation** |

All three use the SAME limits, the SAME first `FULL_TOKEN_CALL` (1000 tokens), and
the SAME `FOLLOWUP_ONE_TOKEN` (1 token); they differ ONLY in the settle condition.
Calls (1/5) and cost ($0.01/$1.00) have spare room, so the follow-up is never denied
merely because call count or cost ran out. Because the follow-up is only 1 token,
a governor that refunds even a few tokens early (on unknown usage, or before settle)
would GRANT it, so tests 1 and 2 catch a partial early refund — not just a full one.
Test 3 shows the same 1-token follow-up IS granted once 900 tokens are truly free,
so the denials are about the held tokens, not a governor that refuses everything.

## RED status on this branch (real)

The `egta` namespace exists via `src/egta/evidence`, so the error is specifically
the missing budget module.

Verified earlier on baseline `69da0e464b562d54bcfdec5beb84bd98bbf8a943`
(`origin/main` before the D-only fast-forward; branch `spec/B-budget-reservation-v2`),
and re-verified on the current baseline **`0ab1c823b62f6cc75c96463f46a72a81da56ed9b`**
(`origin/main` after D's two records; this branch fast-forwarded to it, keeping all
five working files). Same results on both:

- `python -m ruff check .` → All checks passed (exit 0)
- `python -m py_compile test/offline/budget/*.py` → exit 0
- `python -m pytest -m spec test/offline/budget/ --collect-only -q` → **3 collected**
  (the three tests are selected by `-m spec`), exit 0
- `python -m pytest -m spec test/offline/budget/ -q --tb=line` → **3 collected,
  3 executed, 3 failed**, exit 1; first error `ModuleNotFoundError: No module named
  'egta.budget'` at `conftest.py:64` (the lazy `from egta.budget import BudgetGovernor`
  reached when a test calls `governor_factory()`). Business assertions executed: **0**
  (no governor exists). This is NOT a collection error and NOT "0 executed".
- Default suite is unaffected: `python -m pytest -q` → `1412 passed, 1 skipped,
  1 deselected, 24 warnings, 100 subtests passed` (the budget spec is excluded by
  `-m "not integration and not spec"`).

## What the tests deliberately do NOT do

- No governor implementation, no fake governor, no fabricated persisted state.
- No freeze of `call_spec`/`Reservation`/`BudgetState` shapes.
- No claim that integrity/business behaviour passes; they assert the stay-held rule
  once the governor exists.

## Candidate interface (needs B/E review)

The refusal RESULT is frozen by plan §5.1: `reserve(...) -> Reservation |
BudgetDenied`. The tests import `BudgetDenied` and `Reservation` from
`egta.budget`; that public import path (module location / export name) is a
candidate, not yet frozen. The other items below are a MINIMAL proposal the tests
currently assume; each is a single choice rather than a guess-with-fallbacks.

- **Public import path:** `from egta.budget import BudgetGovernor, Reservation,
  BudgetDenied`. Candidate (the result TYPES above are frozen; their module/export
  path is what needs confirming).
- **Construction:** `BudgetGovernor(limits=<dict>, db_path=<Path>)`. Candidate.
- **`call_spec`:** a dict with `max_tokens`, `max_calls`, `max_cost_usd`. Candidate.
- **`limits` keys:** `max_total_tokens`, `max_calls`, `max_cost_usd`. Candidate.
- **Unknown usage:** `settle(rid, actual_usage_or_unknown=None)` — `None` = unknown.
  Candidate; alternatives are a dedicated enum member or a separate
  `settle_unknown(rid)`.
- **Known usage:** `settle(rid, actual_usage_or_unknown={"tokens": N})`. Candidate.
- **Reservation id:** `Reservation.reservation_id`. Candidate.

## Not covered here (future)

- **Real-gateway send-then-interrupt:** a request that actually leaves, times out
  after send, and whose follow-up shows ZERO new transport requests. Deferred to the
  gateway integration test; a governor-only test cannot prove transport behaviour.
- **Durable restart recovery:** "run 内恢复" surviving process restart.
- **Concurrency / no over-sell** under parallel reserve (B2 case).
- **SDK retry accounting:** retries must not double-charge or bypass reserve.
- **End-to-end `propagate`/CLI** proving all model calls pass through the governor.
