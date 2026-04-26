import os
import json
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from dotenv import load_dotenv

load_dotenv()

def test_user_snippet():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    print(f"Testing with Key: {app_key}")
    
    api_client = ApiClient(app_key, app_secret, "us")
    # Removed UAT endpoint to test Production default

    trade_client = TradeClient(api_client)
    res = trade_client.account_v2.get_account_list()
    if res.status_code == 200:
        print("Success!", json.dumps(res.json(), indent=2))
    else:
        print("Error:", res.status_code, res.text)

if __name__ == "__main__":
    test_user_snippet()
