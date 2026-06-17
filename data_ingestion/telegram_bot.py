
async def send_signal_with_options(
        self, signal: dict, option_rec: dict, key_levels: dict
    ):
        """Send signal with full options recommendation"""
        signal_type = signal.get("signal_type", "")
        symbol      = signal.get("symbol", "")
        entry       = signal.get("entry_price", 0)
        sl          = signal.get("stop_loss", 0)
        t1          = signal.get("target_1", 0)
        t2          = signal.get("target_2", 0)
        rr          = signal.get("rr_ratio", 0)
        confidence  = signal.get("confidence", 0)
        time_now    = datetime.now(IST).strftime("%H:%M:%S")

        # Options details
        option_name   = option_rec.get("option_name", "") if option_rec else ""
        option_reason = option_rec.get("option_reason", "") if option_rec else ""
        est_premium   = option_rec.get("estimated_premium", 0) if option_rec else 0

        # Key levels
        pdh = key_levels.get("prev_day_high", 0)
        pdl = key_levels.get("prev_day_low", 0)
        pwh = key_levels.get("prev_week_high", 0)
        pwl = key_levels.get("prev_week_low", 0)

        emoji = "🟢" if signal_type == "BUY" else "🔴"

        message = f"""
{emoji} {signal_type} SIGNAL — {symbol}
StructureIQ • {time_now} IST

OPTION TO BUY:
{option_name}
Est. Premium: ~₹{est_premium:.0f}

TRADE LEVELS:
Entry:    {entry:,.0f}
Stop Loss: {sl:,.0f}
Target 1:  {t1:,.0f}
Target 2:  {t2:,.0f}
R:R = {rr:.1f}R | Confidence: {confidence}%

KEY LEVELS TODAY:
Prev Day High: {pdh:,.0f}
Prev Day Low:  {pdl:,.0f}
Prev Week High: {pwh:,.0f}
Prev Week Low:  {pwl:,.0f}

WHY THIS TRADE:
{option_reason}

Open Dhan → Search {option_name} → Buy
This is NOT auto-executed
"""
        await self._send_message(message)
