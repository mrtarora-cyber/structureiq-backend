# StructureIQ - Risk Engine & Position Sizer
# Protects Nitish's capital on every single trade

import logging
from datetime import datetime
from config import settings
from database import supabase
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

class PositionSizer:
    """
    Risk Management Engine.
    
    Before any signal is sent to Nitish, this engine checks:
    1. Maximum risk per trade (1% of capital = ₹100)
    2. Daily loss limit (2% of capital = ₹200)
    3. Maximum drawdown (5% of capital = ₹500)
    4. Whether capital is sufficient for F&O
    5. Recommended position size in lots
    """

    def __init__(self):
        self.capital        = settings.CAPITAL           # ₹10,000
        self.risk_pct       = settings.RISK_PER_TRADE    # 1%
        self.daily_limit    = settings.DAILY_LOSS_LIMIT  # 2%
        self.max_drawdown   = settings.MAX_DRAWDOWN      # 5%

    def validate_signal(self, signal: dict) -> dict:
        """
        Validate a signal against all risk rules.
        Returns approval status and position sizing.
        """
        entry  = signal.get("entry_price", 0)
        sl     = signal.get("stop_loss", 0)
        symbol = signal.get("symbol", "")

        if not entry or not sl:
            return {"approved": False, "reason": "Invalid entry or stop loss"}

        # Calculate risk per unit
        risk_per_unit = abs(entry - sl)
        if risk_per_unit == 0:
            return {"approved": False, "reason": "Stop loss equals entry"}

        # Maximum money we can risk on this trade
        max_risk_amount = self.capital * (self.risk_pct / 100)  # ₹100

        # Check daily loss limit
        daily_pnl = self._get_today_pnl()
        daily_limit_amount = self.capital * (self.daily_limit / 100)  # ₹200

        if daily_pnl <= -daily_limit_amount:
            return {
                "approved": False,
                "reason": f"Daily loss limit reached. Today's loss: ₹{abs(daily_pnl):.0f}. Limit: ₹{daily_limit_amount:.0f}. No more trades today.",
                "daily_pnl": daily_pnl
            }

        # Calculate recommended lots
        # Nifty lot size = 25, Sensex lot size = 10
        lot_size = 25 if symbol == "NIFTY" else 10
        risk_per_lot = risk_per_unit * lot_size

        # How many lots can we afford?
        recommended_lots = int(max_risk_amount / risk_per_lot)

        # Minimum options premium check
        # Assume minimum premium ₹50/unit for ATM options
        min_premium = 50
        cost_of_1_lot = min_premium * lot_size

        # Capital warnings
        warnings = []

        if cost_of_1_lot > self.capital * 0.5:
            warnings.append(
                f"⚠️ WARNING: 1 lot costs approx ₹{cost_of_1_lot:.0f} "
                f"which is {cost_of_1_lot/self.capital*100:.0f}% of your capital. "
                f"This is HIGH RISK for ₹{self.capital:.0f} capital."
            )

        if recommended_lots < 1:
            warnings.append(
                f"⚠️ Position size less than 1 lot. "
                f"Risk per lot (₹{risk_per_lot:.0f}) exceeds max risk (₹{max_risk_amount:.0f}). "
                f"Consider tighter stop loss."
            )
            recommended_lots = 1  # Minimum 1 lot if trading

        return {
            "approved": True,
            "capital": self.capital,
            "max_risk_amount": round(max_risk_amount, 2),
            "risk_per_unit": round(risk_per_unit, 2),
            "risk_per_lot": round(risk_per_lot, 2),
            "lot_size": lot_size,
            "recommended_lots": recommended_lots,
            "daily_pnl": daily_pnl,
            "remaining_daily_risk": round(daily_limit_amount + daily_pnl, 2),
            "warnings": warnings,
            "risk_summary": (
                f"Risk: ₹{max_risk_amount:.0f} | "
                f"Lots: {recommended_lots} | "
                f"Daily P&L: ₹{daily_pnl:.0f}"
            )
        }

    def calculate_position_size(
        self,
        entry: float,
        stop_loss: float,
        symbol: str
    ) -> dict:
        """
        Standalone position size calculator.
        Used by the dashboard position sizer widget.
        """
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit == 0:
            return {"error": "Stop loss cannot equal entry price"}

        max_risk     = self.capital * (self.risk_pct / 100)
        lot_size     = 25 if symbol == "NIFTY" else 10
        risk_per_lot = risk_per_unit * lot_size
        lots         = max(1, int(max_risk / risk_per_lot))

        return {
            "symbol":           symbol,
            "entry":            entry,
            "stop_loss":        stop_loss,
            "risk_per_unit":    round(risk_per_unit, 2),
            "risk_per_lot":     round(risk_per_lot, 2),
            "lot_size":         lot_size,
            "recommended_lots": lots,
            "total_risk":       round(risk_per_lot * lots, 2),
            "max_allowed_risk": round(max_risk, 2),
            "capital":          self.capital
        }

    def _get_today_pnl(self) -> float:
        """Get today's total P&L from trade journal"""
        try:
            today = datetime.now(IST).date().isoformat()
            result = supabase.table("trade_journal")\
                .select("pnl")\
                .eq("trade_date", today)\
                .execute()
            trades = result.data
            return sum(t.get("pnl", 0) or 0 for t in trades)
        except Exception as e:
            logger.error(f"Error fetching today's PnL: {e}")
            return 0.0

    def get_risk_status(self) -> dict:
        """
        Full risk status report for the dashboard.
        Shows how much risk capacity is remaining today.
        """
        daily_pnl         = self._get_today_pnl()
        daily_limit_amt   = self.capital * (self.daily_limit / 100)
        drawdown_limit    = self.capital * (self.max_drawdown / 100)
        remaining_risk    = daily_limit_amt + daily_pnl
        limit_breached    = daily_pnl <= -daily_limit_amt

        status = "SAFE"
        if daily_pnl <= -daily_limit_amt * 0.5:
            status = "CAUTION"
        if limit_breached:
            status = "STOP TRADING"

        return {
            "capital":           self.capital,
            "daily_pnl":         round(daily_pnl, 2),
            "daily_limit":       round(daily_limit_amt, 2),
            "remaining_risk":    round(remaining_risk, 2),
            "drawdown_limit":    round(drawdown_limit, 2),
            "limit_breached":    limit_breached,
            "status":            status,
            "message": (
                "All clear — trade safely." if status == "SAFE"
                else "Approaching daily loss limit — be careful."
                if status == "CAUTION"
                else "Daily loss limit reached — STOP TRADING TODAY."
            )
        }
