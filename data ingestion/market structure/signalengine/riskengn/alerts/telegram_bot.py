# StructureIQ - Telegram Alert System
# Sends instant trading signals to Nitish's phone

import httpx
import logging
from datetime import datetime
from config import settings
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

class TelegramAlert:
    """
    Sends formatted trading signals to Nitish via Telegram.
    
    Every alert includes:
    - Signal type (BUY/SELL)
    - Symbol (NIFTY/SENSEX)
    - Entry price
    - Stop Loss
    - Target 1 & Target 2
    - Risk/Reward ratio
    - Confidence score
    - Human readable explanation
    - Risk warning if needed
    """

    BASE_URL = "https://api.telegram.org"

    def __init__(self):
        self.token   = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    async def send_signal(self, signal: dict):
        """
        Send a complete trading signal alert to Nitish
        """
        message = self._format_signal(signal)
        await self._send_message(message)

    async def send_message(self, text: str):
        """Send a plain text message"""
        await self._send_message(text)

    def _format_signal(self, signal: dict) -> str:
        """
        Format signal into a beautiful Telegram message.
        Uses emoji for quick visual scanning on mobile.
        """
        signal_type = signal.get("signal_type", "")
        symbol      = signal.get("symbol", "")
        entry       = signal.get("entry_price", 0)
        sl          = signal.get("stop_loss", 0)
        t1          = signal.get("target_1", 0)
        t2          = signal.get("target_2", 0)
        rr          = signal.get("rr_ratio", 0)
        confidence  = signal.get("confidence", 0)
        explanation = signal.get("explanation", "")
        warnings    = signal.get("warnings", [])
        time_now    = datetime.now(IST).strftime("%H:%M:%S")

        # Emoji based on signal type
        if signal_type == "BUY":
            header     = "🟢 BUY SIGNAL"
            sl_label   = "🛑 Stop Loss"
            entry_icon = "📈"
        else:
            header     = "🔴 SELL SIGNAL"
            sl_label   = "🛑 Stop Loss"
            entry_icon = "📉"

        # Confidence bar visual
        filled  = int(confidence / 10)
        empty   = 10 - filled
        conf_bar = "█" * filled + "░" * empty

        message = f"""
╔══════════════════════╗
   {header}
   StructureIQ • {time_now} IST
╚══════════════════════╝

{entry_icon} *{symbol}* — {signal_type}

💰 Entry:     {entry:,.2f}
{sl_label}:  {sl:,.2f}
🎯 Target 1:  {t1:,.2f}
🎯 Target 2:  {t2:,.2f}

⚖️ Risk/Reward: {rr:.1f}R
📊 Confidence:  {confidence}/100
{conf_bar}

📝 *Why this signal?*
{explanation}

💼 *Risk Check*
• Max risk per trade: ₹{settings.CAPITAL * settings.RISK_PER_TRADE / 100:.0f}
• Daily limit: ₹{settings.CAPITAL * settings.DAILY_LOSS_LIMIT / 100:.0f}
"""

        # Add warnings if any
        if warnings:
            message += "\n⚠️ *Warnings*\n"
            for w in warnings:
                message += f"{w}\n"

        message += """
━━━━━━━━━━━━━━━━━━━━━━
⚡ Open Dhan and place manually
🚫 This is NOT auto-executed
━━━━━━━━━━━━━━━━━━━━━━"""

        return message

    async def _send_message(self, text: str):
        """
        Actually send the message via Telegram API
        """
        url = f"{self.BASE_URL}/bot{self.token}/sendMessage"

        payload = {
            "chat_id":    self.chat_id,
            "text":       text,
            "parse_mode": "Markdown"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info("Telegram alert sent successfully")
                else:
                    logger.error(
                        f"Telegram error: {response.status_code} — {response.text}"
                    )
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    async def send_market_open(self):
        """Send market open notification every morning"""
        now = datetime.now(IST).strftime("%d %b %Y")
        await self._send_message(
            f"🔔 *StructureIQ Active*\n"
            f"Market is now open — {now}\n"
            f"Watching NIFTY & SENSEX for structure signals.\n"
            f"Stay focused Nitish! 📊"
        )

    async def send_market_close(self, daily_pnl: float):
        """Send end of day summary"""
        emoji = "✅" if daily_pnl >= 0 else "❌"
        await self._send_message(
            f"🔕 *Market Closed*\n"
            f"{emoji} Today's P&L: ₹{daily_pnl:,.2f}\n"
            f"StructureIQ going to sleep.\n"
            f"See you tomorrow at 9:15 AM! 🌙"
        )

    async def send_daily_limit_warning(self, pnl: float):
        """Alert when daily loss limit is approaching"""
        await self._send_message(
            f"⚠️ *RISK WARNING*\n"
            f"Daily loss is ₹{abs(pnl):,.2f}\n"
            f"Approaching your daily limit of "
            f"₹{settings.CAPITAL * settings.DAILY_LOSS_LIMIT / 100:.0f}\n"
            f"Consider stopping for today."
      )
