import asyncio
import os
import polars as pl
from webull.core.client import ApiClient
from webull.core.request import ApiRequest
from dotenv import load_dotenv

load_dotenv()

async def test_category(symbol: str, category: str):
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    api_client = ApiClient(app_key, app_secret, "us")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    if token:
        api_client.set_token(token)
    
    class BatchBarsRequest(ApiRequest):
        def __init__(self, symbol: str, cat: str):
            super().__init__("/openapi/market-data/stock/batch-bars", version='v2', method="POST", body_params={})
            self.add_body_params("symbols", [symbol])
            self.add_body_params("timespan", "M60") # Hourly
            self.add_body_params("count", 5)
            self.add_body_params("category", cat)

    print(f"Testing {symbol} with category: {category}")
    req = BatchBarsRequest(symbol, category)
    try:
        res = await asyncio.to_thread(api_client.get_response, req)
        if res.status_code == 200:
            print(f"SUCCESS for {symbol} / {category}!")
            print(res.json())
            return True
        else:
            print(f"FAILED for {symbol} / {category}: {res.status_code} {res.text}")
            return False
    except Exception as e:
        print(f"Error for {symbol} / {category}: {e}")
        return False

async def main():
    for symbol in ["SPLG", "NVDA"]:
        for cat in ["US_STOCK", "US_ETF"]:
            await test_category(symbol, cat)

if __name__ == "__main__":
    asyncio.run(main())
