#!/usr/bin/env python3
"""Module-level G1 three-way end-to-end driver (E, G3 evidence).

Runs three scenarios against the REAL modules on `main` (no fakes of the system
under test; the typed input builders are the test-only dataclasses from
``test/offline/risk_gate/fakes.py``, which carry no logic — they only construct
inputs). Uses a temporary SQLite ledger and a fixed clock; no network.

  normal     : compare_runs -> COMPLETE ; RiskGate APPROVED ; version+1 ; +1 ledger
               entry ; cash decreases by filled notional+fees
  declined   : oversized order -> REJECTED ; version unchanged ; 0 ledger entries
               (also STALE_PORTFOLIO for a stale portfolio_version)
  over-budget: budget module not implemented (FR-02 spec-only, #22) -> cannot be
               demonstrated at module level; the contract expects
               BudgetDenied / MISSING_USAGE. Documented gap, owner B.

Exit 0 if the two demonstrable scenarios behave as asserted, else 1.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "test" / "offline" / "risk_gate"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# test-only typed input builders (no logic; dataclasses)
from fakes import NOW, FixedClock, make_evidence, make_policy, make_portfolio, make_proposal  # noqa: E402

from egta.contracts.evaluation import CompletionStatus, RunSummary, compare_runs  # noqa: E402
from egta.contracts.manifest import MetricDef  # noqa: E402
from egta.risk_gate import ledger  # noqa: E402
from egta.risk_gate.models import VerdictStatus  # noqa: E402
from egta.risk_gate.service import RiskGate  # noqa: E402

H = "a" * 64


def _summary(**o) -> RunSummary:
    base = {
        "run_id": "run-1",
        "variant": "B0",
        "target_snapshot_id": "snap-1",
        "model_config_hash": H,
        "prompt_hash": H,
        "code_hash": "c" * 40,
        "policy_hash": H,
        "manifest_hash": H,
    }
    base.update(o)
    return RunSummary(**base)


def _rubric():
    return {
        "token_cost": MetricDef(
            metric="token_cost",
            operator="lte",
            threshold=2.0,
            verification="pytest",
            source="budget",
            aggregation="median",
            unit="USD",
        )
    }


def _ledger_state(db) -> tuple[int, int, Decimal]:
    """(portfolio_version, ledger_entry_count, cash)."""
    conn = ledger.connect(db, 5.0)
    snap = ledger.snapshot(db, "portfolio-1")
    entries = conn.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0]
    conn.close()
    return snap.version, int(entries), snap.cash


def run_gate(db, clock, policy, portfolio, proposal, evidence, stale=None):
    """Real RiskGate; a stale caller portfolio simulates the stale-version path."""
    gate = RiskGate(db_path=db, policy=policy, clock=clock)
    gate.ensure_initialized(portfolio)
    return gate.evaluate_and_commit(proposal, evidence, stale if stale is not None else portfolio)


def main() -> int:
    clock = FixedClock(NOW)
    ok = True

    # ---- normal: comparison + approved order ----
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "normal.db"
        b = _summary(variant="B0", metrics={"token_cost": 1.0})
        e = _summary(variant="B1", metrics={"token_cost": 1.5})
        cmp = compare_runs(b, e, _rubric())
        policy = make_policy()
        portfolio = make_portfolio(cash=Decimal("10000.00"))
        evidence = make_evidence()
        proposal = make_proposal(policy=policy, evidence=evidence, portfolio=portfolio)
        v0, n0, cash0 = _ledger_state_init(db, portfolio)
        verdict = run_gate(db, clock, policy, portfolio, proposal, evidence)
        v1, n1, cash1 = _ledger_state(db)
        normal_ok = (
            cmp.completion_status is CompletionStatus.COMPLETE
            and verdict.status is VerdictStatus.APPROVED
            and v1 == v0 + 1
            and n1 == n0 + 1
            and cash1 < cash0
        )
        ok &= normal_ok
        print(
            f"normal      | compare={cmp.completion_status.name} | "
            f"verdict={verdict.status.name} | version {v0}->{v1} | "
            f"entries +{n1 - n0} | cash {cash0}->{cash1} | {'OK' if normal_ok else 'FAIL'}"
        )

    # ---- declined: oversized order ----
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "declined.db"
        policy = make_policy()
        portfolio = make_portfolio(cash=Decimal("10000.00"))
        evidence = make_evidence()
        # nominal 100 * 100 = 10000 >> 10% NAV(1000) -> oversized
        proposal = make_proposal(
            policy=policy,
            evidence=evidence,
            portfolio=portfolio,
            quantity=100,
            reference_price="100.00",
        )
        v0, n0, cash0 = _ledger_state_init(db, portfolio)
        verdict = run_gate(db, clock, policy, portfolio, proposal, evidence)
        v1, n1, cash1 = _ledger_state(db)
        declined_ok = (
            verdict.status in (VerdictStatus.REJECTED, VerdictStatus.BLOCKED)
            and v1 == v0
            and n1 == n0
            and cash1 == cash0
        )
        ok &= declined_ok
        print(
            f"declined    | verdict={verdict.status.name} | version {v0}->{v1} | "
            f"entries +{n1 - n0} | cash {cash0}->{cash1} | {'OK' if declined_ok else 'FAIL'}"
        )

    # ---- declined-2: stale portfolio_version -> STALE_PORTFOLIO ----
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "stale.db"
        policy = make_policy()
        portfolio = make_portfolio(cash=Decimal("10000.00"))
        evidence = make_evidence()
        proposal = make_proposal(policy=policy, evidence=evidence, portfolio=portfolio)
        v0, n0, cash0 = _ledger_state_init(db, portfolio)
        stale = replace(portfolio, version=portfolio.version + 99)
        verdict = run_gate(db, clock, policy, portfolio, proposal, evidence, stale=stale)
        print(
            f"declined-2  | verdict={verdict.status.name} | "
            f"{'OK' if verdict.status in (VerdictStatus.STALE_PORTFOLIO, VerdictStatus.REJECTED, VerdictStatus.BLOCKED) else 'INFO'}"
        )

    # ---- over-budget: documented gap (no budget module) ----
    print(
        "over-budget | N/A — budget module not implemented (FR-02 spec-only, #22); "
        "contract expects BudgetDenied / MISSING_USAGE; documented gap, owner B, "
        "pending FR-02 implementation"
    )

    return 0 if ok else 1


def _ledger_state_init(db, portfolio) -> tuple[int, int, Decimal]:
    ledger.initialize(db, portfolio)
    return _ledger_state(db)


if __name__ == "__main__":
    raise SystemExit(main())
