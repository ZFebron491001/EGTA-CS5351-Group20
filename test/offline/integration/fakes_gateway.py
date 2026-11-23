"""Test-only builders for the FR-02 model-gateway adapter spec.

Not production code and not a frozen contract. The adapter ``BudgetedModelGateway``
(to live in ``src/egta/adapters/model_gateway.py``) and its refusal exception
``BudgetDeniedError`` are CANDIDATE interfaces (see ``docs/req/spec-FR-02-gateway.md``).
Tests import them lazily so collection stays green while they are unbuilt.

Reuses the project's real ``NormalizedChatOpenAI`` and ``httpx.MockTransport``; a
fictional API key is used and no network leaves the box.
"""

from __future__ import annotations

from typing import Any

import httpx

FICTIONAL_KEY = "sk-TEST-not-a-real-key-000000000000"


def make_mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)


def make_real_llm(handler):
    """The project's real client (NormalizedChatOpenAI) over a MockTransport."""
    from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI

    return NormalizedChatOpenAI(
        model="gpt-4.1",
        api_key=FICTIONAL_KEY,
        base_url="http://mock.local/v1",
        http_client=make_mock_client(handler),
        max_retries=0,
    )


def chat_ok_response(text: str = "ok", total_tokens: int = 2) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "c1", "object": "chat.completion", "created": 0, "model": "gpt-4.1",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": total_tokens - 1, "completion_tokens": 1,
                      "total_tokens": total_tokens},
        },
    )


def request_kind(request: httpx.Request) -> str:
    """Classify a MockTransport request by its JSON body.

    A structured/function-calling request carries ``tools``; a plain chat does not.
    Parsing the body (not the URL) is what distinguishes them in these tests.
    """
    import json

    body = json.loads(request.content.decode() or "{}")
    return "structured" if body.get("tools") else "chat"


def one_call_spec(**over: Any) -> dict[str, Any]:
    """A minimal per-call ask. Default reserves enough tokens for a tiny reply."""
    base = {"max_tokens": 8, "max_calls": 1, "max_cost_usd": "0.01"}
    base.update(over)
    return base


def make_spy(governor, events: list[tuple]):
    """Wrap a real governor so each reserve is recorded, then the real one runs.

    Appends ``("reserve", outcome)`` to the SAME ``events`` list the transport
    handler appends its sends to, so admission and transport share one order.
    Returns a lightweight governor proxy that still delegates ``settle``.
    """

    class _SpyGovernor:
        def __init__(self, real):
            self._real = real

        def reserve(self, call_spec):
            result = self._real.reserve(call_spec)
            name = type(result).__name__
            events.append(("reserve", name))
            return result

        def settle(self, reservation_id, actual_usage_or_unknown):
            return self._real.settle(reservation_id, actual_usage_or_unknown)

    return _SpyGovernor(governor)
