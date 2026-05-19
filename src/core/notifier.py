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

    async def notify_trade(self, symbol: str, side: str, qty: float, price: float, order_id: str = "N/A"):
        """Specific formatter for trade executions."""
        emoji = "🚀" if side == "BUY" else "💰"
        msg = (
            f"{emoji} *TRADE EXECUTED*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"*Symbol:* `{symbol}`\n"
            f"*Side:* `{side}`\n"
            f"*Quantity:* `{qty}`\n"
            f"*Price:* `${price:.2f}`\n"
            f"*Order ID:* `{order_id}`"
        )
        await self.notify(msg)

    async def notify_risk_veto(self, reason: str):
        """Alerts when a trade is blocked by the Oracle."""
        msg = f"🛡 *RISK VETO*\n━━━━━━━━━━━━━━━\n{reason}"
        await self.notify(msg)

    async def notify_system_status(self, status: str):
        """Alerts for system events (Start, Stop, Errors)."""
        msg = f"⚙️ *SYSTEM STATUS*\n━━━━━━━━━━━━━━━\n{status}"
        await self.notify(msg)
