"""FR-01 evidence classification precedence: integrity -> staleness -> time.

Companion to the frozen pack spec (``test_pack.py``, PR #25). It pins the
*precedence* among exclusion causes that the frozen spec leaves open, so a
tampered cache item is reported as ``INTEGRITY_VIOLATION`` (audit correctness,
FR-01/T04) and a future-dated cache item is ``STALE_DATA`` (cache is
unverifiable off-line, E-26 rule), rather than whichever check happens to run
first.

This file is additive only; it does not modify or replace ``test_pack.py``.
It is selected by ``-m spec`` like the rest of the FR-01 pack suite.
"""

from __future__ import annotations

import hashlib

import pytest

pytestmark = pytest.mark.spec


@pytest.fixture(scope="session")
def precedence_api():
    from egta.contracts import Availability, RunSpec
    from egta.contracts.events import ReasonCode
    from egta.evidence.pack import build_pack

    class _Api:
        pass

    api = _Api()
    api.Availability = Availability
    api.RunSpec = RunSpec
    api.ReasonCode = ReasonCode
    api.build_pack = staticmethod(build_pack)
    return api


def _run_spec(api, case: dict) -> object:
    return api.RunSpec(
        schema_version="1.0",
        run_id=f"run-{case['case_id']}",
        ticker="AAPL",
        as_of=case["as_of"],
        mode="enhanced",
        model_config_hash="1" * 64,
        prompt_hash="2" * 64,
        policy_hash="3" * 64,
        snapshot_id=f"snap-{case['case_id']}",
        limits={},
    )


def _rehash(raw: dict) -> dict:
    """Return a copy whose content_hash matches its (tampered) excerpt."""
    copy = dict(raw)
    copy["content_hash"] = hashlib.sha256(copy["excerpt"].encode("utf-8")).hexdigest()
    return copy


def test_tampered_cache_is_integrity_not_stale(precedence_api, load_case):
    """A cache item whose excerpt was altered is INTEGRITY_VIOLATION, not STALE."""
    api = precedence_api
    case = load_case("E-26")  # clean cache item: source_type == "cache"
    raw = dict(case["items"][0])
    raw["excerpt"] = raw["excerpt"] + " [tampered]"
    # keep the OLD content_hash so sha256(excerpt) != content_hash -> tampered
    run_spec = _run_spec(api, case)

    pack = api.build_pack(run_spec, [raw])
    assert pack.items == []
    assert len(pack.excluded_items) == 1
    bad = pack.excluded_items[0]
    assert bad.case_local_id == raw["case_local_id"]
    assert bad.reason_code == api.ReasonCode.INTEGRITY_VIOLATION
    assert bad.availability == api.Availability.UNAVAILABLE


def test_well_formed_cache_still_stale(precedence_api, load_case):
    """Control: an untampered cache item is still STALE_DATA (E-26 unchanged)."""
    api = precedence_api
    case = load_case("E-26")
    raw = case["items"][0]
    assert hashlib.sha256(raw["excerpt"].encode("utf-8")).hexdigest() == raw["content_hash"]
    run_spec = _run_spec(api, case)

    pack = api.build_pack(run_spec, [raw])
    assert pack.items == []
    bad = pack.excluded_items[0]
    assert bad.reason_code == api.ReasonCode.STALE_DATA
    assert bad.availability == api.Availability.STALE


def test_future_cache_is_stale_not_future_data(precedence_api, load_case):
    """A future-dated *cache* item is STALE_DATA (unverifiable off-line), not FUTURE."""
    api = precedence_api
    case = load_case("E-26")
    raw = dict(case["items"][0])
    # Move publication AFTER as_of (2026-11-11T00:00:00Z) but keep it consistent.
    raw["published_at"] = "2026-12-01T00:00:00Z"
    raw["fetched_at"] = "2026-12-01T00:05:00Z"
    raw = _rehash(raw)  # excerpt unchanged, still well-formed (not tampered)
    run_spec = _run_spec(api, case)

    pack = api.build_pack(run_spec, [raw])
    assert pack.items == []
    bad = pack.excluded_items[0]
    # cache is classified as stale before the time filter runs.
    assert bad.reason_code == api.ReasonCode.STALE_DATA
    assert bad.availability == api.Availability.STALE


def test_future_non_cache_is_future_data(precedence_api, load_case):
    """Control: a future-dated non-cache item is FUTURE_DATA (time filter)."""
    api = precedence_api
    case = load_case("E-16")  # future-dated fred item, non-cache
    raw = case["items"][0]
    run_spec = _run_spec(api, case)

    pack = api.build_pack(run_spec, [raw])
    assert pack.items == []
    bad = pack.excluded_items[0]
    assert bad.reason_code == api.ReasonCode.FUTURE_DATA
    assert bad.availability == api.Availability.UNAVAILABLE
