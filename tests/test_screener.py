"""Tests for the penny-stock screener's pure-logic helpers."""

from __future__ import annotations

import pandas as pd

from crypto_trends.data.screener import filter_common_stock


def test_filters_warrants_and_units():
    df = pd.DataFrame({
        "Symbol":        ["AAPL", "FOOW", "BARU", "BAZR",  "QUUX$", "TSLA"],
        "Security Name": ["A",    "B",    "C",    "D",     "E",      "F"],
        "ETF":           ["N",    "N",    "N",    "N",     "N",      "N"],
        "Test Issue":    ["N",    "N",    "N",    "N",     "N",      "N"],
    })
    out = filter_common_stock(df)
    assert "AAPL" in out
    assert "TSLA" in out
    assert "FOOW" not in out      # warrant suffix
    assert "BARU" not in out      # unit suffix
    assert "BAZR" not in out      # rights suffix
    assert "QUUX$" not in out     # preferred ($)


def test_filters_etfs_and_test_issues():
    df = pd.DataFrame({
        "Symbol":        ["GOOD", "ETFY", "TEST", "ALSO"],
        "Security Name": ["a",    "b",    "c",    "d"],
        "ETF":           ["N",    "Y",    "N",    "N"],
        "Test Issue":    ["N",    "N",    "Y",    "N"],
    })
    out = filter_common_stock(df)
    assert "GOOD" in out
    assert "ALSO" in out
    assert "ETFY" not in out
    assert "TEST" not in out


def test_skips_too_long_symbols():
    df = pd.DataFrame({
        "Symbol":        ["AAA", "BBBBBB", "CCCC"],
        "Security Name": ["x",   "y",      "z"],
        "ETF":           ["N",   "N",      "N"],
        "Test Issue":    ["N",   "N",      "N"],
    })
    out = filter_common_stock(df)
    assert "AAA" in out
    assert "CCCC" in out
    assert "BBBBBB" not in out   # 6 chars; common stock is rarely >5


def test_handles_missing_columns():
    df = pd.DataFrame({"Symbol": ["AAPL"], "Security Name": ["a"],
                       "ETF": [None], "Test Issue": [None]})
    out = filter_common_stock(df)
    assert out == ["AAPL"]
