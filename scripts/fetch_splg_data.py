import asyncio
import os
import polars as pl
from webull.core.client import ApiClient
from webull.core.request import ApiRequest
from dotenv import load_dotenv

load_dotenv()

async def fetch_splg():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    api_client = ApiClient(app_key, app_secret, "us")
    
    class BatchBarsRequest(ApiRequest):
        def __init__(self, symbol: str):
            super().__init__("/openapi/market-data/stock/batch-bars", version='v2', method="GET")
            self.add_query_param("symbols", symbol)
            self.add_query_param("timespan", "1m")
            self.add_query_param("count", "1000") # Max allowed usually
            self.add_query_param("category", "STOCK")

    req = BatchBarsRequest("SPLG")
    try:
        res = await asyncio.to_thread(api_client.get_response, req)
        if res.status_code == 200:
            data = res.json()
            bars = data.get("bars", [])
            print(f"Fetched {len(bars)} bars")
            if bars:
                df = pl.from_dicts(bars)
                df.write_parquet("data/raw/SPLG_historical.parquet")
                print("Saved to data/raw/SPLG_historical.parquet")
        else:
            print(f"Failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_splg())
