# StructureIQ - Signal Builder
# Generates trading signals from market structure analysis

import logging
from datetime import datetime
from config import settings
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

class SignalBuilder:
    """
    Generates trading signals based on market structure.
    """

    def generate_signal(
        self,
        symbol: str,
        structure: dict,
        price_data: dict
    ):
        """
        Main signal generation function.
        Returns a signal dict or None if no signal found.
        """
        if not structure or not price_data:
            return None

        trend        = structure.get("trend", "RANGE")
        current_price = price_data.get("last_price", 0)
        events       = structure.get("structure_events", [])
        sr_zones     = structure.get("support_resistance", [])
        sd_zones     = structure.get("supply_demand", [])

        if trend == "RANGE":
            logger.info(f"{symbol}: Market in range — no signal")
            return None

        if trend == "BULLISH":
            signal = self._check_buy_signal(
                symbol, current_price, structure,
                events, sr_zones, sd_zones
            )
            if signal:
                return signal

        if trend == "BEARISH":
            signal = self._check_sell_signal(
                symbol, current_price, structure,
                events, sr_zones, sd_zones
            )
            if signal:
                return signal

        return None

    def _check_buy_signal(
        self, symbol, price, structure,
        events, sr_zones, sd_zones
    ):
        reasons = []
        confidence = 0

        trend = structure.get("trend")
        if trend == "BULLISH":
            confidence += 25
            reasons.append("market is in a bullish structure with higher highs and higher lows")

        bullish_events = [
            e for e in events
            if e.get("direction") == "BULLISH"
        ]
        if bullish_events:
            last = bullish_events[-1]
            confidence += 25
            if last["type"] == "BOS":
                reasons.append(f"a bullish Break of Structure occurred at {last['price']:.2f}")
            elif last["type"] == "CHoCH":
                reasons.append(f"a Change of Character signaled a bullish reversal at {last['price']:.2f}")

        nearest_zone = self._find_nearest_zone(
            price, sr_zones + sd_zones,
            zone_types=["SUPPORT", "DEMAND"]
        )
        if nearest_zone:
            distance_pct = abs(price - nearest_zone["price"]) / price * 100
            if distance_pct < 0.5:
                confidence += 30
                reasons.append(
                    f"price is near a key {nearest_zone['type'].lower()} zone at {nearest_zone['price']:.2f}"
                )

        classified = structure.get("classified_swings", [])
        recent_lows = [s for s in classified[-6:] if s["type"] == "LOW"]
        if recent_lows and recent_lows[-1]["label"] == "HL":
            confidence += 20
            reasons.append(
                f"price formed a higher low at {recent_lows[-1]['price']:.2f} confirming bullish bias"
            )

        if confidence < settings.MIN_CONFIDENCE:
            logger.info(f"{symbol}: BUY confidence too low ({confidence}) — skipping")
            return None

        stop_loss = self._calculate_stop_loss(price, structure, "BUY")
        if not stop_loss:
            return None

        risk = price - stop_loss
        target_1 = round(price + risk * 1.5, 2)
        target_2 = round(price + risk * 2.5, 2)
        rr_ratio = round((target_1 - price) / risk, 2)

        if rr_ratio < settings.MIN_RR_RATIO:
            logger.info(f"{symbol}: RR ratio too low ({rr_ratio}) — skipping")
            return None

        explanation = self._build_explanation("BUY", symbol, reasons, confidence)

        return {
            "symbol": symbol,
            "signal_type": "BUY",
            "timeframe": settings.PRIMARY_TIMEFRAME,
            "entry_price": round(price, 2),
            "stop_loss": round(stop_loss, 2),
            "target_1": target_1,
            "target_2": target_2,
            "rr_ratio": rr_ratio,
            "confidence": confidence,
            "explanation": explanation,
            "status": "ACTIVE",
            "created_at": datetime.now(IST).isoformat()
        }

    def _check_sell_signal(
        self, symbol, price, structure,
        events, sr_zones, sd_zones
    ):
        reasons = []
        confidence = 0

        if structure.get("trend") == "BEARISH":
            confidence += 25
            reasons.append("market is in a bearish structure with lower highs and lower lows")

        bearish_events = [
            e for e in events
            if e.get("direction") == "BEARISH"
        ]
        if bearish_events:
            last = bearish_events[-1]
            confidence += 25
            if last["type"] == "BOS":
                reasons.append(f"a bearish Break of Structure occurred at {last['price']:.2f}")
            elif last["type"] == "CHoCH":
                reasons.append(f"a Change of Character signaled a bearish reversal at {last['price']:.2f}")

        nearest_zone = self._find_nearest_zone(
            price, sr_zones + sd_zones,
            zone_types=["RESISTANCE", "SUPPLY"]
        )
        if nearest_zone:
            distance_pct = abs(price - nearest_zone["price"]) / price * 100
            if distance_pct < 0.5:
                confidence += 30
                reasons.append(
                    f"price is near a key {nearest_zone['type'].lower()} zone at {nearest_zone['price']:.2f}"
                )

        classified = structure.get("classified_swings", [])
        recent_highs = [s for s in classified[-6:] if s["type"] == "HIGH"]
        if recent_highs and recent_highs[-1]["label"] == "LH":
            confidence += 20
            reasons.append(
                f"price formed a lower high at {recent_highs[-1]['price']:.2f} confirming bearish bias"
            )

        if confidence < settings.MIN_CONFIDENCE:
            logger.info(f"{symbol}: SELL confidence too low ({confidence}) — skipping")
            return None

        stop_loss = self._calculate_stop_loss(price, structure, "SELL")
        if not stop_loss:
            return None

        risk = stop_loss - price
        target_1 = round(price - risk * 1.5, 2)
        target_2 = round(price - risk * 2.5, 2)
        rr_ratio = round((price - target_1) / risk, 2)

        if rr_ratio < settings.MIN_RR_RATIO:
            return None

        explanation = self._build_explanation("SELL", symbol, reasons, confidence)

        return {
            "symbol": symbol,
            "signal_type": "SELL",
            "timeframe": settings.PRIMARY_TIMEFRAME,
            "entry_price": round(price, 2),
            "stop_loss": round(stop_loss, 2),
            "target_1": target_1,
            "target_2": target_2,
            "rr_ratio": rr_ratio,
            "confidence": confidence,
            "explanation": explanation,
            "status": "ACTIVE",
            "created_at": datetime.now(IST).isoformat()
        }

    def _calculate_stop_loss(self, price, structure, direction):
        classified = structure.get("classified_swings", [])

        if direction == "BUY":
            lows = [s for s in classified if s["type"] == "LOW"]
            if not lows:
                return None
            last_low = lows[-1]["price"]
            return round(last_low * 0.999, 2)

        else:
            highs = [s for s in classified if s["type"] == "HIGH"]
            if not highs:
                return None
            last_high = highs[-1]["price"]
            return round(last_high * 1.001, 2)

    def _find_nearest_zone(self, price, zones, zone_types):
        relevant = [z for z in zones if z.get("type") in zone_types]
        if not relevant:
            return None
        relevant.sort(key=lambda z: abs(z["price"] - price))
        return relevant[0] if relevant else None

    def _build_explanation(self, signal_type, symbol, reasons, confidence):
        if not reasons:
            reasons = ["multiple confluence factors aligned"]

        reason_text = ", ".join(reasons[:-1])
        if len(reasons) > 1:
            reason_text += f", and {reasons[-1]}"
        else:
            reason_text = reasons[0]

        return (
            f"{signal_type} signal on {symbol} "
            f"(Confidence: {confidence}/100) — "
            f"{reason_text}."
      )
