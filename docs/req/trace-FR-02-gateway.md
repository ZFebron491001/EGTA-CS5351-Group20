# Trace — FR-02 budget-gateway adapter + runner integration (test-first spec)

- **Status:** DRAFT (test-first). Companion to `docs/req/spec-FR-02-gateway.md`.
- **Tests:** `test/offline/integration/test_gateway.py` (4 adapter cases) +
  `test/offline/integration/test_runner_cli.py` (4 runner/CLI cases), with
  `test/offline/integration/conftest.py` + `fakes_gateway.py`.
- **Depends on:** #22 (budget spec, merged), #45 (`src/egta/budget/` governor, merged),
  the RiskGate (D FR-04), E's SqliteAuditSink
- **Why a separate suite:** the four adapter cases were previously inside
  `test/offline/budget/`; with `-m spec` that directory then collected 8, which would
  break the #22 approval record (`actual_cases: 4`). They are moved to
  `test/offline/integration/` so `test/offline/budget` keeps exactly 4. The frozen
  #22 files (`test_reservation_holds.py`, `test_admission.py`, `conftest.py`,
  `fakes.py`) are unchanged.

## Candidate adapter interface (needs E/C)

`BudgetedModelGateway` — proposed for `src/egta/adapters/model_gateway.py`. NOT frozen.

```
BudgetedModelGateway(governor=BudgetGovernor, llm=<chat model>, call_spec=<dict>)
  .invoke(prompt)             -> reserve; refused => no send; granted => send + settle
  .bind_tools(tools)          -> returns a gateway that admits ONLY on .invoke
  .with_structured_output(s)  -> returns a gateway whose .invoke admits per send
```

The adapter is the object the tests call; it — not the test — triggers `reserve`,
the send, and `settle`. This is the wiring the production code must provide.

## Candidate adapter refusal exception

#45's `BudgetDenied` is a governor RETURN value (a plain dataclass, not an
exception), so the adapter cannot raise it. The candidate adapter therefore raises
**`BudgetDeniedError`** (proposed in `src/egta/adapters/model_gateway.py`) carrying
`reason_code == "BUDGET_DENIED"`. Both refusal tests assert this one exception and its
`reason_code`; it is a candidate interface pending E/C, like the adapter itself.

Two different notions of "denied" are kept distinct:
- **Adapter refusal** (unit scope here): a governed send with no budget raises
  `BudgetDeniedError` and the provider is NOT called.
- **Workflow final status** (not covered here): what the full run reports on
  exhaustion (`INCOMPLETE` vs a governor status) is E's decision and is listed below.

## Coverage (test-first; four tests, all currently RED)

Every test shares ONE ``events`` list. A spy wraps the real governor's ``reserve``:
it CALLS the real ``reserve`` first, then records the returned outcome as
``("reserve", outcome)``; the MockTransport handler records ``("send", kind)``. So
admission and transport are observed in one order, not just a send count.

Scope of these four cases: they cover the **admission/send ordering** (does the
gateway reserve before sending, and refuse before sending). ``settle`` (usage
settlement / the amount released per axis) and **sent-then-timeout keeps the
reservation held** are NOT exercised here and remain for later verification.

| # | Test | Adapter entry | Fixture | Expected event sequence |
|---|---|---|---|---|
| 1a | `test_ample_budget_reserve_then_send` | `gw.invoke` | real `NormalizedChatOpenAI` + MockTransport; ample limits | `[("reserve","Reservation"), ("send","chat")]` |
| 1b | `test_zero_budget_reserve_refused_transport_zero` | `gw.invoke` | zero limits `{0,0,"0"}` | `[("reserve","BudgetDenied")]`; raises `BudgetDeniedError` (reason_code `BUDGET_DENIED`); no send |
| 2 | `test_bind_tools_admits_nothing_then_bound_chain_admits_once` | `gw.bind_tools` then REAL `prompt \| bound` chain `.invoke` | ample limits; tool schema | bind: `[]`; after chain: `[("reserve","Reservation"), ("send","structured")]` (request carries tools) |
| 3 | `test_structured_400_fallback_readmits_allowance_one_transport_one` | original `invoke_structured_or_freetext(structured, gw, ...)` | allowance 1; structured → HTTP 400; reserve covers the 2-token reply | `[("reserve","Reservation"), ("send","structured"), ("reserve","BudgetDenied")]`; second admission refused |

The structured case uses a real Pydantic schema (`_Report(BaseModel)`), the project's
original helper, and parses the MockTransport JSON body (`tools` present => structured)
to classify requests. Reservation for the ample cases uses `max_tokens=8`, covering
the simulated 2-token reply.

## Runner / CLI coverage (test-first; four cases, currently RED)

`test/offline/integration/test_runner_cli.py`. Only the MODEL is faked; budget, risk
and audit use their real implementations.

