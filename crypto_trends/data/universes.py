"""Hardcoded universe lists.

These are starter universes for the MVP. In a real product, large-cap names
would be refreshed from S&P 500 constituent data and penny-stock screens
would run daily. For now: refresh manually as needed.
"""

# S&P 500 — top ~100 by recent market cap. Refresh periodically.
SP100 = [
    "AAPL", "MSFT", "NVDA", "GOOG", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
    "AVGO", "JPM", "WMT", "LLY", "ORCL", "V", "MA", "XOM", "PG", "JNJ",
    "COST", "HD", "ABBV", "BAC", "KO", "PLTR", "NFLX", "TMUS", "AMD",
    "CRM", "CVX", "WFC", "PEP", "TMO", "CSCO", "ABT", "ADBE", "ACN", "MCD",
    "LIN", "IBM", "MRK", "PM", "GE", "AXP", "NOW", "DIS", "CAT", "UBER",
    "T", "QCOM", "VZ", "ISRG", "INTU", "GS", "BKNG", "TXN", "RTX", "MS",
    "AMGN", "BLK", "PFE", "SCHW", "SPGI", "NEE", "PGR", "LOW", "C", "HON",
    "BSX", "ANET", "BX", "TJX", "DHR", "DE", "ETN", "BA", "GILD", "VRTX",
    "ELV", "CMCSA", "AMAT", "ADI", "PANW", "MU", "SYK", "MDLZ", "ADP",
    "CB", "SBUX", "PLD", "MMC", "REGN", "LMT", "INTC", "FI", "KKR", "CME",
    "BMY", "SO", "UPS", "ICE", "LRCX",
]

# Liquid US-listed (NASDAQ/NYSE) sub-$5 names. These are SEC-regulated stocks
# trading on major exchanges — NOT pink sheets, which carry much higher risk.
# Universe is volatile; expect ~20% of these to be over $5 or delisted at any
# given time — the ingester drops anything it can't fetch.
#
# Real product: replace with a daily screen of NASDAQ/NYSE listings where
# last_close < 5 AND 20d_avg_dollar_volume > 1_000_000.
PENNY_CANDIDATES = [
    "SOFI", "F", "PLUG", "AAL", "RIG", "GPS", "BBAI", "NIO", "RIVN",
    "BTG", "KGC", "HBAN", "MARA", "RIOT", "CLF", "X", "VALE", "HOOD",
    "GRAB", "BITF", "HUT", "CIFR", "WULF", "IREN", "CLSK", "WBD",
    "SNAP", "PINS", "LCID", "AUR", "JOBY", "ACHR", "EVGO", "CHPT",
    "BLNK", "DNN", "UEC", "URG", "NU", "STNE", "PAGS", "VTRS", "TEVA",
    "AGNC", "NLY", "OPEN", "RUM", "BBAI", "SOUN", "RGTI", "QBTS",
    "IONQ", "QUBT", "TLRY", "CGC", "ACB", "HEXO", "SNDL",
]


def all_equity_universe() -> dict[str, list[str]]:
    """Return {asset_class: [tickers]} for both equity sleeves."""
    return {
        "equity_large": SP100,
        "equity_micro": PENNY_CANDIDATES,
    }
