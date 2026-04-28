import asyncio
import os
import json
from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan
from dotenv import load_dotenv

load_dotenv()

async def test_dataclient():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    
    print(f"Testing DataClient with NVDA on PROD...")
    try:
        api_client = ApiClient(app_key, app_secret, "us")
        api_client.set_token(token)
        
        data_client = DataClient(api_client)
        
        symbol = "MSFT"
        print(f"Testing DataClient.get_corp_action with {symbol} on PROD...")
        res = await asyncio.to_thread(
            data_client.market_data.get_corp_action, 
            [symbol],
            ["DIVIDEND"]
        )
        if res.status_code == 200:
            print("SUCCESS (PROD)!", json.dumps(res.json(), indent=2))
        else:
            print(f"FAILED (PROD): {res.status_code} {res.text}")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_dataclient())
