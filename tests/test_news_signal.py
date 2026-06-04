"""Tests for the news_v1 signal aggregation.

Builds a fresh DB, seeds universe + news rows, computes the signal, and
verifies buzz/sentiment z-scores + the negative_event keyword flag.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from crypto_trends.data.store import connect
from crypto_trends.signals.news import compute_for_asset_class


def _seed_universe(symbols: list[str], asset_class: str = "equity_large") -> None:
    with connect() as c:
        for i, s in enumerate(symbols, 1):
            c.execute(
                'INSERT INTO universe (symbol, base, quote, asset_class, "rank", '
                'included, updated_at) VALUES (?, ?, ?, ?, ?, TRUE, now())',
                [s, s, "USD", asset_class, i],
            )


def _seed_news(rows: list[tuple]) -> None:
    """rows: [(symbol, headline, published_at, sentiment, asset_class)]"""
    with connect() as c:
        for sym, head, ts, sent, ac in rows:
            c.execute(
                "INSERT INTO news (id, symbol, asset_class, source, headline, "
                "url, publisher, published_at, sentiment) "
                "VALUES (nextval('news_id_seq'), ?, ?, 'yfinance', ?, NULL, 'test', ?, ?)",
                [sym, ac, head, ts, sent],
            )


def test_buzz_z_score_reflects_relative_volume(tmp_db):
    _seed_universe(["AAA", "BBB", "CCC"])
    now = datetime.utcnow()
    rows = [
        ("AAA", "story 1", now - timedelta(hours=1), 0.1, "equity_large"),
        ("AAA", "story 2", now - timedelta(hours=2), 0.2, "equity_large"),
        ("AAA", "story 3", now - timedelta(hours=3), 0.0, "equity_large"),
        ("BBB", "single",  now - timedelta(hours=1), 0.0, "equity_large"),
        # CCC has zero headlines
    ]
    _seed_news(rows)

    sigs = compute_for_asset_class("equity_large", window_hours=24)

    assert sigs["AAA"].buzz == 3
    assert sigs["BBB"].buzz == 1
    assert sigs["CCC"].buzz == 0
    assert sigs["AAA"].buzz_z > sigs["BBB"].buzz_z > sigs["CCC"].buzz_z


def test_negative_event_triggered_by_keyword(tmp_db):
    _seed_universe(["AAA", "BBB"])
    now = datetime.utcnow()
    rows = [
        # AAA has a bankruptcy keyword even though sentiment is mildly positive
        ("AAA", "Company files for Chapter 11 bankruptcy after restructuring", now,
         0.1, "equity_large"),
        # BBB has very negative sentiment but no keyword — should NOT trigger
        ("BBB", "Stock had a rough day after broad market sell-off", now,
         -0.8, "equity_large"),
    ]
    _seed_news(rows)

    sigs = compute_for_asset_class("equity_large", window_hours=24)

    assert sigs["AAA"].negative_event is True
    assert sigs["BBB"].negative_event is False


def test_window_excludes_old_headlines(tmp_db):
    _seed_universe(["AAA"])
    now = datetime.utcnow()
    rows = [
        ("AAA", "fresh",  now - timedelta(hours=2),  0.5, "equity_large"),
        ("AAA", "old",    now - timedelta(hours=30), 0.5, "equity_large"),
    ]
    _seed_news(rows)

    sigs = compute_for_asset_class("equity_large", window_hours=24)

    # Only the fresh headline should be counted.
    assert sigs["AAA"].buzz == 1
    assert sigs["AAA"].recent_headline == "fresh"


def test_empty_universe_returns_empty(tmp_db):
    sigs = compute_for_asset_class("equity_large")
    assert sigs == {}
