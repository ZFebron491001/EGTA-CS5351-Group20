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

## 4. Left as acceptance-only (no callable entry yet)

- **Unified gateway object**: none exists; must be created (see §4 file 1).
- **Jev reserve**: `post_screen.py` calls `requests.post` directly; it must reserve
  around each attempt. No budget-aware Jev path exists today.
- **Zero-budget transport=0**: needs the wrapper; without it the plain model sends.

## 5. Runner / CLI acceptance (unified offline entry)

A minimal offline runner wires the REAL modules and fakes **only the model**:

```
egta.app.runner.run_offline(*, governor, provider, limits, evidence, proposal,
                            portfolio, clock, db_path, audit_path) -> RunResult
python -m egta --offline --db-path <p> --audit-path <p>                 # CLI form
```

The runner owns the wiring; tests read results back INDEPENDENTLY (real ledger
connection via `egta.risk_gate.ledger`, real `SqliteAuditReader`), and never trust
the runner's own deltas. The audit is queried by a **known run_id taken from the
input proposal / public run params** (`proposal.run_id`, e.g. `"run-1"`), and the
runner must return that SAME `run_id`. Candidate `RunResult` fields used by the
tests: `run_id`, `verdict` (real `RiskVerdict`), `evidence_pack_hash`, `reason_code`.
The CLI exposes `egta.__main__.main(argv) -> int` and dispatches to
`egta.app.runner.run_offline` with the parsed `db_path`/`audit_path`.

| # | Path | Entry | Fake | Real modules under test | Pass condition |
|---|---|---|---|---|---|
| R1 | normal | `run_offline` | provider reply; ONE shared event list | real governor (admit before send), real RiskGate APPROVED, real ledger, real audit | same sequence `[("reserve","Reservation"),("send","chat")]`; verdict `APPROVED`; independent ledger read = +1 entry & version+1; `result.run_id == proposal.run_id`; audit read by that run_id is non-empty and all share it; `evidence_pack_hash == pack.pack_hash` |
| R2 | risk-reject | `run_offline` | provider | real RiskGate, real ledger, real audit | known reject fixture (insufficient cash) → exactly `REJECTED` with `POLICY_REJECTED`; `result.run_id == proposal.run_id`; independent ledger read unchanged before/after; audit read by that run_id carries the reason |
| R3 | budget-deny | `run_offline` | provider must receive **0** | real governor zero limits, real ledger, real audit | provider receives 0 calls; `reason_code == ReasonCode.BUDGET_DENIED`; `result.run_id == proposal.run_id`; independent ledger read unchanged; audit read by that run_id has a **BUDGET_DENIED** event. **Workflow terminal status is NOT asserted** — explicit spec item pending E (§8). |
| R4 | CLI | `python -m egta` | test spy on `run_offline` | `egta.__main__.main` | public CLI with `--offline --db-path --audit-path` dispatches to `run_offline` with those params; exit code 0 |

