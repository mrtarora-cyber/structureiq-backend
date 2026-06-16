# StructureIQ - Options Engine
# Tells Nitish exactly which option to buy (CE or PE)
# with strike price, expiry and key levels

import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

class OptionsEngine:
    """
    Converts structure signals into specific F&O recommendations.
    
    Tells Nitish:
    - CE (Call) or PE (Put)
    - Which strike price
    - Which expiry
    - Key levels (Prev Day High/Low, Prev Week High/Low)
    - Plain English explanation
    """

    # Nifty strikes are in multiples of 50
    # Sensex strikes are in multiples of 100
    STRIKE_GAP = {
        "NIFTY": 50,
        "SENSEX": 100
    }

    def get_option_recommendation(
        self,
        signal: dict,
        key_levels: dict
    ) -> dict:
        """
        Given a BUY/SELL signal, recommend the exact option to trade.
        """
        if not signal:
            return None

        symbol      = signal.get("symbol", "NIFTY")
        signal_type = signal.get("signal_type", "")
        entry       = signal.get("entry_price", 0)
        sl          = signal.get("stop_loss", 0)
        t1          = signal.get("target_1", 0)
        t2          = signal.get("target_2", 0)
        confidence  = signal.get("confidence", 0)

        # Determine CE or PE
        option_type = "CE" if signal_type == "BUY" else "PE"

        # Find ATM strike (closest to current price)
        atm_strike = self._get_atm_strike(entry, symbol)

        # For BUY → buy slightly ITM CE (one strike below)
        # For SELL → buy slightly ITM PE (one strike above)
        gap = self.STRIKE_GAP[symbol]
        if signal_type == "BUY":
            recommended_strike = atm_strike  # ATM CE
        else:
            recommended_strike = atm_strike  # ATM PE

        # Get expiry
        expiry = self._get_nearest_expiry()
        expiry_str = expiry.strftime("%d %b")

        # Build key levels context
        pdh = key_levels.get("prev_day_high", 0)
        pdl = key_levels.get("prev_day_low", 0)
        pwh = key_levels.get("prev_week_high", 0)
        pwl = key_levels.get("prev_week_low", 0)
        day_open = key_levels.get("day_open", 0)

        # Determine which key level triggered the signal
        trigger_level = self._find_trigger_level(entry, key_levels, signal_type)

        # Build plain English explanation for options
        option_reason = self._build_option_reason(
            signal_type, option_type, symbol,
            recommended_strike, expiry_str,
            trigger_level, key_levels
        )

        # Risk for options (estimate premium)
        est_premium = self._estimate_premium(entry, recommended_strike, signal_type, symbol)

        return {
            "symbol":             symbol,
            "signal_type":        signal_type,
            "option_type":        option_type,
            "strike":             recommended_strike,
            "expiry":             expiry_str,
            "option_name":        f"{symbol} {recommended_strike} {option_type} {expiry_str}",
            "entry_price":        entry,
            "stop_loss":          sl,
            "target_1":           t1,
            "target_2":           t2,
            "estimated_premium":  est_premium,
            "confidence":         confidence,
            "trigger_level":      trigger_level,
            "option_reason":      option_reason,
            "key_levels": {
                "prev_day_high":  pdh,
                "prev_day_low":   pdl,
                "prev_week_high": pwh,
                "prev_week_low":  pwl,
                "day_open":       day_open
            }
        }

    def get_key_levels(self, candles_daily: list, candles_15m: list) -> dict:
        """
        Extract key price levels from historical data.
        Previous Day High/Low, Previous Week High/Low, Day Open.
        """
        levels = {}

        if not candles_daily or len(candles_daily) < 2:
            return levels

        # Previous day candle (index -2, since -1 is today)
        prev_day = candles_daily[-2] if len(candles_daily) >= 2 else {}
        today    = candles_daily[-1] if candles_daily else {}

        levels["prev_day_high"]  = prev_day.get("high", 0)
        levels["prev_day_low"]   = prev_day.get("low", 0)
        levels["prev_day_close"] = prev_day.get("close", 0)
        levels["day_open"]       = today.get("open", 0)
        levels["day_high"]       = today.get("high", 0)
        levels["day_low"]        = today.get("low", 0)

        # Previous week: look back 5-7 trading days
        if len(candles_daily) >= 7:
            week_candles = candles_daily[-7:-2]
            if week_candles:
                levels["prev_week_high"] = max(c.get("high", 0) for c in week_candles)
                levels["prev_week_low"]  = min(c.get("low", 0) for c in week_candles)

        # Previous hour high/low from 15m candles
        if candles_15m and len(candles_15m) >= 4:
            last_hour = candles_15m[-4:]
            levels["prev_hour_high"] = max(c.get("high", 0) for c in last_hour)
            levels["prev_hour_low"]  = min(c.get("low", 0) for c in last_hour)

        return levels

    def _get_atm_strike(self, price: float, symbol: str) -> int:
        """Find the At-The-Money strike price"""
        gap = self.STRIKE_GAP[symbol]
        return round(round(price / gap) * gap)

    def _get_nearest_expiry(self) -> datetime:
        """
        Get nearest weekly expiry.
        Nifty expires every Thursday.
        Sensex expires every Friday.
        """
        today = datetime.now(IST)
        # Find next Thursday (weekday 3)
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7
        expiry = today + timedelta(days=days_until_thursday)
        return expiry

    def _find_trigger_level(
        self, price: float, levels: dict, signal_type: str
    ) -> dict:
        """
        Find which key level the price is near.
        This tells Nitish WHY this is a good entry point.
        """
        tolerance = price * 0.003  # 0.3% tolerance

        level_names = {
            "prev_day_high":  "Previous Day High",
            "prev_day_low":   "Previous Day Low",
            "prev_week_high": "Previous Week High",
            "prev_week_low":  "Previous Week Low",
            "day_open":       "Today's Open",
            "prev_hour_high": "Previous Hour High",
            "prev_hour_low":  "Previous Hour Low"
        }

        for key, name in level_names.items():
            level_price = levels.get(key, 0)
            if level_price and abs(price - level_price) <= tolerance:
                return {
                    "name":  name,
                    "price": level_price,
                    "key":   key
                }

        # Return nearest level even if not exactly at it
        closest = None
        closest_dist = float('inf')
        for key, name in level_names.items():
            level_price = levels.get(key, 0)
            if level_price:
                dist = abs(price - level_price)
                if dist < closest_dist:
                    closest_dist = dist
                    closest = {"name": name, "price": level_price, "key": key}

        return closest or {"name": "Structure Zone", "price": price, "key": "structure"}

    def _estimate_premium(
        self, price: float, strike: int,
        signal_type: str, symbol: str
    ) -> float:
        """
        Rough premium estimate for ATM weekly options.
        This is an approximation — actual premium varies.
        """
        # ATM weekly options typically trade at 0.5-1% of underlying
        if symbol == "NIFTY":
            est = price * 0.006  # ~0.6% of Nifty price
        else:
            est = price * 0.005  # ~0.5% of Sensex price

        return round(est, 0)

    def _build_option_reason(
        self, signal_type, option_type, symbol,
        strike, expiry, trigger_level, levels
    ) -> str:
        """
        Build a clear, simple explanation for Nitish.
        No jargon — plain trading language.
        """
        pdh = levels.get("prev_day_high", 0)
        pdl = levels.get("prev_day_low", 0)
        pwh = levels.get("prev_week_high", 0)
        pwl = levels.get("prev_week_low", 0)

        trigger_name  = trigger_level.get("name", "key level") if trigger_level else "key level"
        trigger_price = trigger_level.get("price", 0) if trigger_level else 0

        if signal_type == "BUY":
            return (
                f"Market structure is BULLISH. "
                f"Price is near {trigger_name} ({trigger_price:,.0f}) which is acting as support. "
                f"BUY {symbol} {strike} CE expiring {expiry}. "
                f"This is a CALL option — you profit when {symbol} goes UP. "
                f"Key levels to watch: PDH {pdh:,.0f} is resistance, PDL {pdl:,.0f} is your safety net."
            )
        else:
            return (
                f"Market structure is BEARISH. "
                f"Price is near {trigger_name} ({trigger_price:,.0f}) which is acting as resistance. "
                f"BUY {symbol} {strike} PE expiring {expiry}. "
                f"This is a PUT option — you profit when {symbol} goes DOWN. "
                f"Key levels to watch: PDL {pdl:,.0f} is target zone, PDH {pdh:,.0f} is your stop area."
            )

    def format_levels_summary(self, levels: dict, symbol: str) -> str:
        """
        Format key levels into a clean summary for the dashboard.
        """
        pdh  = levels.get("prev_day_high", 0)
        pdl  = levels.get("prev_day_low", 0)
        pwh  = levels.get("prev_week_high", 0)
        pwl  = levels.get("prev_week_low", 0)
        dop  = levels.get("day_open", 0)
        dh   = levels.get("day_high", 0)
        dl   = levels.get("day_low", 0)

        return {
            "symbol": symbol,
            "today": {
                "open": dop,
                "high": dh,
                "low":  dl
            },
            "previous_day": {
                "high": pdh,
                "low":  pdl
            },
            "previous_week": {
                "high": pwh,
                "low":  pwl
            }
        }
