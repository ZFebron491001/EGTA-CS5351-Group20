# FR-02 / INV-03 — Model-gateway integration: acceptance spec

- **Status:** DRAFT (test-first spec, B). Targets the failure mode the governor
  cannot catch on its own: **a model call that bypasses `BudgetGovernor.reserve`.**
- **Depends on:** #22 (budget spec, merged), #45 (`src/egta/budget/` governor API).
- **Related:** plan §5.1/§5.3/§7.3 B1–B4; `trace-FR-02-admission.md` (pending-gateway list).

## 1. Model-entry inventory (where a request actually leaves the process)

Every external model call funnels through a LangChain chat model built at
`tradingagents/graph/trading_graph.py:79-80` via `create_tier_client(...).get_llm()`.
The **only** object that can send is that chat model's `.invoke(...)`. The Jev
screener is a separate, direct-HTTP path.

| Entry | File / function | Who sends | Bypass? |
|---|---|---|---|
| CLI | `cli/run.py` → `TradingAgentsGraph(...)` → `graph.stream_run` | the chat models created in `trading_graph.py:79-80` | same models; no gateway hook today |
| `propagate()` | `trading_graph.py:167` → `_run_graph` → `self.graph.invoke` | same chat models | same |
| Tool-bound analyst turn | `agents/analysts/turn.py:26` `(prompt \| llm.bind_tools(tools)).invoke(...)` | chat model | **sends directly**; binding happens on the model |
| Plain analyst wrap-up | `turn.py:24` `(prompt \| llm).invoke(...)` | chat model | sends directly |
| Structured output | `agents/structured.py:69` `structured_llm.invoke(prompt)` | chat model (derived `with_structured_output`) | sends directly |
| Structured→free-text fallback | `agents/structured.py:95` `plain_llm.invoke(prompt)` | chat model | **second send**; separate from the first |
| Researchers/managers/debators | `bull/bear_researcher`, `portfolio_manager:85`, `research_manager`, `aggressive/conservative/neutral_debator:48` `llm.invoke(...)` | chat model | send directly |
| Reflection (memory) | `tradingagents/memory/reflection.py:63` `self.quick_thinking_llm.invoke(...)` | the SAME quick model (`trading_graph.py:106`) | sends directly; outside the graph nodes |
| **Jev screener** | `agents/post_screen.py:68 system_one → requests.post(...)` with retry loop (`for attempt in range(_ATTEMPTS)`, retries on 429/529/transient) | **`requests` directly, NOT the chat model** | **confirmed bypass**: never touches `get_llm()` |
| SDK implicit retry | `llm_clients/factory.py:123-125` forwards `max_retries` to the chat model | the SDK, inside one `.invoke` | invisible to `reserve`; N calls → 1 reserve unless disabled |

**Candidate interception point (not yet chosen).** There is no single unified gateway
object today. The `get_llm()` return at `trading_graph.py:79-80` is recorded here as a
**candidate** integration point: it is the one object shared by the graph's chat-model
sends (analysts, researchers, managers, debators, structured output, the structured→
free-text fallback, and reflection, which reuses the same quick model at
`trading_graph.py:106`). Installing a gateway wrapper there is a *proposal* to be
confirmed with E/C, not a frozen decision.

Coverage boundaries of that candidate are stated explicitly rather than assumed:

- **`bind_tools` and `with_structured_output` derived objects**: both are produced by
  methods on the same `NormalizedChatOpenAI` (`openai_client.py:20`); whether the
  wrapper captures those derived runnables depends on how it is built (it must
  re-admit on the *derived* object's `.invoke`, or the derivation bypasses the
  governor). The adapter spec pins this explicitly (case 2/3).
- **reflection**: reuses the same quick model object, so a wrapper at `get_llm()`
  covers it *only if* the reflector holds the wrapped object; today
  `Reflector(self.quick_thinking_llm)` at `trading_graph.py:106` would need the wrapped
  object injected.
- **Jev**: `post_screen.py` `requests.post` is a **confirmed separate path** and is
  NOT covered by a `get_llm()` wrapper; it needs its own adapter (reserve per attempt,
  explicit retries re-admit). Left as a pending acceptance item.
- **SDK implicit retry**: hidden inside one `.invoke`; a wrapper sees one call, so
  governed runs must keep `max_retries=0`.

## 2. Acceptance cases (test-first where an entry exists today)

