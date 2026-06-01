import asyncio
import sys
import os

# Ensure the root of the project is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.execution.alpaca_client import AlpacaClient

async def run_live_connection_test():
    print("--- TESTING ALPACA CONNECTIVITY ---")
    print(f"Base URL: {settings.ALPACA_BASE_URL}")
    print(f"API Key ID: {settings.ALPACA_API_KEY[:6]}...")
    
    client = AlpacaClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        base_url=settings.ALPACA_BASE_URL
    )
    
    # 1. Test Account Details
    try:
        print("\nFetching Account details...")
        account = await client.get_account()
        print("✅ Account details fetched successfully!")
        print(f"Account Number: {account.get('account_number')}")
        print(f"Status: {account.get('status')}")
        print(f"Cash Balance: ${float(account.get('cash', 0.0)):.2f}")
        print(f"Equity: ${float(account.get('equity', 0.0)):.2f}")
        print(f"Trading Blocked: {account.get('trading_blocked')}")
    except Exception as e:
        print(f"❌ Failed to fetch Account details: {e}")
        
    # 2. Test Market Data (Last Price of SPLG)
    try:
        print(f"\nFetching last trade price for {settings.SYMBOL}...")
        price = await client.get_last_price(settings.SYMBOL)
        if price is not None:
            print(f"✅ Market data fetched successfully!")
            print(f"Last Price of {settings.SYMBOL}: ${price:.2f}")
        else:
            print(f"⚠️ Last Price fetched returned None (market feed empty or closed)")
    except Exception as e:
        print(f"❌ Failed to fetch market data: {e}")

if __name__ == "__main__":
    asyncio.run(run_live_connection_test())
