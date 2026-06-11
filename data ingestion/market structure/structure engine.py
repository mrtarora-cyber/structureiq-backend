# StructureIQ - Market Structure Engine
# Detects: HH, HL, LH, LL, BOS, CHoCH, Trends, S/R Zones, Supply/Demand

import pandas as pd
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StructureEngine:
    """
    The core intelligence of StructureIQ.
    
    Given a list of candles, this engine:
    1. Finds swing highs and swing lows
    2. Classifies them as HH, HL, LH, LL
    3. Detects Break of Structure (BOS)
    4. Detects Change of Character (CHoCH)
    5. Identifies current trend
    6. Finds Support/Resistance zones
    7. Finds Supply/Demand zones
    """

    def __init__(self):
        # How many candles on each side to confirm a swing point
        self.swing_strength = 3

    def analyze(self, symbol: str, candles: list) -> dict:
        """
        Main analysis function.
        Input: list of candle dicts
        Output: complete market structure dict
        """
        if len(candles) < 20:
            return {"error": "Not enough candles"}

        # Convert to DataFrame for easy analysis
        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Step 1: Find all swing points
        swings = self._find_swings(df)

        # Step 2: Classify swings as HH/HL/LH/LL
        classified = self._classify_swings(swings)

        # Step 3: Detect BOS and CHoCH
        structure_events = self._detect_bos_choch(df, classified)

        # Step 4: Determine current trend
        trend = self._determine_trend(classified)

        # Step 5: Find Support and Resistance zones
        sr_zones = self._find_sr_zones(df, swings)

        # Step 6: Find Supply and Demand zones
        sd_zones = self._find_supply_demand(df, swings)

        # Step 7: Get last structure event
        last_event = structure_events[-1] if structure_events else {}

        return {
            "symbol": symbol,
            "trend": trend,
            "swings": swings[-10:],          # Last 10 swing points
            "classified_swings": classified[-10:],
            "structure_events": structure_events[-5:],
            "last_event": last_event.get("type", ""),
            "support_resistance": sr_zones,
            "supply_demand": sd_zones,
            "current_price": float(df["close"].iloc[-1]),
            "last_candle": {
                "open":  float(df["open"].iloc[-1]),
                "high":  float(df["high"].iloc[-1]),
                "low":   float(df["low"].iloc[-1]),
                "close": float(df["close"].iloc[-1]),
            },
            "analyzed_at": datetime.now().isoformat()
        }

    def _find_swings(self, df: pd.DataFrame) -> list:
        """
        Find swing highs and swing lows in price data.
        A swing high = candle with highest high among neighbors
        A swing low  = candle with lowest low among neighbors
        """
        swings = []
        n = self.swing_strength

        for i in range(n, len(df) - n):
            # Check swing high
            is_swing_high = all(
                df["high"].iloc[i] >= df["high"].iloc[i-j] and
                df["high"].iloc[i] >= df["high"].iloc[i+j]
                for j in range(1, n+1)
            )

            # Check swing low
            is_swing_low = all(
                df["low"].iloc[i] <= df["low"].iloc[i-j] and
                df["low"].iloc[i] <= df["low"].iloc[i+j]
                for j in range(1, n+1)
            )

            if is_swing_high:
                swings.append({
                    "index": i,
                    "type": "HIGH",
                    "price": float(df["high"].iloc[i]),
                    "timestamp": str(df["timestamp"].iloc[i])
                })

            if is_swing_low:
                swings.append({
                    "index": i,
                    "type": "LOW",
                    "price": float(df["low"].iloc[i]),
                    "timestamp": str(df["timestamp"].iloc[i])
                })

        # Sort by index
        swings.sort(key=lambda x: x["index"])
        return swings

    def _classify_swings(self, swings: list) -> list:
        """
        Classify swing points as HH, HL, LH, LL
        HH = Higher High (swing high above previous swing high)
        HL = Higher Low  (swing low above previous swing low)
        LH = Lower High  (swing high below previous swing high)
        LL = Lower Low   (swing low below previous swing low)
        """
        classified = []
        prev_high = None
        prev_low = None

        for swing in swings:
            if swing["type"] == "HIGH":
                if prev_high is None:
                    label = "HH"  # First high defaults to HH
                elif swing["price"] > prev_high:
                    label = "HH"  # Higher High = bullish
                else:
                    label = "LH"  # Lower High = bearish
                prev_high = swing["price"]

            else:  # LOW
                if prev_low is None:
                    label = "HL"  # First low defaults to HL
                elif swing["price"] > prev_low:
                    label = "HL"  # Higher Low = bullish
                else:
                    label = "LL"  # Lower Low = bearish
                prev_low = swing["price"]

            classified.append({**swing, "label": label})

        return classified

    def _detect_bos_choch(self, df: pd.DataFrame, classified: list) -> list:
        """
        Detect Break of Structure (BOS) and Change of Character (CHoCH)

        BOS = Price breaks a swing point IN THE DIRECTION of current trend
              (confirms trend continuation)

        CHoCH = Price breaks a swing point AGAINST the current trend
                (signals possible trend reversal)
        """
        events = []
        current_price = float(df["close"].iloc[-1])

        highs = [s for s in classified if s["type"] == "HIGH"]
        lows  = [s for s in classified if s["type"] == "LOW"]

        if len(highs) < 2 or len(lows) < 2:
            return events

        last_hh = next((s for s in reversed(highs) if s["label"] == "HH"), None)
        last_lh = next((s for s in reversed(highs) if s["label"] == "LH"), None)
        last_hl = next((s for s in reversed(lows)  if s["label"] == "HL"), None)
        last_ll = next((s for s in reversed(lows)  if s["label"] == "LL"), None)

        trend = self._determine_trend(classified)

        # BOS Bullish: price breaks above last HH in bullish trend
        if trend == "BULLISH" and last_hh:
            if current_price > last_hh["price"]:
                events.append({
                    "type": "BOS",
                    "direction": "BULLISH",
                    "price": last_hh["price"],
                    "description": f"Bullish BOS — price broke above {last_hh['price']:.2f}"
                })

        # BOS Bearish: price breaks below last LL in bearish trend
        if trend == "BEARISH" and last_ll:
            if current_price < last_ll["price"]:
                events.append({
                    "type": "BOS",
                    "direction": "BEARISH",
                    "price": last_ll["price"],
                    "description": f"Bearish BOS — price broke below {last_ll['price']:.2f}"
                })

        # CHoCH Bullish: price breaks above LH in bearish trend (reversal signal)
        if trend == "BEARISH" and last_lh:
            if current_price > last_lh["price"]:
                events.append({
                    "type": "CHoCH",
                    "direction": "BULLISH",
                    "price": last_lh["price"],
                    "description": f"Bullish CHoCH — possible reversal above {last_lh['price']:.2f}"
                })

        # CHoCH Bearish: price breaks below HL in bullish trend (reversal signal)
        if trend == "BULLISH" and last_hl:
            if current_price < last_hl["price"]:
                events.append({
                    "type": "CHoCH",
                    "direction": "BEARISH",
                    "price": last_hl["price"],
                    "description": f"Bearish CHoCH — possible reversal below {last_hl['price']:.2f}"
                })

        return events

    def _determine_trend(self, classified: list) -> str:
        """
        Determine current market trend based on swing structure
        BULLISH  = HH + HL pattern
        BEARISH  = LH + LL pattern
        RANGE    = Mixed / unclear
        """
        if len(classified) < 4:
            return "RANGE"

        recent = classified[-6:]  # Look at last 6 swing points

        highs = [s for s in recent if s["type"] == "HIGH"]
        lows  = [s for s in recent if s["type"] == "LOW"]

        if not highs or not lows:
            return "RANGE"

        hh_count = sum(1 for s in highs if s["label"] == "HH")
        hl_count = sum(1 for s in lows  if s["label"] == "HL")
        lh_count = sum(1 for s in highs if s["label"] == "LH")
        ll_count = sum(1 for s in lows  if s["label"] == "LL")

        bullish_score = hh_count + hl_count
        bearish_score = lh_count + ll_count

        if bullish_score > bearish_score + 1:
            return "BULLISH"
        elif bearish_score > bullish_score + 1:
            return "BEARISH"
        else:
            return "RANGE"

    def _find_sr_zones(self, df: pd.DataFrame, swings: list) -> list:
        """
        Find Support and Resistance zones from swing points
        Zones where price has reversed multiple times = strong S/R
        """
        zones = []
        tolerance = 0.003  # 0.3% price tolerance for zone clustering

        highs = [s for s in swings if s["type"] == "HIGH"]
        lows  = [s for s in swings if s["type"] == "LOW"]

        # Resistance zones from swing highs
        for h in highs[-8:]:
            price = h["price"]
            buffer = price * tolerance
            zones.append({
                "type": "RESISTANCE",
                "price_high": round(price + buffer, 2),
                "price_low":  round(price - buffer, 2),
                "price":      round(price, 2),
                "strength":   1
            })

        # Support zones from swing lows
        for l in lows[-8:]:
            price = l["price"]
            buffer = price * tolerance
            zones.append({
                "type": "SUPPORT",
                "price_high": round(price + buffer, 2),
                "price_low":  round(price - buffer, 2),
                "price":      round(price, 2),
                "strength":   1
            })

        # Merge nearby zones and increase strength
        merged = self._merge_zones(zones, tolerance)
        return merged

    def _find_supply_demand(self, df: pd.DataFrame, swings: list) -> list:
        """
        Find Supply and Demand zones
        Supply zone = area where price dropped sharply from (sellers waiting)
        Demand zone = area where price rose sharply from (buyers waiting)
        """
        zones = []

        for i in range(2, len(df) - 2):
            candle = df.iloc[i]
            prev   = df.iloc[i-1]
            next1  = df.iloc[i+1]

            body_size = abs(float(candle["close"]) - float(candle["open"]))
            avg_body  = df["close"].rolling(10).std().iloc[i]

            # Strong bullish candle = demand zone below it
            if (float(candle["close"]) > float(candle["open"]) and
                body_size > avg_body * 1.5):
                zones.append({
                    "type": "DEMAND",
                    "price_high": round(float(candle["open"]), 2),
                    "price_low":  round(float(candle["low"]),  2),
                    "price":      round((float(candle["open"]) + float(candle["low"])) / 2, 2),
                    "strength":   1
                })

            # Strong bearish candle = supply zone above it
            if (float(candle["close"]) < float(candle["open"]) and
                body_size > avg_body * 1.5):
                zones.append({
                    "type": "SUPPLY",
                    "price_high": round(float(candle["high"]), 2),
                    "price_low":  round(float(candle["open"]), 2),
                    "price":      round((float(candle["high"]) + float(candle["open"])) / 2, 2),
                    "strength":   1
                })

        # Return most recent zones only
        return zones[-10:]

    def _merge_zones(self, zones: list, tolerance: float) -> list:
        """Merge overlapping zones and count their strength"""
        if not zones:
            return []

        merged = []
        used = set()

        for i, zone in enumerate(zones):
            if i in used:
                continue
            strength = 1
            for j, other in enumerate(zones):
                if i == j or j in used:
                    continue
                if (zone["type"] == other["type"] and
                    abs(zone["price"] - other["price"]) / zone["price"] < tolerance * 3):
                    strength += 1
                    used.add(j)
            merged.append({**zone, "strength": strength})
            used.add(i)

        # Sort by strength descending
        merged.sort(key=lambda x: x["strength"], reverse=True)
        return merged[:10]  # Return top 10 zones
