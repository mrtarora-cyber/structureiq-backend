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
    
    A signal is only generated when:
    1. Clear trend is identified (BULLISH or BEARISH)
    2. Price is near a key zone (Support/Demand or Resistance/Supply)
    3. A structure event confirms the move (BOS or CHoCH)
    4. Risk/Reward ratio is at least 1.5
    5. Confidence score is at least 60/100
    """

    def generate_signal(
        self,
        symbol: str,
        structure: dict,
        price_data: dict
    ) -> dict | None:
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
        last_event   = structure.get("last_event", "")

        if trend == "RANGE":
            logger.info(f"{symbol}: Market in range — no signal")
            return None

        # Check for BUY signal conditions
        if trend == "BULLISH":
            signal = self._check_buy_signal(
                symbol, current_price, structure,
                events, sr_zones, sd_zones
            )
            if signal:
                return signal

        # Check for SELL signal conditions
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
    ) -> dict | None:
        """
        BUY signal conditions:
        - Bullish trend (HH + HL structure)
        - Price near support or demand zone
        - BOS or CHoCH bullish event present
        - Good RR ratio
        """
        reasons = []
        confidence = 0

        # Condition 1: Bullish trend confirmed
        trend = structure.get("trend")
        if trend == "BULLISH":
            confidence += 25
            reasons.append("market is in a bullish structure with higher highs and higher lows")

        # Condition 2: Recent bullish structure event
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

        # Condition 3: Price near support or demand zone
        nearest_zone = self._find_nearest_zone(
            price, sr_zones + sd_zones,
            zone_types=["SUPPORT", "DEMAND"],
            direction="above"
        )
        if nearest_zone:
            distance_pct = abs(price - nearest_zone["price"]) / price * 100
            if distance_pct < 0.5:  # Within 0.5% of zone
                confidence += 30
                reasons.append(
                    f"price is near a key {nearest_zone['type'].lower()} zone at {nearest_zone['price']:.2f}"
                )

        # Condition 4: Check swing structure
        classified = structure.get("classified_swings", [])
        recent_lows = [s for s in classified[-6:] if s["type"] == "LOW"]
        if recent_lows and recent_lows[-1]["label"] == "HL":
            confidence += 20
            reasons.append(
                f"price formed a higher low at {recent_lows[-1]['price']:.2f} confirming bullish bias"
            )

        # Only generate signal if confidence is high enough
        if confidence < settings.MIN_CONFIDENCE:
            logger.info(f"{symbol}: BUY confidence too low ({confidence}) — skipping")
            return None

        # Calculate entry, stop loss, targets
        stop_loss = self._calculate_stop_loss(
            price, structure, "BUY"
        )
        if not stop_loss:
            return None

        risk = price - stop_loss
        target_1 = round(price + risk * 1.5, 2)
        target_2 = round(price + risk * 2.5, 2)
        rr_ratio = round((target_1 - price) / risk, 2)

        if rr_ratio < settings.MIN_RR_RATIO:
            logger.info(f"{symbol}: RR ratio too low ({rr_ratio}) — skipping")
            return None

        # Build human-readable explanation
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
    ) -> dict | None:
        """
        SELL signal conditions:
        - Bearish trend (LH + LL structure)
        - Price near resistance or supply zone
        - BOS or CHoCH bearish event present
        - Good RR ratio
        """
        reasons = []
        confidence = 0

        # Condition 1: Bearish trend confirmed
        if structure.get("trend") == "BEARISH":
            confidence += 25
            reasons.append("market is in a bearish structure with lower highs and lower lows")

        # Condition 2: Recent bearish structure event
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

        # Condition 3: Price near resistance or supply zone
        nearest_zone = self._find_nearest_zone(
            price, sr_zones + sd_zones,
            zone_types=["RESISTANCE", "SUPPLY"],
            direction="below"
        )
        if nearest_zone:
            distance_pct = abs(price - nearest_zone["price"]) / price * 100
            if distance_pct < 0.5:
                confidence += 30
                reasons.append(
                    f"price is near a key {nearest_zone['type'].lower()} zone at {nearest_zone['price']:.2f}"
                )

        # Condition 4: Check swing structure
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

        # Calculate entry, stop loss, targets
        stop_loss = self._calculate_stop_loss(
            price, structure, "SELL"
        )
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

    def _calculate_stop_loss(
        self, price: float, structure: dict, direction: str
    ) -> float | None:
        """
        Calculate stop loss based on recent swing points
        BUY:  SL = below last swing low
        SELL: SL = above last swing high
        """
        classified = structure.get("classified_swings", [])

        if direction == "BUY":
            lows = [s for s in classified if s["type"] == "LOW"]
            if not lows:
                return None
            last_low = lows[-1]["price"]
            # Add small buffer below swing low
            return round(last_low * 0.999, 2)

        else:  # SELL
            highs = [s for s in classified if s["type"] == "HIGH"]
            if not highs:
                return None
            last_high = highs[-1]["price"]
            # Add small buffer above swing high
            return round(last_high * 1.001, 2)

    def _find_nearest_zone(
        self, price: float, zones: list,
        zone_types: list, direction: str
    ) -> dict | None:
        """Find the nearest relevant price zone"""
        relevant = [z for z in zones if z.get("type") in zone_types]
        if not relevant:
            return None

        # Sort by distance from current price
        relevant.sort(
            key=lambda z: abs(z["price"] - price)
        )
        return relevant[0] if relevant else None

    def _build_explanation(
        self, signal_type: str, symbol: str,
        reasons: list, confidence: int
    ) -> str:
        """
        Build a human-readable explanation for the signal.
        Example output:
        'BUY signal on NIFTY (Confidence: 80/100) —
         market is in a bullish structure with higher highs and higher lows,
         a bullish Break of Structure occurred at 22150.00,
         and price is near a key support zone at 22100.00.'
        """
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
