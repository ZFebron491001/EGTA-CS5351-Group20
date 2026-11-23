"""Offline spec for the FR-02 budget-gateway ADAPTER (candidate interface).

Test-first spec for the adapter that makes a real model path pay budget: the
candidate ``BudgetedModelGateway`` (to live in ``src/egta/adapters/model_gateway.py``).
The adapter entry and its refusal exception ``BudgetDeniedError`` are CANDIDATE
interfaces pending E/C sign-off (see ``docs/req/spec-FR-02-gateway.md``); the tests
call them so the future production code itself triggers admission and the send.

Lives under ``test/offline/integration`` (NOT ``test/offline/budget``) so the frozen
#22 governor suite keeps collecting exactly its four approved cases.

Every test uses ONE ``events`` list. A spy around the real governor's ``reserve``
appends ``("reserve", <outcome>)``; the MockTransport handler appends ``("send", <kind>)``.
So admission and transport are observed in a single order — not just a send count.

Reuses the real ``NormalizedChatOpenAI`` + ``httpx.MockTransport`` (+ fictional key),
the real Pydantic schema pattern, and the project's original
``invoke_structured_or_freetext`` / ``prompt | bound`` chain.

RED by design: ``egta.adapters.model_gateway`` (and, until #45 merges, ``egta.budget``)
do not exist, so each test fails at a lazy import inside its body — not at collection.

Not covered here (acceptance-only): final workflow status on exhaustion, C's
independent model calls, Jev's direct-HTTP path, explicit-retry accounting.
"""

from __future__ import annotations

import httpx
import pytest
from fakes_gateway import (
    chat_ok_response,
    make_real_llm,
    make_spy,
    one_call_spec,
    request_kind,
)
from pydantic import BaseModel

pytestmark = pytest.mark.spec


class _Report(BaseModel):
    """Real Pydantic schema for the structured path (never a plain class)."""

    summary: str


def _gateway(governor, llm, call_spec):
    from egta.adapters.model_gateway import BudgetedModelGateway

    return BudgetedModelGateway(governor=governor, llm=llm, call_spec=call_spec)


def _denied_error_type():
    from egta.adapters.model_gateway import BudgetDeniedError

    return BudgetDeniedError


# ---------------------------------------------------------------------------
# 1a. Ample budget: reserve -> transport (one send).
# ---------------------------------------------------------------------------


def test_ample_budget_reserve_then_send(governor_factory):
    events: list[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append(("send", request_kind(request)))
        return chat_ok_response("hi")

    gov = governor_factory().governor
    spy = make_spy(gov, events)
    llm = make_real_llm(handler)
    _gateway(spy, llm, one_call_spec()).invoke("hello")

    assert events == [("reserve", "Reservation"), ("send", "chat")], events


# ---------------------------------------------------------------------------
# 1b. Zero budget: reserve, transport 0, refusal via the candidate exception.
# ---------------------------------------------------------------------------


def test_zero_budget_reserve_refused_transport_zero(governor_factory):
    events: list[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append(("send", request_kind(request)))
        return chat_ok_response("hi")

    gov = governor_factory(limits={"max_total_tokens": 0, "max_calls": 0, "max_cost_usd": "0"}).governor
    spy = make_spy(gov, events)
    llm = make_real_llm(handler)
    gw = _gateway(spy, llm, one_call_spec())

    with pytest.raises(_denied_error_type()) as ei:
        gw.invoke("hello")
    assert ei.value.reason_code == "BUDGET_DENIED"
    assert events == [("reserve", "BudgetDenied")], events  # no send


# ---------------------------------------------------------------------------
# 2. bind_tools admits nothing; goes through the REAL `prompt | bound` chain;
#    the bound send admits once and the request carries the tool.
# ---------------------------------------------------------------------------


def test_bind_tools_admits_nothing_then_bound_chain_admits_once(governor_factory):
    events: list[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        events.append(("send", request_kind(request)))
        return chat_ok_response("hi")

    gov = governor_factory().governor
    spy = make_spy(gov, events)
    llm = make_real_llm(handler)
    gw = _gateway(spy, llm, one_call_spec())

    bound = gw.bind_tools(
        [{"type": "function", "function": {"name": "get_stock_data", "parameters": {"type": "object"}}}]
    )
    # Binding alone: nothing admitted, nothing sent.
    assert events == [], f"bind_tools must not reserve or send, got {events}"

    # The production analyst pattern: prompt | llm.bind_tools(tools), then .invoke.
    from langchain_core.prompts import ChatPromptTemplate

    chain = ChatPromptTemplate.from_messages([("human", "{q}")]) | bound
    chain.invoke({"q": "hello"})

    # Exactly one admission then one send, and the send carried tools.
    assert events == [("reserve", "Reservation"), ("send", "structured")], events


# ---------------------------------------------------------------------------
# 3. Real invoke_structured_or_freetext: structured 400 -> fallback RE-ADMITS.
#    Allowance 1: two admission attempts, transport only the first send.
# ---------------------------------------------------------------------------


def test_structured_400_fallback_readmits_allowance_one_transport_one(governor_factory):
    events: list[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        kind = request_kind(request)
        events.append(("send", kind))
        if kind == "structured":
            return httpx.Response(400, json={"error": {"message": "simulated refusal"}})
        return chat_ok_response("fallback")

    # Allowance for exactly one call. Reserve enough tokens (8) to cover the 2-token reply.
    gov = governor_factory(limits={"max_total_tokens": 10_000, "max_calls": 1, "max_cost_usd": "1.00"}).governor
    spy = make_spy(gov, events)
    llm = make_real_llm(handler)
    gw = _gateway(spy, llm, one_call_spec())

    structured = gw.with_structured_output(_Report)

    from tradingagents.agents.structured import invoke_structured_or_freetext

    with pytest.raises(_denied_error_type()) as ei:
        invoke_structured_or_freetext(structured, gw, "prompt", lambda r: r.summary, "probe")
    assert ei.value.reason_code == "BUDGET_DENIED"

    # Order: admit structured -> send structured(400) -> admit fallback (refused).
    # Transport saw only the first (structured) send.
    assert events == [
        ("reserve", "Reservation"),
        ("send", "structured"),
        ("reserve", "BudgetDenied"),
    ], events
