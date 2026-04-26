import os
import json
import asyncio
from dotenv import load_dotenv
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

load_dotenv()

async def check_account_details():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    if not app_key or not app_secret:
        print("FAILED: Webull credentials missing in .env")
        return

    try:
        api_client = ApiClient(app_key, app_secret, "us")
        trade_client = TradeClient(api_client)
        
        # 1. Get Account List
        print("--- Fetching Account List ---")
        res = await asyncio.to_thread(trade_client.account_v2.get_account_list)
        
        if res.status_code != 200:
            print(f"FAILED: Webull Error {res.status_code}: {res.text}")
            return
            
        accounts = res.json()
        if not accounts:
            print("No accounts found.")
            return
            
        account_id = accounts[0].get("account_id")
        print(f"Using Account ID: {account_id}")
        
        # 2. Get Account Details (Balance / Buying Power)
        print("\n--- Fetching Account Balance ---")
        res_account = await asyncio.to_thread(
            trade_client.account_v2.get_account_balance,
            account_id
        )
        if res_account.status_code == 200:
            print(json.dumps(res_account.json(), indent=2))
        else:
            print(f"Failed to fetch account details: {res_account.text}")

        # 3. Get Account Positions
        print("\n--- Fetching Current Positions ---")
        res_positions = await asyncio.to_thread(
            trade_client.account_v2.get_account_position,
            account_id
        )
        if res_positions.status_code == 200:
            positions = res_positions.json()
            if not positions:
                print("No current positions held.")
            else:
                for pos in positions:
                    print(json.dumps(pos, indent=2))
        else:
            print(f"Failed to fetch positions: {res_positions.text}")

    except Exception as e:
        print(f"FAILED: Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_account_details())
