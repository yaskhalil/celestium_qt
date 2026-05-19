import asyncio
from src.core.notifier import TelegramNotifier
from src.config import settings

async def test_notifier():
    print(f"Telegram Enabled: {settings.TELEGRAM_ENABLED}")
    print(f"Bot Token: {settings.TELEGRAM_BOT_TOKEN[:5]}...")
    print(f"Chat ID: {settings.TELEGRAM_CHAT_ID}")
    
    notifier = TelegramNotifier()
    print("Sending test message...")
    await notifier.notify_system_status("🧪 Test Notification from CelestiumQT")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(test_notifier())
