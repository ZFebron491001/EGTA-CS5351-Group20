"""Test-only builders for the offline FR-02 / INV-03 budget-reservation spec.

Not production code and not a frozen contract. Only the two entry-point
signatures are frozen by the plan (§5.1):

    BudgetGovernor.reserve(call_spec) -> Reservation | BudgetDenied
    BudgetGovernor.settle(reservation_id, actual_usage_or_unknown) -> BudgetState

Everything else used below (how the governor is constructed, the attributes of
``Reservation``/``BudgetState``, and how "unknown usage" is encoded) is a
CANDIDATE interface proposed for B/E review — see
``docs/req/trace-FR-02-budget-reservation.md`` "Candidate interface (needs B/E)".
These builders only give the behavioural tests a minimal, documented input so a
failing implementation is caught. Stdlib only; no ``src/`` import here.

Design note on the numbers (the point of the whole spec): only ONE budget axis is
the bottleneck. The other two axes have spare room, so a governor that wrongly
releases the held token reservation would let the second request through. If all
three axes were exhausted, a second request could be denied for the wrong reason
and the test would pass despite the bug.
"""

from __future__ import annotations

from typing import Any

# --- Budget limits (token is the ONLY tight axis) --------------------------
# tokens: room for exactly ONE 1000-token call.
# calls : room for several calls (2 is enough to send a second one).
# cost  : room for several calls at the tiny per-call cost.
BUDGET_LIMITS: dict[str, Any] = {
    "max_total_tokens": 1000,
    "max_calls": 5,
    "max_cost_usd": "1.00",
}

# One call asks for 1000 tokens; that consumes the whole token axis.
FULL_TOKEN_CALL: dict[str, Any] = {
    "max_tokens": 1000,
    "max_calls": 1,
    "max_cost_usd": "0.01",
}

# The single follow-up asked in every scenario: just 1 token. It is tiny on
# purpose — with 900 tokens free (known-low-usage case) it fits, and with 0 free
# (unknown / outstanding) it is the smallest request that a wrongly-refunded hold
# would let slip through. Calls and cost stay far from their limits.
FOLLOWUP_ONE_TOKEN: dict[str, Any] = {
    "max_tokens": 1,
    "max_calls": 1,
    "max_cost_usd": "0.01",
}

# Known low ACTUAL usage for the control: the first call reserved 1000 tokens but
# used only 100, so ``settle`` releases 900 back. The same 1-token follow-up is then
# granted. The three scenarios differ ONLY in the settle condition, so a partial
# early refund (e.g. refunding <1000 but >? on unknown/outstanding) is detectable.
LOW_KNOWN_USAGE: dict[str, Any] = {"tokens": 100}


def base_limits() -> dict[str, Any]:
    return dict(BUDGET_LIMITS)
