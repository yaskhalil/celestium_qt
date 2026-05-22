import httpx
import structlog
import asyncio
from src.config import settings

logger = structlog.get_logger()

class TelegramNotifier:
    """
    Asynchronous Telegram Notifier for real-time system alerts.
    """
    def __init__(self):
        self.enabled = settings.TELEGRAM_ENABLED
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    async def notify(self, message: str):
        """Sends a message to the configured Telegram chat."""
        if not self.enabled:
            return

        if not self.token or not self.chat_id:
            logger.warning("Telegram: Enabled but token or chat_id is missing")
            return

        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                response = await client.post(self.base_url, json=payload, timeout=5.0)
                if response.status_code != 200:
                    logger.error("Telegram: API Error", status=response.status_code, text=response.text)
                else:
                    logger.debug("Telegram: Message sent successfully")
        except Exception as e:
            logger.error("Telegram: Failed to send notification", error=str(e))

    async def notify_startup(self, balance: float, shadow_mode: bool):
        """Alerts when bot boots up."""
        mode = "🟢 LIVE TRADING" if not shadow_mode else "🟡 SHADOW MODE"
        msg = (
            f"🚀 *CELESTIUM QT ONLINE*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"*Status:* `{mode}`\n"
            f"*Starting Balance:* `${balance:.2f}`\n"
            f"*Target:* `{settings.SYMBOL}`\n"
            f"*Timeframe:* `5Min`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Monitoring market for optimal regime..."
        )
        await self.notify(msg)

    async def notify_shutdown(self, balance: float):
        """Alerts when bot goes offline."""
        msg = (
            f"🛑 *CELESTIUM QT OFFLINE*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"*Final Balance:* `${balance:.2f}`\n"
            f"System safely halted."
        )
        await self.notify(msg)

    async def notify_daily_recap(self, pnl: float, balance: float, trades: int):
        """Sends EOD summary."""
        emoji = "📈" if pnl >= 0 else "📉"
        msg = (
            f"{emoji} *DAILY MARKET CLOSE*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"*Daily PNL:* `${pnl:.2f}`\n"
            f"*Total Trades:* `{trades}`\n"
            f"*Ending Balance:* `${balance:.2f}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Awaiting next session..."
        )
        await self.notify(msg)

    async def notify_trade(self, symbol: str, side: str, qty: float, price: float, order_id: str = "N/A", tp: float = 0.0, sl: float = 0.0):
        """Specific formatter for trade executions."""
        emoji = "🟢" if side == "BUY" else "🔴"
        msg = (
            f"{emoji} *TRADE EXECUTED*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"*Symbol:* `{symbol}`\n"
            f"*Action:* `{side}`\n"
            f"*Quantity:* `{qty}`\n"
            f"*Fill Price:* `${price:.2f}`\n"
            f"*Take Profit:* `${tp:.2f}`\n"
            f"*Stop Loss:* `${sl:.2f}`\n"
            f"*Order ID:* `{order_id}`"
        )
        await self.notify(msg)

    async def notify_risk_veto(self, reason: str):
        """Alerts when a trade is blocked by the Oracle."""
        msg = f"🛡 *RISK VETO*\n━━━━━━━━━━━━━━━\n{reason}"
        await self.notify(msg)
