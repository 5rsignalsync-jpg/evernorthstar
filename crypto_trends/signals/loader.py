"""Load wide-format close-price panels from DuckDB."""

from __future__ import annotations

import pandas as pd

from crypto_trends.data.store import connect


def load_close_panel(
    asset_class: str = "crypto",
    interval: str | None = None,
    source: str | None = None,
) -> pd.DataFrame:
    """Return a wide DataFrame: rows = ts, columns = symbol, values = close.

    Args:
        asset_class: 'crypto', 'equity_large', or 'equity_micro'. Required.
        interval: '1h', '1d', '1w'. Defaults sensibly per asset_class.
        source: 'binance' or 'yfinance'. Defaults sensibly per asset_class.

    Only includes symbols currently in the universe (included=TRUE).
    """
    if interval is None:
        interval = "1h" if asset_class.startswith("crypto") else "1d"
    if source is None:
        source = "binance" if asset_class.startswith("crypto") else "yfinance"

    sql = """
        SELECT o.ts, o.symbol, o.close
        FROM ohlcv o
        JOIN universe u ON u.symbol = o.symbol
        WHERE u.included = TRUE
          AND u.asset_class = ?
          AND o.interval = ?
          AND o.source = ?
        ORDER BY o.ts, o.symbol
    """
    with connect(read_only=True) as conn:
        long_df = conn.execute(sql, [asset_class, interval, source]).fetchdf()

    if long_df.empty:
        return pd.DataFrame()

    wide = long_df.pivot(index="ts", columns="symbol", values="close")
    wide.columns.name = None
    return wide.sort_index()