| # | Test | Entry under test | Fixture / input | Observation point | Pass condition |
|---|---|---|---|---|---|
| 1 | ample vs zero budget end-to-end | `TradingAgentsGraph.propagate` (or `cli/run.run_analysis`) with a gateway-wrapped quick/deep model + `httpx.MockTransport` | limits ample vs `{tokens:0,calls:0,cost:"0"}` | MockTransport received-request count | ample → ≥1 send, entries reach the workflow; zero → **transport receives 0**, run ends `INCOMPLETE`/denied (no crash) |
| 2 | tool binding spends nothing; bound call admits | `agents/analysts/turn.py:26` via a bound model | allowance for exactly one call; first `bind_tools` then one `bound.invoke` | governor admission count; transport count | binding admits 0; the bound send admits exactly 1; transport 1 |
| 3 | structured 400 → fallback re-admits; one allowance → 1 send | `agents/structured.py invoke_structured_or_freetext` with a gateway-wrapped model | allowance 1; structured returns HTTP 400 | admission calls; transport log | structured admits 1 (send, 400); fallback **re-admits** and is refused (no second send); transport total **1** |
| 4 | sent-then-timeout, token-only bottleneck | gateway-wrapped real send; MockTransport records then raises timeout | first call reserves 1000/1000 tokens (calls/cost spare); then a 1-token request via same governor | first send observable; second `reserve` result; transport total | second request `BudgetDenied`; transport total stays 1; reservation not released pre-settle |
| 5 | SDK retry off; explicit retry re-admits | gateway-wrapped model with `max_retries=0`; an explicit retry helper | one logical retry | admission count; transport count | SDK does NOT resend (transport=1 per attempt); each explicit attempt calls `reserve` again (2 admissions, 2 sends) |

Cases 1–4 have a callable entry **only after** the gateway wrapper exists; until then
they are acceptance conditions, not green tests. Case 5 needs the wrapper plus an
explicit-retry call site (currently none in the chat path; Jev has its own).

## 3. Left as acceptance-only (no callable entry yet)

- **Unified gateway object**: none exists; must be created (see §4 file 1).
- **Jev reserve**: `post_screen.py` calls `requests.post` directly; it must reserve
  around each attempt. No budget-aware Jev path exists today.
- **Zero-budget transport=0**: needs the wrapper; without it the plain model sends.

## 4. Minimal change file list (for the implementation round, not this spec)

1. **New** `src/egta/adapters/model_gateway.py` — a wrapper class over the chat model
   that (a) calls `governor.reserve`, (b) on `BudgetDenied` returns without sending,
   (c) on `Reservation` delegates the send, (d) calls `governor.settle(usage or None)`.
   Install it at `trading_graph.py:79-80` (one line each, behind a config flag so the
   baseline stays comparable).
2. **Edit** `tradingagents/agents/post_screen.py` — reserve around each `requests.post`
   attempt; make explicit retries re-admit; document SDK-retry is off for the chat path.
3. **Edit** `tradingagents/llm_clients/factory.py` — keep `max_retries=0` the default
   for governed runs (explicit `llm_max_retries` disabled) so SDK resends never bypass
   the governor.
4. **Tests** `test/offline/budget/test_gateway.py` + `conftest`/`fakes` additions
   (MockTransport counter, gateway wrapper factory), plus a trace.

The frozen `test/offline/budget/test_reservation_holds.py` and `test_admission.py`
stay byte-identical.

## 5. Questions only E/C can settle

- **E (interface):** is the gateway a `contracts`-level port (injected by `app`) or an
  `adapters/` concrete wrapper installed in `trading_graph`? Also confirm the candidate
  **adapter refusal exception** `BudgetDeniedError` (carries `reason_code`,
  `"BUDGET_DENIED"`), separate from #45's `BudgetDenied` return dataclass.
- **E (status):** what final workflow status does the zero-budget path report
  (`INCOMPLETE` vs a dedicated governor status)? This is distinct from the adapter's
  unit-level refusal (`BudgetDeniedError`): the adapter refuses a single send; the
  workflow status describes the whole run.
- **C (context/deliberation boundary):** does the deliberation layer ever call a model
  other than through the shared `get_llm()` object (e.g. its own summarizer)? If so,
  that path must go through the same gateway.
- **E/C (Jev):** is Jev enabled in any governed run? If yes, its direct HTTP path must
  reserve; if it is out of scope, we document it as a non-governed optional feature.
