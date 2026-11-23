"""Offline spec for the unified RUNNER / CLI integration of FR-02 (candidate).

Test-first spec for a minimal end-to-end runner that wires the real modules:
evidence fixture -> model gateway (budget admission) -> provider (FAKED) ->
deliberation proposal (FIXED fixture, C pending) -> real RiskGate -> real paper
ledger -> real audit. Only the MODEL/provider is faked; budget, risk and audit use
their REAL implementations on ``main`` (#45 governor, the RiskGate (D, FR-04),
E's ``SqliteAuditSink``/``SqliteAuditReader``).

Candidate entry points (pending E sign-off; see ``docs/req/spec-FR-02-gateway.md``
§"Runner / CLI acceptance")::

    egta.app.runner.run_offline(*, governor, provider, limits, evidence, proposal,
                                portfolio, clock, db_path, audit_path) -> RunResult
    python -m egta --offline --db-path ... --audit-path ...                (CLI form)

The tests do NOT fake the governor, the risk gate or the audit sink: faking them
would let a real bypass pass (the exact failure this spec guards). They read the
results back INDEPENDENTLY (real ledger connection + real ``SqliteAuditReader``).

Covered paths:
  1. normal      : admit precedes send (one shared event sequence); evidence
                   traceable; compliant proposal through the REAL RiskGate; ledger
                   delta read independently; audit read by the input proposal's
                   known run_id and the runner returns the same run_id;
                   result.evidence_pack_hash equals the real hash of the input pack.
  2. risk-reject : a KNOWN reject fixture from the risk_gate suite; assert the exact
                   verdict + reason; read the rejection event by the known run_id and
                   the runner returns the same run_id; ledger unchanged before/after.
  3. budget-deny : provider/MockTransport receives 0; ledger unchanged; shared
                   ``BUDGET_DENIED``; audit read by the known run_id contains a
                   BUDGET_DENIED event and the runner returns the same run_id.
                   Workflow terminal status is NOT asserted — explicit item pending E.
  4. CLI         : the public CLI entry with real offline args calls the runner; a
                   test spy observes the dispatch; assert params/exit code.

RED by design: ``egta.app.runner`` / ``egta.__main__`` do not exist, so each test
fails at a lazy import inside its body — not at collection. Business assertions
execute 0 while the runner is unbuilt.

Scope note (C pending): the deliberation module is absent, so a FIXED proposal
fixture stands in for C's output. That covers budget/risk/audit wiring, NOT a full
deliberation integration (listed as pending in the trace).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.spec


# ---------------------------------------------------------------------------
# Lazy accessors (so collection stays green; failures land inside test bodies)
# ---------------------------------------------------------------------------


def _runner():
    from egta.app.runner import run_offline

    return run_offline


def _reason_code():
    from egta.contracts.events import ReasonCode

    return ReasonCode


def _risk_fakes():
    """Fixed evidence/proposal/portfolio builders from the REAL risk_gate suite."""
    import sys
    from pathlib import Path

    rg = Path(__file__).resolve().parents[1] / "risk_gate"
    if str(rg) not in sys.path:
        sys.path.insert(0, str(rg))
    import fakes  # test-only typed builders (no logic)

    return fakes


def _audit_reader(conn):
    from egta.evaluation.sink import SqliteAuditReader

    return SqliteAuditReader(conn)


def _audit_conn(audit_path):
    import sqlite3

    return sqlite3.connect(audit_path)


def _ledger_state(db_path):
    """Independent read of (portfolio_version, ledger_entry_count) via the real ledger."""
    from egta.risk_gate import ledger

    conn = ledger.connect(db_path, 5.0)
    try:
        row = conn.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()
        count = int(row[0])
        snap = ledger.read_portfolio(conn, "portfolio-1")
        return snap.version, count
    finally:
        conn.close()


def _ledger_state_init(db_path, portfolio):
    """Seed the real paper ledger with this portfolio, then read its starting state."""
    from egta.risk_gate import ledger

    ledger.initialize(db_path, portfolio)
    return _ledger_state(db_path)


def _pack_hash(evidence) -> str:
    """The real hash of the input pack object (``pack_hash`` attribute)."""
    return evidence.pack_hash


# ---------------------------------------------------------------------------
# 1. Normal path — admission-before-send, real risk commit, independent audit.
# ---------------------------------------------------------------------------


def test_runner_normal_admit_before_send_real_risk_and_audit(governor_factory, tmp_path):
    fakes = _risk_fakes()
    db_path = tmp_path / "ledger.db"
    audit_path = tmp_path / "audit.db"

    # One shared event list: governor spy and fake provider append to it in order.
    events: list[tuple] = []
    real_gov = governor_factory(
        limits={"max_total_tokens": 10000, "max_calls": 5, "max_cost_usd": "1.00"}
    ).governor

    class _SpyGovernor:
        def reserve(self, call_spec):
            result = real_gov.reserve(call_spec)
            events.append(("reserve", type(result).__name__))
            return result

        def settle(self, reservation_id, usage):
            return real_gov.settle(reservation_id, usage)

    def fake_provider(prompt: str):
        events.append(("send", "chat"))
        return fakes.canonical_bytes({"reply": "ok"})

    policy = fakes.base_policy()
    portfolio = fakes.base_portfolio()
    evidence = fakes.base_evidence_pack()
    proposal = fakes.make_proposal(policy=policy, evidence=evidence, portfolio=portfolio)
    known_run_id = proposal.run_id  # "run-1" — carried by the input proposal

    result = _runner()(
        governor=_SpyGovernor(),
        provider=fake_provider,
        limits={"max_total_tokens": 10000, "max_calls": 5, "max_cost_usd": "1.00"},
        evidence=evidence,
        proposal=proposal,
        portfolio=portfolio,
        clock=fakes.FixedClock(fakes.NOW),
        db_path=db_path,
        audit_path=audit_path,
    )

    # (a) The SAME sequence: admission granted BEFORE the send; exactly one send.
    assert events == [("reserve", "Reservation"), ("send", "chat")], events

    # (b) Real risk gate approved.
    assert result.verdict.status.value == "APPROVED"

    # (c) Independent ledger read: +1 entry and version advanced by the real gate.
    version_after, entries_after = _ledger_state(db_path)
    assert entries_after == 1
    assert version_after == int(portfolio.version) + 1

    # (d) The runner returns the SAME known run_id as the input.
    assert result.run_id == known_run_id

    # (e) Independent audit read by the known run_id: non-empty, all for that run.
    conn = _audit_conn(audit_path)
    try:
        audit_events = _audit_reader(conn).read(known_run_id)
    finally:
        conn.close()
    assert audit_events, "audit must contain at least one event for the run"
    assert all(e.run_id == known_run_id for e in audit_events)

    # (f) The result's evidence pack hash equals the REAL hash of the input pack.
    assert result.evidence_pack_hash == _pack_hash(evidence)


# ---------------------------------------------------------------------------
# 2. Risk-reject — known reject fixture, exact verdict/reason, audit, no ledger.
# ---------------------------------------------------------------------------


def test_runner_risk_reject_ledger_unchanged_audit_reason(governor_factory, tmp_path):
    fakes = _risk_fakes()
    db_path = tmp_path / "ledger.db"
    audit_path = tmp_path / "audit.db"
    gov = governor_factory().governor

    def fake_provider(prompt: str):
        return fakes.canonical_bytes({"reply": "ok"})

    # Known reject fixture (risk suite): insufficient cash cannot overdraw -> the
    # REAL risk gate returns REJECTED / POLICY_REJECTED (FND-02 case family).
    portfolio = fakes.make_portfolio(cash="899.99", positions=(("MSFT", 91, "100.00"),))
    policy = fakes.make_policy()
    evidence = fakes.base_evidence_pack()
    proposal = fakes.make_proposal(
        policy=policy, evidence=evidence, portfolio=portfolio, quantity=9
    )
    known_run_id = proposal.run_id  # "run-1" — carried by the input proposal

    version_before, entries_before = _ledger_state_init(db_path, portfolio)

    result = _runner()(
        governor=gov,
        provider=fake_provider,
        limits={"max_total_tokens": 10000, "max_calls": 5, "max_cost_usd": "1.00"},
        evidence=evidence,
        proposal=proposal,
        portfolio=portfolio,
        clock=fakes.FixedClock(fakes.NOW),
        db_path=db_path,
        audit_path=audit_path,
    )

    # Exact verdict + reason from the REAL gate (verified standalone: REJECTED /
    # POLICY_REJECTED for this insufficient-cash fixture).
    assert result.verdict.status.value == "REJECTED"
    assert _reason_code().POLICY_REJECTED in result.verdict.reasons

    # The runner returns the SAME known run_id as the input.
    assert result.run_id == known_run_id

    # Ledger unchanged (independent read before/after).
    version_after, entries_after = _ledger_state(db_path)
    assert entries_after == entries_before
    assert version_after == version_before

    # Real audit reader queried by the known run_id: a rejection event exists.
    conn = _audit_conn(audit_path)
    try:
        audit_events = _audit_reader(conn).read(known_run_id)
    finally:
        conn.close()
    assert audit_events
    assert any(e.reason_code == _reason_code().POLICY_REJECTED for e in audit_events)


# ---------------------------------------------------------------------------
# 3. Budget-deny — transport 0, ledger unchanged, BUDGET_DENIED, real audit.
# ---------------------------------------------------------------------------


def test_runner_budget_deny_transport_zero_shared_reason(governor_factory, tmp_path):
    fakes = _risk_fakes()
    db_path = tmp_path / "ledger.db"
    audit_path = tmp_path / "audit.db"
    gov = governor_factory(
        limits={"max_total_tokens": 0, "max_calls": 0, "max_cost_usd": "0"}
    ).governor

    sends: list[str] = []

    def fake_provider(prompt: str):
        sends.append(prompt)
        return fakes.canonical_bytes({"reply": "never"})

    policy = fakes.base_policy()
    portfolio = fakes.base_portfolio()
    evidence = fakes.base_evidence_pack()
    proposal = fakes.make_proposal(policy=policy, evidence=evidence, portfolio=portfolio)
    known_run_id = proposal.run_id  # "run-1" — carried by the input proposal

    version_before, entries_before = _ledger_state_init(db_path, portfolio)

    result = _runner()(
        governor=gov,
        provider=fake_provider,
        limits={"max_total_tokens": 0, "max_calls": 0, "max_cost_usd": "0"},
        evidence=evidence,
        proposal=proposal,
        portfolio=portfolio,
        clock=fakes.FixedClock(fakes.NOW),
        db_path=db_path,
        audit_path=audit_path,
    )

    # Provider/MockTransport received ZERO calls.
    assert sends == [], sends
    # Shared refusal reason.
    assert result.reason_code == _reason_code().BUDGET_DENIED
    # The runner returns the SAME known run_id as the input.
    assert result.run_id == known_run_id
    # Ledger unchanged (independent read before/after).
    version_after, entries_after = _ledger_state(db_path)
    assert entries_after == entries_before
    assert version_after == version_before
    # Real audit reader queried by the known run_id: this run has a BUDGET_DENIED
    # audit event.
    conn = _audit_conn(audit_path)
    try:
        audit_events = _audit_reader(conn).read(known_run_id)
    finally:
        conn.close()
    assert audit_events
    assert any(e.reason_code == _reason_code().BUDGET_DENIED for e in audit_events)
    # NOTE: the workflow terminal status on budget exhaustion is deliberately NOT
    # asserted here — it remains an explicit spec item pending E's ruling.


# ---------------------------------------------------------------------------
# 4. CLI — public entry with real offline args dispatches to the runner.
# ---------------------------------------------------------------------------


def test_cli_offline_entry_dispatches_runner(monkeypatch, tmp_path):
    import importlib

    main_mod = importlib.import_module("egta.__main__")

    called: dict = {}

    def spy_runner(**kwargs):
        called.update(kwargs)
        return None

    # Observe dispatch: the CLI must call the runner with the offline paths.
    monkeypatch.setattr("egta.app.runner.run_offline", spy_runner, raising=True)

    exit_code = main_mod.main(
        [
            "--offline",
            "--db-path", str(tmp_path / "ledger.db"),
            "--audit-path", str(tmp_path / "audit.db"),
        ]
    )
    assert exit_code == 0
    assert called, "CLI must dispatch to run_offline"
    assert called.get("db_path") == str(tmp_path / "ledger.db")
    assert called.get("audit_path") == str(tmp_path / "audit.db")
