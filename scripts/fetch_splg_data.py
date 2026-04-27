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
            super().__init__("/openapi/market-data/stock/batch-bars", version='v2', method="POST", body_params={})
            self.add_body_params("symbols", [symbol])
            self.add_body_params("timespan", "M60") # Hourly
            self.add_body_params("count", 1000)
            self.add_body_params("category", "US_STOCK")

    req = BatchBarsRequest("SPLG")
    try:
        res = await asyncio.to_thread(api_client.get_response, req)
        if res.status_code == 200:
            data = res.json()
            bars = []
            if isinstance(data, dict):
                if "bars" in data:
                    bars = data["bars"]
                elif "data" in data:
                    for item in data["data"]:
                        if item.get("symbol") == "SPLG":
                            bars = item.get("bars", [])
                            break
            
            print(f"Fetched {len(bars)} bars")
            if bars:
                df = pl.from_dicts(bars)
                # Map columns
                rename_map = {"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
                rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
                if rename_map:
                    df = df.rename(rename_map)
                
                if "timestamp" in df.columns and df["timestamp"].dtype in [pl.Int64, pl.Float64]:
                    df = df.with_columns(pl.from_epoch(pl.col("timestamp"), time_unit="ms"))
                
                df.write_parquet("data/raw/SPLG_historical.parquet")
                print("Saved to data/raw/SPLG_historical.parquet")
        else:
            print(f"Failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_splg())
