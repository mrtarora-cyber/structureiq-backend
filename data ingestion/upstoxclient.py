# StructureIQ - Upstox Data Client
# Fetches live prices and candles for Nifty & Sensex

import httpx
import pandas as pd
import logging
from datetime import datetime, timedelta
from config import settings
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

class UpstoxClient:
    """
    Connects to Upstox API to get:
    - Live prices (every 30 seconds)
    - Historical candles (for structure analysis)
    """

    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self):
        self.token = settings.UPSTOX_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }
        # Last known prices (backup if API fails)
        self.last_prices = {
            "NIFTY": None,
            "SENSEX": None
        }

    async def get_live_price(self, symbol: str) -> dict:
        """
        Get current live price for NIFTY or SENSEX
        Returns: price, change, change_percent
        """
        instrument = settings.INSTRUMENT_TOKENS.get(symbol)
        if not instrument:
            logger.error(f"Unknown symbol: {symbol}")
            return None

        url = f"{self.BASE_URL}/market-quote/quotes"
        params = {"instrument_key": instrument}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    quote = data.get("data", {}).get(instrument, {})

                    last_price = quote.get("last_price", 0)
                    ohlc = quote.get("ohlc", {})
                    prev_close = ohlc.get("close", last_price)
                    change = last_price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    result = {
                        "symbol": symbol,
                        "last_price": last_price,
                        "open": ohlc.get("open", 0),
                        "high": ohlc.get("high", 0),
                        "low": ohlc.get("low", 0),
                        "prev_close": prev_close,
                        "change": round(change, 2),
                        "change_percent": round(change_pct, 2),
                        "timestamp": datetime.now(IST).isoformat()
                    }

                    # Save as backup
                    self.last_prices[symbol] = result
                    return result

                else:
                    logger.warning(f"Upstox API error {response.status_code} for {symbol}")
                    # Return last known price if API fails
                    return self.last_prices.get(symbol)

        except Exception as e:
            logger.error(f"Error fetching live price for {symbol}: {e}")
            return self.last_prices.get(symbol)

    async def get_candles(self, symbol: str, timeframe: str, count: int = 100) -> list:
        """
        Get historical OHLCV candles for structure analysis
        timeframe: 1m, 5m, 15m, 30m, 1H, 1D
        """
        instrument = settings.INSTRUMENT_TOKENS.get(symbol)
        if not instrument:
            return []

        # Map our timeframe names to Upstox format
        tf_map = {
            "1m":  "1minute",
            "5m":  "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "1H":  "60minute",
            "1D":  "day"
        }
        upstox_tf = tf_map.get(timeframe, "15minute")

        # Date range
        today = datetime.now(IST).date()
        from_date = (today - timedelta(days=30)).isoformat()
        to_date = today.isoformat()

        url = f"{self.BASE_URL}/historical-candle/{instrument}/{upstox_tf}/{to_date}/{from_date}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=15
                )

                if response.status_code == 200:
                    data = response.json()
                    candles_raw = data.get("data", {}).get("candles", [])

                    # Convert to standard format
                    candles = []
                    for c in candles_raw[-count:]:
                        candles.append({
                            "timestamp": c[0],
                            "open":   float(c[1]),
                            "high":   float(c[2]),
                            "low":    float(c[3]),
                            "close":  float(c[4]),
                            "volume": int(c[5]) if len(c) > 5 else 0
                        })

                    logger.info(f"Fetched {len(candles)} candles for {symbol} {timeframe}")
                    return candles

                else:
                    logger.warning(f"Candle fetch failed {response.status_code} for {symbol}")
                    return []

        except Exception as e:
            logger.error(f"Error fetching candles for {symbol} {timeframe}: {e}")
            return []

    async def get_market_depth(self, symbol: str) -> dict:
        """
        Get buy/sell order depth for volume confirmation
        """
        instrument = settings.INSTRUMENT_TOKENS.get(symbol)
        if not instrument:
            return {}

        url = f"{self.BASE_URL}/market-quote/depth"
        params = {"instrument_key": instrument}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", {}).get(instrument, {})
                return {}
        except Exception as e:
            logger.error(f"Error fetching market depth: {e}")
            return {}
