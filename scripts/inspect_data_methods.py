import os
from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from dotenv import load_dotenv

load_dotenv()

def inspect_data_client():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.set_token(token)
    
    data_client = DataClient(api_client)
    
    print("--- DataClient.market_data Methods ---")
    for attr in dir(data_client.market_data):
        if not attr.startswith("_"):
            print(f"data_client.market_data.{attr}")

if __name__ == "__main__":
    inspect_data_client()
