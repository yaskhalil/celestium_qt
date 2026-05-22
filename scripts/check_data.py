import asyncio
from src.config import settings
from src.execution.alpaca_client import AlpacaClient

async def check_data():
    client = AlpacaClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        base_url=settings.ALPACA_BASE_URL
    )
    
    symbol = settings.SYMBOL
    print(f"--- Checking Alpaca Data Feed ---")
    print(f"Target: {symbol}")
    print(f"Timeframe: 5Min")
    
    # The bot needs at least 110 bars for the 100-period Hurst exponent and gradients
    df = await client.get_bars(symbol, timeframe="5Min", limit=200)
    
    bar_count = len(df)
    print(f"Bars Retrieved: {bar_count}")
    
    if bar_count >= 110:
        print("✅ STATUS: READY. The bot has enough historical data to compute all ML features.")
    else:
        print("❌ STATUS: NOT READY.")
        print(f"The XGBoost model requires a minimum of 110 bars to calculate the Hurst Exponent and ATR features.")
        if bar_count == 0:
            print("Reason: Alpaca's free 'iex' feed may not have recent volume for this asset, or you have invalid API keys.")
            
    await client.close()

if __name__ == "__main__":
    # Disable structlog output for this simple diagnostic script
    import logging
    logging.getLogger().setLevel(logging.CRITICAL)
    asyncio.run(check_data())
