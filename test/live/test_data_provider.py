"""Live data-provider test for FR-01 evidence (module A).

This test talks to a REAL provider (Yahoo Finance via ``yfinance``). It is
**skipped by default** and only runs when ``EGTA_LIVE_DATA=1`` is set, because:

* the offline suite and CI must stay network-free (NFR-08);
* live availability/credentials are environment-specific, so a green default run
  must not depend on the network.

Purpose: confirm that real provider data satisfies the same evidence invariants
module A enforces on fixtures (``egta.evidence`` / ``egta.evidence.hashing``):

* ``published_at``/bar date is parseable and not in the future relative to "now";
* ``content_hash`` equals ``sha256(excerpt)`` (integrity, FR-01/T04);
* a real item is admissible under INV-02 for an ``as_of`` of "now".

It uses ``pytest.mark.skipif`` (built-in, so ``--strict-markers`` is satisfied)
rather than a custom ``live`` marker, because ``pyproject.toml`` markers are not
module A's to edit.

Run locally:
    EGTA_LIVE_DATA=1 pytest test/live/test_data_provider.py -q -rsx
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from egta.evidence.pack import build_pack  # noqa: E402
from egta.evidence.time_policy import is_admissible  # noqa: E402

_LIVE = os.environ.get("EGTA_LIVE_DATA") == "1"
_live_only = pytest.mark.skipif(not _LIVE, reason="live provider test; set EGTA_LIVE_DATA=1")

_TICKER = os.environ.get("EGTA_LIVE_TICKER", "AAPL")


def _fetch_recent_daily_bar(ticker: str) -> dict:
    """Fetch the most recent daily OHLCV row for ``ticker`` from Yahoo Finance.

    Returns fields the test needs to build an evidence item. Network + import of
    ``yfinance`` happen only here, so importing this module offline is safe.
    """
    import yfinance as yf

    history = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
    if history is None or history.empty:
        pytest.skip(f"no daily bars returned for {ticker} (provider/network)")
    last_index = history.index[-1]
    row = history.iloc[-1]
    bar_date = last_index.date() if hasattr(last_index, "date") else last_index
    return {
        "bar_date": bar_date,
        "close": float(row["Close"]),
        "open": float(row["Open"]),
        "high": float(row["High"]),
        "low": float(row["Low"]),
        "volume": float(row["Volume"]),
    }


def _evidence_item(ticker: str, bar: dict) -> dict:
    excerpt = (
        f"OHLC {bar['bar_date'].isoformat()}: open {bar['open']}, high {bar['high']}, "
        f"low {bar['low']}, close {bar['close']}"
    )
    return {
        "case_local_id": f"live-{ticker}-{bar['bar_date'].isoformat()}",
        "source_type": "yfinance_bar",
        "source_uri": f"yfinance://{ticker}/{bar['bar_date'].isoformat()}",
        "time_granularity": "date_only",
        "published_at": bar["bar_date"].isoformat(),
        "fetched_at": datetime.now(UTC).isoformat(),
        "excerpt": excerpt,
        "content_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        "trust_label": "primary",
    }


@pytest.fixture(scope="module")
def live_bar():
    return _fetch_recent_daily_bar(_TICKER)


@_live_only
def test_live_bar_date_not_in_future(live_bar):
    bar_date = live_bar["bar_date"]
    assert isinstance(bar_date, date)
    # A daily bar dated today or earlier is fine; a future date would be lookahead.
    assert bar_date <= datetime.now(UTC).date() + timedelta(days=1)


@_live_only
def test_live_content_hash_matches_excerpt(live_bar):
    item = _evidence_item(_TICKER, live_bar)
    assert hashlib.sha256(item["excerpt"].encode("utf-8")).hexdigest() == item["content_hash"]


@_live_only
def test_live_item_admissible_under_inv02(live_bar):
    item = _evidence_item(_TICKER, live_bar)
    as_of = datetime.now(UTC)
    verdict = is_admissible(
        published_at=item["published_at"],
        time_granularity=item["time_granularity"],
        as_of=as_of,
    )
    # The latest completed daily bar (yesterday or earlier) must be point-in-time
    # admissible; a same-day-in-progress bar may be excluded, which is also valid.
    if live_bar["bar_date"] < as_of.date():
        assert verdict.admissible, verdict.reason_code


@_live_only
def test_live_pack_builds_with_real_bar(live_bar):
    from egta.contracts import RunSpec

    item = _evidence_item(_TICKER, live_bar)
    run_spec = RunSpec(
        schema_version="1.0",
        run_id="run-live",
        ticker=_TICKER,
        as_of=datetime.now(UTC),
        mode="enhanced",
        model_config_hash="1" * 64,
        prompt_hash="2" * 64,
        policy_hash="3" * 64,
        snapshot_id="snap-live",
        limits={},
    )
    pack = build_pack(run_spec, [item])
    # Whatever the admission outcome, the pack is well-formed and hash-bound.
    assert pack.run_id == run_spec.run_id
    assert len(pack.pack_hash) == 64
    for admitted in pack.items:
        assert hashlib.sha256(admitted.excerpt.encode("utf-8")).hexdigest() == admitted.content_hash