| # | Test | Entry | Fakes | Expected |
|---|---|---|---|---|
| R1 | `test_runner_normal_admit_before_send_real_risk_and_audit` | `egta.app.runner.run_offline` | fake provider reply; fixed evidence/proposal | admits before 1 send; real RiskGate `APPROVED`; ledger +1; `result.run_id == proposal.run_id`; audit by that run_id non-empty; evidence hash == pack hash |
| R2 | `test_runner_risk_reject_ledger_unchanged_audit_reason` | `run_offline`, known reject fixture (insufficient cash) | fake provider | real gate `REJECTED` + `POLICY_REJECTED` (verified standalone); `result.run_id == proposal.run_id`; ledger unchanged; audit by that run_id carries the reason |
| R3 | `test_runner_budget_deny_transport_zero_shared_reason` | `run_offline`, zero limits | fake provider (must get 0) | provider receives 0; `reason_code == ReasonCode.BUDGET_DENIED`; `result.run_id == proposal.run_id`; ledger unchanged; audit by that run_id has a BUDGET_DENIED event; terminal status **not** asserted (pending E) |
| R4 | `test_cli_offline_entry_parses_and_invokes_runner` | `python -m egta` | — | `egta.__main__.main` exists |

## RED status (real, 2026-11-23)

Recorded against latest `origin/main` `48c324f` (PR #62 merged; contains #45 governor). The
integration suite overlaid into a scratch worktree of main (nothing committed):
business assertions executed **0**; every failure is a lazy import inside a test
body, not collection, and no business `assert` is reached.

- **Governor (frozen #22):** `pytest -m spec test/offline/budget -q` → **4 passed**
  (count preserved; the 4 gateway cases are no longer in this directory).
- **Integration (new):** `pytest -m spec test/offline/integration -q` → **8 collected,
  8 failed**:
  - 4 fail → `ModuleNotFoundError: No module named 'egta.adapters'` (adapter cases);
  - 3 fail → `ModuleNotFoundError: No module named 'egta.app'` (runner R1/R2/R3);
  - 1 fails → `ModuleNotFoundError: No module named 'egta.__main__'` (CLI R4).
- **On this branch (pre-#45 ancestor):** governor 4 + integration 8 all fail at
  `egta.budget` (the branch predates #45); this is expected and superseded by the
  main-based record above.
- `ruff check test/offline/integration/ test/offline/budget/` → All checks passed;
  `py_compile` exit 0.

## Coverage: tested vs needs-integration (per production entry)

| Production entry | Status |
|---|---|
| Tool binding (`turn.py:26`) | **spec, RED (adapter case 2)** |
| Structured output first send (`structured.py:69`) | **spec, RED (adapter case 3)** |
| Structured→free-text fallback re-admit (`structured.py:95`) | **spec, RED (adapter case 3)** |
| Zero-budget send refused (`gw.invoke`) | **spec, RED (adapter case 1b)** |
| Ample-budget reserve→send (`gw.invoke`) | **spec, RED (adapter case 1a)** |
| Normal / risk-reject / budget-deny run wiring | **spec, RED (runner R1/R2/R3)** |
| CLI offline entry | **spec, RED (R4)** |
| `propagate()` over the real graph (`trading_graph.py:167`) | **needs integration** |
| CLI `stream_run` over the real graph (`cli/run.py`) | **needs integration** |
| Reflection (`memory/reflection.py:63`) | **needs integration** |
| Jev direct HTTP (`post_screen.py:68`) | **needs integration** (bypass until adapter) |
| SDK implicit retry (`factory.py:123-125`) | **needs integration** (`max_retries=0`) |
| Explicit retry | **needs integration** (each attempt re-admits) |
| Sent-then-timeout keeps reservation held | **needs integration** (settle(id, None)) |

## Not covered (acceptance-only, no callable entry yet)

- **Final run status** on budget exhaustion (propagate/CLI): E to confirm; runner R3
  asserts membership in an existing contract enum (`CompletionStatus`) only.
- **C's independent model calls** (any deliberation model call outside the shared
  `get_llm()` object): C to confirm; full deliberation integration pending; the
  runner uses a FIXED proposal fixture in the meantime.
- **Jev direct-HTTP path** (`agents/post_screen.py:68` `requests.post`): must reserve per
  attempt; pending its own adapter.
- **Explicit-retry accounting**: each explicit retry must re-admit; needs a call site.
- **Sent-then-timeout end-to-end**: the governor holds an unsettled reservation (#22),
  but the real send-timeout → `settle(id, None)` proof is still integration acceptance.

## Reused-as-is

`test/offline/budget/test_reservation_holds.py`, `test_admission.py`, `conftest.py`,
`fakes.py` stay byte-identical to #22 (the frozen governor spec).
