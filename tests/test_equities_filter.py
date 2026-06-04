"""Tests for the penny-stock price/ADV filter in equities ingestion."""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_trends.data.ingest.equities import _filter_penny


def _bars(close: float, volume: float, n: int = 30) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close, "Volume": volume},
        index=idx,
    )


def test_keeps_cheap_liquid():
    by_ticker = {"PENNY": _bars(close=2.0, volume=2_000_000)}
    out = _filter_penny(by_ticker)
    assert list(out.keys()) == ["PENNY"]   # 2 * 2M = $4M ADV, well above $1M


def test_drops_too_expensive():
    by_ticker = {"TOOHI": _bars(close=12.0, volume=2_000_000)}
    out = _filter_penny(by_ticker)
    assert out == {}


def test_drops_too_illiquid():
    by_ticker = {"THIN": _bars(close=2.0, volume=10_000)}
    out = _filter_penny(by_ticker)
    assert out == {}                       # $20k ADV, way below floor


def test_handles_empty_frame():
    by_ticker = {"EMPTY": pd.DataFrame()}
    out = _filter_penny(by_ticker)
    assert out == {}


def test_uses_last_close_not_average():
    # First 20 bars cheap, last bar above the ceiling.
    bars = _bars(close=2.0, volume=5_000_000, n=21)
    bars.iloc[-1, bars.columns.get_loc("Close")] = 7.0
    out = _filter_penny({"BREAKUP": bars})
    assert out == {}                       # filter looks at last close
