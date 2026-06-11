# StructureIQ - Configuration
# Reads all environment variables and settings

import os
from dotenv import load_dotenv
import pytz

load_dotenv()

class Settings:
    # App
    APP_NAME: str = "StructureIQ"
    VERSION: str = "1.0.0"

    # Supabase Database
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://mreolzlwfxyhrngdxnfz.supabase.co")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # Upstox Market Data
    UPSTOX_TOKEN: str = os.getenv("UPSTOX_TOKEN", "")

    # Telegram Alerts
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "5623578362")

    # Risk Management
    CAPITAL: float = float(os.getenv("CAPITAL", "10000"))
    RISK_PER_TRADE: float = float(os.getenv("RISK_PER_TRADE", "1.0"))
    DAILY_LOSS_LIMIT: float = float(os.getenv("DAILY_LOSS_LIMIT", "2.0"))
    MAX_DRAWDOWN: float = float(os.getenv("MAX_DRAWDOWN", "5.0"))

    # Market Hours (IST)
    MARKET_OPEN_HOUR: int = 9
    MARKET_OPEN_MINUTE: int = 15
    MARKET_CLOSE_HOUR: int = 15
    MARKET_CLOSE_MINUTE: int = 30

    # Timezone
    TIMEZONE: pytz.timezone = pytz.timezone("Asia/Kolkata")

    # Symbols to track
    SYMBOLS: list = ["NIFTY", "SENSEX"]

    # Upstox instrument tokens
    # These are Upstox's internal codes for Nifty and Sensex
    INSTRUMENT_TOKENS: dict = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "SENSEX": "BSE_INDEX|SENSEX"
    }

    # Signal Settings
    MIN_RR_RATIO: float = 1.5        # Minimum risk/reward to generate signal
    MIN_CONFIDENCE: int = 60          # Minimum confidence score (out of 100)
    CANDLES_NEEDED: int = 50          # Candles needed for structure analysis

    # Timeframes to analyze
    TIMEFRAMES: list = ["1m", "5m", "15m", "30m", "1H", "1D"]
    PRIMARY_TIMEFRAME: str = "15m"    # Main timeframe for signals

settings = Settings()
