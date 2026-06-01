import pytest
import respx
import httpx
from src.core.notifier import TelegramNotifier
from src.config import settings

@pytest.mark.asyncio
async def test_telegram_notifier_disabled():
    """Verify that when Telegram is disabled, no HTTP request is made."""
    notifier = TelegramNotifier()
    notifier.enabled = False
    notifier.token = "fake_token"
    notifier.chat_id = "fake_chat_id"

    # If it was enabled and tried to hit the API, respx would raise an error if not mocked,
    # or we can mock it and assert it was not called.
    async with respx.mock:
        route = respx.post(f"https://api.telegram.org/botfake_token/sendMessage")
        await notifier.notify("Test Message")
        assert not route.called

@pytest.mark.asyncio
async def test_telegram_notifier_enabled_success():
    """Verify that when Telegram is enabled, a correct HTTP POST is sent."""
    notifier = TelegramNotifier()
    notifier.enabled = True
    notifier.token = "fake_token"
    notifier.chat_id = "fake_chat_id"
    notifier.base_url = f"https://api.telegram.org/bot{notifier.token}/sendMessage"

    async with respx.mock as mock:
        mock_route = mock.post(notifier.base_url).mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        
        await notifier.notify("Hello World")
        
        assert mock_route.called
        request = mock_route.calls[0].request
        import json
        payload = json.loads(request.content)
        assert payload["chat_id"] == "fake_chat_id"
        assert payload["text"] == "Hello World"
        assert payload["parse_mode"] == "Markdown"

@pytest.mark.asyncio
async def test_telegram_notifier_api_error():
    """Verify that API errors are handled without raising exceptions."""
    notifier = TelegramNotifier()
    notifier.enabled = True
    notifier.token = "fake_token"
    notifier.chat_id = "fake_chat_id"
    notifier.base_url = f"https://api.telegram.org/bot{notifier.token}/sendMessage"

    async with respx.mock as mock:
        mock_route = mock.post(notifier.base_url).mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        
        # This should not raise an exception, just log the error internally
        await notifier.notify("Hello World")
        assert mock_route.called

@pytest.mark.asyncio
async def test_telegram_notifier_missing_config():
    """Verify that notify returns early if token or chat_id is missing."""
    notifier = TelegramNotifier()
    notifier.enabled = True
    notifier.token = ""
    notifier.chat_id = ""

    async with respx.mock as mock:
        await notifier.notify("Hello World")
        assert len(mock.calls) == 0

@pytest.mark.asyncio
async def test_telegram_notifier_formatters():
    """Verify all helper methods build and send expected Markdown payloads."""
    notifier = TelegramNotifier()
    notifier.enabled = True
    notifier.token = "fake_token"
    notifier.chat_id = "fake_chat_id"
    notifier.base_url = f"https://api.telegram.org/bot{notifier.token}/sendMessage"

    async with respx.mock as mock:
        mock_route = mock.post(notifier.base_url).mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        # 1. Startup Notification
        await notifier.notify_startup(balance=358.00, shadow_mode=True)
        assert mock_route.called
        startup_text = mock_route.calls[-1].request.content.decode()
        assert "CELESTIUM QT ONLINE" in startup_text
        assert "SHADOW MODE" in startup_text
        assert "$358.00" in startup_text

        # 2. Shutdown Notification
        await notifier.notify_shutdown(balance=360.50)
        assert mock_route.called
        shutdown_text = mock_route.calls[-1].request.content.decode()
        assert "CELESTIUM QT OFFLINE" in shutdown_text
        assert "$360.50" in shutdown_text

        # 3. Daily Recap Notification
        await notifier.notify_daily_recap(pnl=2.50, balance=360.50, trades=3, vetos=1, payout_capital=10.00)
        assert mock_route.called
        recap_text = mock_route.calls[-1].request.content.decode()
        assert "DAILY MARKET CLOSE" in recap_text
        assert "$2.50" in recap_text
        assert "$360.50" in recap_text
        assert "$10.00" in recap_text

        # 4. Trade Execution Notification
        await notifier.notify_trade(symbol="SPLG", side="BUY", qty=5.0, price=60.25, order_id="ord_123", tp=62.00, sl=59.50)
        assert mock_route.called
        trade_text = mock_route.calls[-1].request.content.decode()
        assert "TRADE EXECUTED" in trade_text
        assert "SPLG" in trade_text
        assert "BUY" in trade_text
        assert "5.0" in trade_text
        assert "$60.25" in trade_text
        assert "ord_123" in trade_text

        # 5. Risk Veto Notification
        await notifier.notify_risk_veto(reason="Vetoed: hurst threshold not met")
        assert mock_route.called
        veto_text = mock_route.calls[-1].request.content.decode()
        assert "RISK VETO" in veto_text
        assert "hurst threshold not met" in veto_text
