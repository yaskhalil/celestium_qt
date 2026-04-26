import os
import json
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from dotenv import load_dotenv

load_dotenv()

def test_sdk_with_token():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    
    print(f"Testing SDK with Token: {token}")
    
    api_client = ApiClient(app_key, app_secret, "us")
    # Manually set the token in the client
    api_client.set_token(token)

    trade_client = TradeClient(api_client)
    
    try:
        # SDK get_account_list uses GET /openapi/account/list
        res = trade_client.account_v2.get_account_list()
        if res.status_code == 200:
            print("SUCCESS!", json.dumps(res.json(), indent=2))
        else:
            print(f"FAILED: {res.status_code} {res.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_sdk_with_token()
