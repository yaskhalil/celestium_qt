import asyncio
import os
import json
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from dotenv import load_dotenv

load_dotenv()

async def check_subscriptions():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.set_token(token)
    
    trade_client = TradeClient(api_client)
    
    try:
        print("Fetching app subscriptions...")
        res = await asyncio.to_thread(trade_client.account.get_app_subscriptions)
        if res.status_code == 200:
            print("App Subscriptions:", json.dumps(res.json(), indent=2))
        else:
            print(f"Failed to get subscriptions: {res.status_code} {res.text}")
            
        print("\nFetching account list...")
        res = await asyncio.to_thread(trade_client.account_v2.get_account_list)
        if res.status_code == 200:
            accounts = res.json()
            print("Account List:", json.dumps(accounts, indent=2))
            
            for acc in accounts:
                acc_id = acc.get("account_id")
                print(f"\nFetching profile for account {acc_id}...")
                # SDK might require account_id
                res_profile = await asyncio.to_thread(trade_client.account.get_account_profile, acc_id)
                if res_profile.status_code == 200:
                    print(f"Profile {acc_id}:", json.dumps(res_profile.json(), indent=2))
                else:
                    print(f"Failed to get profile for {acc_id}: {res_profile.status_code} {res_profile.text}")

                print(f"Fetching balance for account {acc_id}...")
                res_balance = await asyncio.to_thread(trade_client.account_v2.get_account_balance, acc_id)
                if res_balance.status_code == 200:
                    print(f"Balance {acc_id}:", json.dumps(res_balance.json(), indent=2))
                else:
                    print(f"Failed to get balance for {acc_id}: {res_balance.status_code} {res_balance.text}")

                print(f"Fetching positions for account {acc_id}...")
                res_pos = await asyncio.to_thread(trade_client.account_v2.get_account_position, acc_id)
                if res_pos.status_code == 200:
                    print(f"Positions {acc_id}:", json.dumps(res_pos.json(), indent=2))
                else:
                    print(f"Failed to get positions for {acc_id}: {res_pos.status_code} {res_pos.text}")
        else:
            print(f"Failed to get account list: {res.status_code} {res.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_subscriptions())
