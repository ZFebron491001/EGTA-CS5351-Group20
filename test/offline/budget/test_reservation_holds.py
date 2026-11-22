"""Offline spec for FR-02 / INV-03: an outstanding token reservation is not
released early when usage is unknown, or when a reservation has not been settled.

The single error this spec is built to catch: a governor that REFUNDS (fully or
partly) the held token reservation on unknown usage, or before settle, so the next
request for the same tokens is wrongly granted.

Every scenario uses the SAME limits and the SAME first call (which reserves the
whole 1000-token axis) and the SAME tiny 1-token follow-up. The three scenarios
differ ONLY in the settle condition, so an early refund of even a few tokens is
detectable:

    unknown usage        -> follow-up must be BudgetDenied
    outstanding/unsettled -> follow-up must be BudgetDenied
    known 100 used (900 free) -> follow-up must be a Reservation

Focus is the GOVERNOR layer, using only the two frozen entry points (§5.1):

    BudgetGovernor.reserve(call_spec) -> Reservation | BudgetDenied
    BudgetGovernor.settle(reservation_id, actual_usage_or_unknown) -> BudgetState

A refusal is asserted ONLY as the contract type ``BudgetDenied`` (not ``None`` or a
truthiness guess); a grant is asserted POSITIVELY as the contract type
``Reservation`` (so ``None`` or a wrong value cannot pass as a grant either).

RED by design: ``egta.budget`` is absent on this branch, so each test fails when it
calls ``governor_factory()`` (lazy import). No fake governor, no xfail/skip.

Not covered here (tracked in the trace): the real-gateway "request sent, then timed
out, transport shows no new request" path, durable restart recovery, and concurrency.
"""

from __future__ import annotations

import pytest
from fakes import FOLLOWUP_ONE_TOKEN, FULL_TOKEN_CALL, LOW_KNOWN_USAGE

pytestmark = pytest.mark.spec


def _reservation_id(reservation) -> object:
    """The reservation's public id. Attribute name is a CANDIDATE (see trace)."""
    return reservation.reservation_id


def _is_reservation(result) -> bool:
    """Contract: a grant is the ``Reservation`` type (not ``None``)."""
    from egta.budget import Reservation

    return isinstance(result, Reservation)


def _is_denied(result) -> bool:
    """Contract: a refusal is the ``BudgetDenied`` type (not ``None``)."""
    from egta.budget import BudgetDenied

    return isinstance(result, BudgetDenied)


# ---------------------------------------------------------------------------
# Scenario 1: settle(unknown) must NOT release the held token reservation, so a
#             1-token follow-up is still denied.
# ---------------------------------------------------------------------------


def test_unknown_usage_holds_token_reservation_denies_one_token_followup(governor_factory):
    gov = governor_factory().governor

    # First call reserves the whole 1000-token axis (calls/cost have spare room).
    reservation = gov.reserve(FULL_TOKEN_CALL)
    rid = _reservation_id(reservation)

    # Usage comes back UNKNOWN (not a numeric amount). The 1000 tokens must stay held.
    gov.settle(rid, actual_usage_or_unknown=None)

    # Only 1 token is asked for, yet 0 are free if the hold is correct: this must be
    # refused with BudgetDenied. A governor that refunded even a few tokens on unknown
    # usage would grant it — and the test fails. That is the bug we want to catch.
    assert _is_denied(gov.reserve(FOLLOWUP_ONE_TOKEN))


# ---------------------------------------------------------------------------
# Scenario 2: an outstanding (reserved-but-not-yet-settled) reservation must not be
#             reusable. A 1-token follow-up while it is outstanding is denied.
# ---------------------------------------------------------------------------


def test_outstanding_unsettled_reservation_denies_one_token_followup(governor_factory):
    gov = governor_factory().governor

    # Reserve the whole token axis; do NOT settle (the call is still outstanding).
    reservation = gov.reserve(FULL_TOKEN_CALL)
    assert _reservation_id(reservation) is not None

    # While outstanding, all 1000 tokens are still held: a 1-token follow-up is
    # refused. A governor that lets an unsettled reservation be reused fails here.
    assert _is_denied(gov.reserve(FOLLOWUP_ONE_TOKEN))


# ---------------------------------------------------------------------------
# Control: known low usage DOES release tokens, so the SAME 1-token follow-up is
#          granted. This proves the denials above are about the held tokens, not a
#          governor that refuses everything.
# ---------------------------------------------------------------------------


def test_known_low_usage_releases_tokens_grants_one_token_followup(governor_factory):
    """Same limits: knowing 100 tokens were used refunds 900, leaving 900 free, so
    the 1-token follow-up fits and must be granted (a ``Reservation``)."""
    gov = governor_factory().governor

    reservation = gov.reserve(FULL_TOKEN_CALL)
    rid = _reservation_id(reservation)

    # Known low usage (100 tokens) settles the call; 900 tokens become free.
    gov.settle(rid, actual_usage_or_unknown=dict(LOW_KNOWN_USAGE))

    # 1 <= 900 free tokens: the follow-up must be a Reservation (positive assertion).
    assert _is_reservation(gov.reserve(FOLLOWUP_ONE_TOKEN))
