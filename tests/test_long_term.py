"""Tests for the long-term factor signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_trends.signals.long_term import compute, compute_components


def _close_panel(symbols: list[str], n: int = 300) -> pd.DataFrame:
    """All symbols have flat prices — momentum component will be ~0 across the board."""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({s: 100.0 for s in symbols}, index=idx)


def _fundamentals(spec: dict[str, dict]) -> pd.DataFrame:
    """spec: {symbol: {roe, debt_to_equity, profit_margin, pe, pb, market_cap}}"""
    return pd.DataFrame(spec).T


def test_higher_quality_scores_higher():
    syms = ["HQ", "MED", "LQ"]
    close = _close_panel(syms)
    f = _fundamentals({
        "HQ":  {"roe": 0.30, "debt_to_equity": 30, "profit_margin": 0.25,
                "pe": 25, "pb": 5, "market_cap": 1e11},
        "MED": {"roe": 0.15, "debt_to_equity": 80, "profit_margin": 0.10,
                "pe": 25, "pb": 5, "market_cap": 1e11},
        "LQ":  {"roe": 0.02, "debt_to_equity": 200, "profit_margin": 0.01,
                "pe": 25, "pb": 5, "market_cap": 1e11},
    })

    scores = compute(close, f)

    assert scores["HQ"] > scores["MED"] > scores["LQ"]


def test_value_component_prefers_lower_pe():
    syms = ["CHEAP", "FAIR", "EXP"]
    close = _close_panel(syms)
    f = _fundamentals({
        "CHEAP": {"roe": 0.15, "debt_to_equity": 60, "profit_margin": 0.10,
                  "pe": 8,  "pb": 1.5, "market_cap": 1e11},
        "FAIR":  {"roe": 0.15, "debt_to_equity": 60, "profit_margin": 0.10,
                  "pe": 18, "pb": 3.0, "market_cap": 1e11},
        "EXP":   {"roe": 0.15, "debt_to_equity": 60, "profit_margin": 0.10,
                  "pe": 60, "pb": 8.0, "market_cap": 1e11},
    })

    comps = compute_components(close, f)

    assert comps.loc["CHEAP", "value"] > comps.loc["FAIR", "value"] > comps.loc["EXP", "value"]


def test_missing_symbols_excluded():
    close = _close_panel(["A", "B"])
    # Only one fundamental row.
    f = _fundamentals({
        "A": {"roe": 0.2, "debt_to_equity": 50, "profit_margin": 0.15,
              "pe": 20, "pb": 3, "market_cap": 1e10},
    })
    comps = compute_components(close, f)
    assert "A" in comps.index
    assert "B" not in comps.index


def test_returns_empty_for_no_overlap():
    close = _close_panel(["A", "B"])
    f = _fundamentals({
        "Z": {"roe": 0.2, "debt_to_equity": 50, "profit_margin": 0.15,
              "pe": 20, "pb": 3, "market_cap": 1e10},
    })
    out = compute(close, f)
    assert out.empty
