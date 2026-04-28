import os
import json
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from dotenv import load_dotenv

load_dotenv()

def inspect_client():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.set_token(token)
    
    trade_client = TradeClient(api_client)
    
    print("--- TradeClient Attributes ---")
    for attr in dir(trade_client):
        if not attr.startswith("_"):
            print(f"trade_client.{attr}")
            
    if hasattr(trade_client, "account"):
        print("\n--- TradeClient.account Methods ---")
        for attr in dir(trade_client.account):
            if not attr.startswith("_"):
                print(f"trade_client.account.{attr}")

    if hasattr(trade_client, "account_v2"):
        print("\n--- TradeClient.account_v2 Methods ---")
        for attr in dir(trade_client.account_v2):
            if not attr.startswith("_"):
                print(f"trade_client.account_v2.{attr}")

    if hasattr(trade_client, "order_v2"):
        print("\n--- TradeClient.order_v2 Methods ---")
        for attr in dir(trade_client.order_v2):
            if not attr.startswith("_"):
                print(f"trade_client.order_v2.{attr}")

if __name__ == "__main__":
    inspect_client()
