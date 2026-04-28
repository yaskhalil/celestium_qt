import asyncio
import os
import json
import uuid
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from dotenv import load_dotenv

load_dotenv()

async def test_trading():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    account_id = "7QHCR3S6PNACFGMQJTNK4DJPV9"
    
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.set_token(token)
    
    trade_client = TradeClient(api_client)
    
    # Try a place order with manual request
    print(f"Testing Order Placement for NIO (Manual)...")
    from webull.core.request import ApiRequest
    try:
        body = {
            "account_id": account_id,
            "client_combo_order_id": uuid.uuid4().hex,
            "combo_type": "NORMAL",
            "new_orders": [{
                "client_order_id": uuid.uuid4().hex,
                "instrument_type": "EQUITY",
                "symbol": "NIO",
                "market": "US",
                "side": "BUY",
                "order_type": "LIMIT",
                "limit_price": "1.00", # NIO is $6+, so $1 is very safe
                "quantity": "1",
                "time_in_force": "DAY",
                "support_trading_session": "CORE"
            }]
        }
        
        req = ApiRequest("/openapi/trade/stock/order/place", version="v2", method="POST", body_params=body)
        res = await asyncio.to_thread(api_client.get_response, req)
        
        if res.status_code == 200:
            print("PLACE SUCCESS!", json.dumps(res.json(), indent=2))
        else:
            print(f"PLACE FAILED: {res.status_code} {res.text}")
            
    except Exception as e:
        print(f"PLACE ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_trading())
