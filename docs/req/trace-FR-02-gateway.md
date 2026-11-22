# Trace — FR-02 budget-gateway adapter (test-first spec)

- **Status:** DRAFT (test-first). Companion to `docs/req/spec-FR-02-gateway.md`.
- **Tests:** `test/offline/budget/test_gateway.py` (+ `fakes_gateway.py`).
- **Depends on:** #22 (budget spec, merged), #45 (`src/egta/budget/` governor).

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

## RED status (real)

Baseline `bc0e1cd` (== `origin/main`). Two runs, business assertions executed **0**
in BOTH:

- **Default worktree (no #45):** 4 collected, 4 failed — all four at `conftest.py:64`
  importing `egta.budget` (`from egta.budget import BudgetGovernor`, #45 not merged).
- **Joint with #45 fixed head `2173d6ff5b51e6218b0b6d7cd3be8fa1c6c229ca`** (overlaid in
  a scratch copy; nothing of E's committed here): 4 collected, 4 failed — all four at
  `test_gateway.py:47` importing **`egta.adapters`** (the candidate adapter is unbuilt).

So once the governor is present, RED lands cleanly on the adapter module (`egta.adapters`),
not on the budget layer.
- `ruff check test/offline/budget/` → All checks passed (exit 0); `py_compile` exit 0.
- **Fixture soundness probe** (no adapter, real client): `prompt | bound` reaches
  MockTransport as `["structured"]`; `invoke_structured_or_freetext` on a 400 yields
  `["structured","chat"]` — the fixtures do exercise the real send paths.

## Not covered (acceptance-only, no callable entry yet)

- **Final run status** on budget exhaustion (propagate/CLI): E to confirm.
- **C's independent model calls** (any deliberation model call outside the shared
  `get_llm()` object): C to confirm; if present it needs the same gateway.
- **Jev direct-HTTP path** (`agents/post_screen.py:68` `requests.post`): must reserve per
  attempt; pending its own adapter.
- **Explicit-retry accounting**: each explicit retry must re-admit; needs a call site.

## Reused-as-is

`test/offline/budget/test_reservation_holds.py`, `test_admission.py`, `conftest.py`,
`fakes.py` stay byte-identical to #22 (the frozen governor spec).
