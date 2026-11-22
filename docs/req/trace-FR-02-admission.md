# Trace — FR-02 / INV-03 budget admission (governor-layer spec + gateway-pending list)

Requirement-to-test trace for `test/offline/budget/test_admission.py`. This
complements `test_reservation_holds.py` (the token-hold spec, PR #22).

**Spec/test only. No `src/` implementation.** This file delivers the ONE governor
test that can be written honestly today; the rest are listed as gateway-wiring
acceptance items because no unified gateway entry exists yet.

## Requirement basis

- Day 1 (B, evening): reserve/settle with a concurrency lock.
- Day 2 (B, morning): interruption / unknown-usage tests, reservation not released.
- §5.1: `reserve(call_spec) -> Reservation | BudgetDenied`;
  `settle(reservation_id, actual_usage_or_unknown) -> BudgetState`.
- §5.3: reserve/settle persisted; unknown usage does not release; run-scope recovery.
- §7.3 B3: no over-sell; all model calls pass through the governor; SDK implicit
  retry disabled; do not record only post-call tokens.

## Delivered test (governor layer)

| Test | Chain | Expected | Simulation? |
|---|---|---|---|
| `test_two_concurrent_calls_do_not_oversell_one_slot` | test starts 2 threads (barrier) → each calls `gov.reserve`; governor's lock decides | both entered; **exactly one `Reservation` and one `BudgetDenied`** | none: pure governor assertion; NO transport count is claimed |

The barrier has a timeout and each worker join has a timeout, so a hung thread fails
the test instead of blocking it.

## Pending gateway wiring (NOT written as tests — would pass despite a real bypass)

The following were drafted before but are removed because, without a unified gateway
entry that lets the TESTED code trigger the send/fallback/admission, a budget bypass
in the project's real path would still pass. There is no gateway/budget entry on
`main` today. Each is an acceptance condition to implement once the gateway exists:

1. **Tool binding does not spend budget; the bound call admits.**
   - Must drive the real bound object (``bound.invoke``), not ``gov.reserve`` by hand.
   - Acceptance: binding admits nothing; one bound call yields one admission.
2. **Structured HTTP 400 → plain-text fallback admits again, via the real helper.**
   - Must call the project's ``tradingagents.agents.structured.invoke_structured_or_freetext``
     (with the gateway-wrapped model) so the tested code triggers the fallback and
     the second admission itself.
   - Acceptance: two separate admissions; process-local transport log
     ``["structured","chat"]``.
3. **Allowance 1 + structured 400 → fallback denied, transport total 1.**
   - Same real-helper path; the second admission must be refused by the governor.
   - Acceptance: first `Reservation`; fallback `BudgetDenied`; transport total 1.
4. **Same business entry under ample and zero budget (gateway wiring).**
   - Must call the real entry (app/runner/gateway), NOT a test-built `_run_entry_once`.
   - Acceptance: ample → admitted + 1 send; zero → entry runs, admitted result is
     denied, transport 0; final run status per the frozen contract (see Q1).
5. **Sent, then interrupted before usage (gateway wiring) — token is the only tight
   axis.**
   - Setup: first call reserves **1000/1000 tokens** (calls and cost have spare room).
   - Behavior: via the tested entry, the first request leaves; the mock/real transport
     records it then the call times out **before** usage is confirmed; then a SECOND
     request for **1 token** through the SAME entry.
   - Acceptance: the second request is refused (`BudgetDenied`); the reservation is
     still held (token not refunded — call/cost spare room means the denial cannot be
     explained by those axes); transport total stays 1.
   - Why it needs wiring: the timeout must reach the budget logic through a public
     entry that owns reserve/settle. A governor-only test cannot route a client
     timeout back into the reservation, and re-inventing a gateway in the test would
     hide a real bypass. This is the "interruption" complement to #22's outstanding
     reservation (which never sends) and is distinct from cross-process recovery.

Observed client behavior (for the future item 5): a real ``NormalizedChatOpenAI`` over
``httpx.MockTransport`` that records then raises ``httpx.ReadTimeout`` surfaces
``langchain_openai.chat_models.base.OpenAITimeoutError`` (a subclass of
``openai.APITimeoutError``) to the caller, with the request having left once. Note:
``httpx.MockTransport`` records an IN-PROCESS received request; it is not proof of a
real socket send.

## Reuse vs. #22 bytes (avoid duplicate delivery)

Compared against #22 fixed commit `efa4bbe1d4aa5b3c0e9530e95eee58b637f92adc`:

- `test/offline/budget/conftest.py`: **byte-identical** to #22. After #22 merges, take
  it from #22; do not re-deliver.
- `test/offline/budget/fakes.py`: byte-identical #22 prefix + a small admission
  suffix (`ONE_CALL_LIMITS`, `ONE_CALL_ASK`). After #22 merges, keep only the suffix.
- `test_reservation_holds.py`: untouched; #22's three cases and semantics are preserved.
- `test_admission.py`: this branch's new file (1 test).

## Evidence and baseline

History (earlier draft worktree `spec/B-budget-admission`, HEAD `6830926`, draft
untracked): the isolated draft was authored and first run there; results in the
"RED status" below are re-run in the #22 worktree described next.

Final run (this commit's worktree — the #22 branch, `spec/B-budget-reservation-v2`):

- Worktree HEAD at run time: `efa4bbe1d4aa5b3c0e9530e95eee58b637f92adc`.
- Verification ran on HEAD `efa4bbe` with the local, uncommitted admission increment.
- `origin/main` queried during this session: `141547a87f6781abf85ee51fba33898d7c0db671`
  (after the #21 merge). The increment was **not** separately re-run on a `141547a`
  checkout; it ran on the `efa4bbe` worktree above.
- `httpx.MockTransport` records in-process received requests only; it is not proof
  of a real socket send.

## RED status on this branch (real, #22 worktree at `efa4bbe` + increment)

The explicit budget spec now selects all four tests (three reservation from #22 +
the one admission test):

- `python -m ruff check .` → All checks passed (exit 0)
- `python -m py_compile test/offline/budget/*.py` → exit 0
- `python -m pytest -m spec test/offline/budget/ --collect-only -q` → **4 collected**
- `python -m pytest -m spec test/offline/budget/ -q --tb=line` → **4 collected,
  4 executed, 4 failed**, exit 1; every failure at `conftest.py:64`
  (`ModuleNotFoundError: No module named 'egta.budget'`); **business assertions
  executed: 0**. Not a collection error, not "0 executed".

## Open questions for E / C

For **E**: (1) final run status when budget is exhausted at the entry
(`INCOMPLETE` vs a dedicated governor status); (2) whether tool binding lives on the
governor or a gateway/adapter; (3) structured + fallback = two separate admissions
(this spec's expectation, consistent with the client sending twice).

For **C**: (4) the fake gateway interface: how a bound-tool call and a structured
fallback route through the single admission point, and how the gateway surfaces
"interrupted after send, before usage" to the budget layer. This is what turns items
1–5 above into real tests.

## Not covered here

- Cross-process durable restart recovery.
- SDK retry accounting (retries must not double-charge or bypass reserve).
- End-to-end `propagate`/CLI run status.