The three module paths use the real `BudgetGovernor` (#45), the real `RiskGate`
(D's FR-04 module) and the real `SqliteAuditSink`/`SqliteAuditReader`; faking any of
them would let a real bypass pass, which is exactly what this suite guards against.
Ledger deltas and audit records are read back INDEPENDENTLY (a fresh ledger
connection and the real audit reader), not from the runner's own return values.

**C scope (pending):** the deliberation module is absent, so a FIXED proposal
fixture (`test/offline/risk_gate/fakes.py` builders) stands in for C's output. This
covers budget/risk/audit wiring; full deliberation integration stays pending.

## 6. Production call inventory and integration status

Every place a request can leave the process, and whether it is covered by a tested
entry or still needs integration verification:

| Entry | Where | Send path | Status |
|---|---|---|---|
| `propagate()` | `trading_graph.py:167` → `_run_graph` → `graph.invoke` | chat models from `get_llm()` | **needs integration**: gateway wrapper at `get_llm()` (candidate, §1) + runner test R1 generalised to the real graph |
| CLI | `cli/run.py` → `TradingAgentsGraph(...)` → `stream_run` | same chat models | **needs integration**: R4 pins `python -m egta` entry; full CLI-over-graph e2e pending |
| Tool binding | `agents/analysts/turn.py:26` `(prompt \| llm.bind_tools(tools)).invoke` | chat model (derived) | **spec, RED (adapter)**: case 2 — binding admits 0, bound send admits once |
| Structured output | `agents/structured.py:69` `structured_llm.invoke` | chat model (derived) | **spec, RED (adapter)**: case 3 first send |
| Structured→free-text fallback | `agents/structured.py:95` `plain_llm.invoke` | chat model | **spec, RED (adapter)**: case 3 — fallback RE-ADMITS, allowance 1 → refused |
| Reflection | `memory/reflection.py:63` `self.quick_thinking_llm.invoke` | same quick model | **needs integration**: wrap the injected quick model |
| Jev direct HTTP | `agents/post_screen.py:68` `requests.post` + retry loop | **`requests` directly (bypass)** | **needs integration**: must reserve per attempt; own adapter |
| SDK implicit retry | `llm_clients/factory.py:123-125` `max_retries` | SDK inside one `.invoke` | **needs integration**: governed runs keep `max_retries=0` |
| Explicit retry | (no chat-path call site today) | new attempt | **needs integration**: each attempt re-admits (R5 acceptance) |

**Sent-then-timeout (unknown usage keeps the reservation held):** the governor
already holds an unsettled reservation (#22 frozen case). The end-to-end proof — a
real send that times out before usage returns, leaving the hold in place — is an
**integration acceptance item** (not yet a green test): the adapter must call
`settle(id, None)` on timeout, keeping the reservation held. Each **explicit retry**
must call `reserve` again (a new reservation), never reuse the timed-out hold.

## 7. Minimal change file list (for the implementation round, not this spec)

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
4. **New** `src/egta/app/runner.py` — `run_offline(...)` wiring evidence → gateway
   (budget) → provider (fake in tests) → fixed proposal → real `RiskGate` → ledger →
   audit; returns a `RunResult`. **New** `src/egta/__main__.py` — `python -m egta`
   with an `--offline` flag selecting the fake-provider runner.
5. **Tests** `test/offline/integration/test_gateway.py` (4 adapter cases) +
   `test_runner_cli.py` (4 runner/CLI cases) + `conftest.py`/`fakes_gateway.py`;
   trace + acceptance table. Lives in `test/offline/integration/` (NOT
   `test/offline/budget/`) so the frozen #22 governor suite keeps collecting exactly
   its four approved cases.

The frozen `test/offline/budget/test_reservation_holds.py`, `test_admission.py`,
`conftest.py` and `fakes.py` stay byte-identical to #22.

## 8. Questions only E/C can settle

- **E (CI selector / routing):** the integration suite lives in
  `test/offline/integration/` to protect the #22 governor count. Should CI add a
  per-suite gate for it (a new `test-hash-FR-02-integration.txt` `actual_cases`
  record), or fold it into check-permissions `build-b` routing only? `check-permissions`
  already maps `src/egta/budget/`, `src/egta/adapters/`, `src/egta/app/`,
  `test/offline/budget/` → `build-b`; `test/offline/integration/` needs the same
  routing or a new selector. Record the implementation applicability condition
  (RED lands on `egta.adapters` / `egta.app`, both unbuilt) and the approval-record
  route (B's FR-02 budget record vs a new integration record) in the merged spec.

- **E (interface):** is the gateway a `contracts`-level port (injected by `app`) or an
  `adapters/` concrete wrapper installed in `trading_graph`? Also confirm the candidate
  **adapter refusal exception** `BudgetDeniedError` (carries `reason_code`,
  `"BUDGET_DENIED"`), separate from #45's `BudgetDenied` return dataclass.
- **E (status) — explicit spec item:** what final workflow status does the zero-budget
  path report (`INCOMPLETE` vs a dedicated governor status)? This is an open decision:
  the R3 test deliberately does NOT assert any `CompletionStatus` membership; the
  assertion is deferred to a spec item that flips on E's ruling. It is distinct from
  the adapter's unit-level refusal (`BudgetDeniedError`): the adapter refuses a single
  send; the workflow status describes the whole run.
- **C (context/deliberation boundary):** does the deliberation layer ever call a model
  other than through the shared `get_llm()` object (e.g. its own summarizer)? If so,
  that path must go through the same gateway.
- **E/C (Jev):** is Jev enabled in any governed run? If yes, its direct HTTP path must
  reserve; if it is out of scope, we document it as a non-governed optional feature.
