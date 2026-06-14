-- Crypto Trends schema. Idempotent; safe to re-run.

CREATE TABLE IF NOT EXISTS universe (
    symbol      VARCHAR PRIMARY KEY,    -- e.g. "BTCUSDT", "AAPL"
    base        VARCHAR NOT NULL,       -- e.g. "BTC", "AAPL"
    quote       VARCHAR NOT NULL,       -- e.g. "USDT", "USD"
    asset_class VARCHAR NOT NULL DEFAULT 'crypto',  -- crypto | equity_large | equity_micro
    rank        INTEGER,                -- 1 = largest within its asset class
    included    BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ohlcv (
    symbol      VARCHAR NOT NULL,
    ts          TIMESTAMP NOT NULL,     -- bar open time, UTC
    interval    VARCHAR NOT NULL,       -- "1h", "1d", "1w"
    asset_class VARCHAR NOT NULL DEFAULT 'crypto',
    open        DOUBLE  NOT NULL,
    high        DOUBLE  NOT NULL,
    low         DOUBLE  NOT NULL,
    close       DOUBLE  NOT NULL,
    volume      DOUBLE  NOT NULL,
    quote_volume DOUBLE,
    source      VARCHAR NOT NULL,       -- "binance" | "yfinance"
    PRIMARY KEY (symbol, ts, interval, source)
);

-- Migrations for pre-existing databases. DuckDB ALTER doesn't accept DEFAULT/NOT NULL,
-- so we add the column then backfill. Both statements are idempotent.
ALTER TABLE universe ADD COLUMN IF NOT EXISTS asset_class VARCHAR;
ALTER TABLE ohlcv    ADD COLUMN IF NOT EXISTS asset_class VARCHAR;
UPDATE universe SET asset_class = 'crypto' WHERE asset_class IS NULL;
UPDATE ohlcv    SET asset_class = 'crypto' WHERE asset_class IS NULL;

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_ts ON ohlcv(symbol, ts);

CREATE TABLE IF NOT EXISTS signal_scores (
    symbol          VARCHAR NOT NULL,
    ts              TIMESTAMP NOT NULL,
    signal_name     VARCHAR NOT NULL,   -- "momentum_v1", "long_term_v1", etc.
    score           DOUBLE NOT NULL,    -- normalized roughly to [-1, 1] (long-only signals: [0, 1])
    components      JSON,               -- sub-scores for debugging
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, ts, signal_name)
);

-- Quarterly-ish snapshot of fundamentals for the long-term sleeve.
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol          VARCHAR NOT NULL,
    as_of           DATE NOT NULL,      -- snapshot date
    market_cap      DOUBLE,
    pe              DOUBLE,             -- trailing PE
    forward_pe      DOUBLE,
    pb              DOUBLE,             -- price/book
    roe             DOUBLE,
    debt_to_equity  DOUBLE,
    profit_margin   DOUBLE,
    sector          VARCHAR,
    industry        VARCHAR,
    fetched_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, as_of)
);

CREATE INDEX IF NOT EXISTS idx_signal_ts_name ON signal_scores(ts, signal_name);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id          BIGINT PRIMARY KEY,
    source      VARCHAR NOT NULL,
    started_at  TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    rows        BIGINT,
    status      VARCHAR NOT NULL,       -- "ok", "error"
    note        VARCHAR
);

CREATE SEQUENCE IF NOT EXISTS ingest_runs_id_seq START 1;

-- Headlines + VADER sentiment, deduped on (symbol, headline, published_at).
CREATE TABLE IF NOT EXISTS news (
    id              BIGINT PRIMARY KEY,
    symbol          VARCHAR NOT NULL,
    asset_class     VARCHAR NOT NULL,
    source          VARCHAR NOT NULL,    -- "yfinance" | "cryptocompare"
    headline        VARCHAR NOT NULL,
    url             VARCHAR,
    publisher       VARCHAR,
    published_at    TIMESTAMP NOT NULL,
    fetched_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sentiment       DOUBLE,              -- VADER compound score in [-1, 1]
    UNIQUE (symbol, headline, published_at)
);
CREATE INDEX IF NOT EXISTS idx_news_symbol_ts ON news(symbol, published_at);
CREATE SEQUENCE IF NOT EXISTS news_id_seq START 1;

-- Smart-money / public-disclosure trades: Congress, 13F filers, corporate insiders.
-- The PK is a deterministic SHA1 hash of the row content (see signals/smart_money_id())
-- so re-ingesting the same disclosure is a no-op via ON CONFLICT.
CREATE TABLE IF NOT EXISTS smart_money_trades (
    id                BIGINT PRIMARY KEY,
    source            VARCHAR NOT NULL,    -- congress_house | congress_senate | 13f | insider
    actor_id          VARCHAR NOT NULL,    -- e.g. nancy_pelosi, cik_0001067983 (Berkshire)
    actor_name        VARCHAR NOT NULL,
    actor_role        VARCHAR,             -- Representative | Senator | Hedge Fund | Insider
    party_or_meta     VARCHAR,             -- D / R / I, or "fund"
    ticker            VARCHAR NOT NULL,
    side              VARCHAR NOT NULL,    -- buy | sell | exchange
    transaction_date  DATE,                -- actual trade date where known
    disclosure_date   DATE NOT NULL,       -- when it became public
    amount_min        DOUBLE,              -- congress brackets; 13F/insider may be NULL
    amount_max        DOUBLE,
    shares            DOUBLE,              -- 13F + Form 4 only
    notes             VARCHAR,
    fetched_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sm_ticker_disclosure
    ON smart_money_trades(ticker, disclosure_date);
CREATE INDEX IF NOT EXISTS idx_sm_actor_disclosure
    ON smart_money_trades(actor_id, disclosure_date);

-- Upcoming earnings dates so the UI can flag "going long into a guidance cut" risk.
CREATE TABLE IF NOT EXISTS earnings_calendar (
    symbol              VARCHAR NOT NULL,
    date                DATE NOT NULL,             -- announcement date
    eps_actual          DOUBLE,
    eps_estimated       DOUBLE,
    revenue_actual      DOUBLE,
    revenue_estimated   DOUBLE,
    last_updated        TIMESTAMP,
    fetched_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_calendar(date);
