from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the `crypto_trends` package. Anchoring paths here
# means scripts/servers work regardless of cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    duckdb_path: Path = _PROJECT_ROOT / "data" / "crypto_trends.duckdb"

    # Binance.US by default — Binance.com geo-blocks US IPs. Override with
    # https://api.binance.com if you have an unblocked connection.
    binance_base_url: str = "https://api.binance.us"
    binance_api_key: str = ""
    binance_api_secret: str = ""

    universe_size: int = 50
    quote_asset: str = "USDT"

    # FinancialModelingPrep — free key unlocks Congress (Pelosi Tracker +
    # Kongressional Conviction). $14/mo Starter additionally unlocks historical
    # fundamentals for the long-term sleeve backtest.
    fmp_api_key: str = ""

    # Auth — SECRET_KEY signs JWT cookies. In dev a generated default is OK;
    # production deployments MUST set this via env or sessions will be wiped on
    # every restart. SQLite path is co-located with DuckDB analytics by default.
    secret_key: str = "dev-only-change-me-in-production-fb8c2e9a7b3f4d5e6a8c9d0e1f2a3b4c"
    users_db_path: Path = _PROJECT_ROOT / "data" / "users.db"
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7
    auth_cookie_name: str = "crypto_trends_session"

    # DEV_MODE=true permits the hardcoded SECRET_KEY default + relaxes other
    # prod-only fail-fasts (e.g. allow multiple uvicorn workers with SQLite).
    # Default true so local dev "just works"; deploy scripts must set false.
    dev_mode: bool = True

    # Stripe — get keys at https://dashboard.stripe.com/test/apikeys
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro_monthly: str = ""   # e.g. price_1ABC... from your Stripe dashboard
    stripe_price_pro_annual: str = ""
    # One-time price ($99) for the limited "Founder Lifetime" tier — 100 spots.
    # Buying this flips the user to subscription_tier='founder_lifetime' with
    # no expiry. Counter enforced server-side at checkout time.
    stripe_price_founder_lifetime: str = ""
    founder_lifetime_spot_cap: int = 100

    # NOWPayments — get key at https://account.nowpayments.io/store/api-keys
    nowpayments_api_key: str = ""
    nowpayments_ipn_secret: str = ""

    # Public URL for redirect/return after payment (set in prod to your domain)
    app_base_url: str = "http://localhost:3000"

    # CORS — comma-separated list of allowed frontend origins. Dev default is
    # localhost:3000; in prod set to your Vercel URL (e.g.
    # "https://evernorthstar.vercel.app,https://signalsync.5royals.com").
    # Credentials + cookies require explicit origins; cannot use "*".
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
