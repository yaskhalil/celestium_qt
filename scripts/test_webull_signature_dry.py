import asyncio
import json
import polars as pl
from src.execution.webull_client import WebullClient

async def test_signature():
    # Dummy keys
    client = WebullClient(
        app_key="test_key",
        app_secret="test_secret",
        access_token="test_token"
    )
    
    symbol = "AAPL"
    
    print("\n--- Testing get_last_price ---")
    try:
        # We expect this to fail but we want to see the "illegal request line" or URL
        price = await client.get_last_price(symbol)
        print(f"Price: {price}")
    except Exception as e:
        print(f"Caught expected error: {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(test_signature())
