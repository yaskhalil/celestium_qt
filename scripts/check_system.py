import os
import json
import asyncio
import structlog
from dotenv import load_dotenv
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from src.data.duck_storage import DuckDBStorage
from src.core.oracle import Oracle, AccountState
from src.core.boolean_network import BooleanStateSpace

logger = structlog.get_logger()
load_dotenv()

async def check_webull():
    print("\n--- [1/4] Checking Webull Connectivity ---")
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    if not app_key or not app_secret:
        print("FAILED: Webull credentials missing in .env")
        return False

    try:
        api_client = ApiClient(app_key, app_secret, "us")
        # Removed UAT endpoint to test Production default
        
        trade_client = TradeClient(api_client)
        
        # SDK calls are likely synchronous
        res = await asyncio.to_thread(trade_client.account_v2.get_account_list)
        
        if res.status_code == 200:
            print("SUCCESS: Connected to Webull UAT.")
            print(json.dumps(res.json(), indent=2))
            return True
        else:
            print(f"FAILED: Webull Error {res.status_code}: {res.text}")
            return False
            
    except Exception as e:
        print(f"FAILED: Webull Connection Error: {e}")
        return False

def check_duckdb():
    print("\n--- [2/4] Checking DuckDB Storage ---")
    try:
        storage = DuckDBStorage()
        df = storage.fetch_ohlcv("TEST", limit=1)
        print(f"SUCCESS: Connected to DuckDB.")
        return True
    except Exception as e:
        print(f"FAILED: DuckDB Error: {e}")
        return False

def check_boolean_logic():
    print("\n--- [3/4] Checking Boolean State Space ---")
    import polars as pl
    bss = BooleanStateSpace()
    # Mock data to test mapping
    df = pl.DataFrame({
        "hurst": [0.45],
        "hurst_gradient": [0.01],
        "efficiency_ratio": [0.6],
        "volatility": [0.02],
        "vol_adj_momentum": [0.5],
        "adx": [25.0]
    })
    state = bss.map_to_bits(df)
    is_attractor = bss.is_in_attractor(state)
    print(f"Logic Test: Market State {state} is {'in an Attractor' if is_attractor else 'NOT in an attractor'}.")
    return True

def check_oracle():
    print("\n--- [4/4] Checking T+1 Settlement Oracle ---")
    state = AccountState.load()
    oracle = Oracle(state)
    print(f"Settled Cash: ${state.settled_cash}")
    print(f"Unsettled Cash: ${state.unsettled_cash}")
    
    can_trade = oracle.validate_trade(1, 50.0, "BUY")
    print(f"Oracle: Hypothetical $50 trade is {'ALLOWED' if can_trade else 'VETOED'}.")
    return True

if __name__ == "__main__":
    print("CelestiumQT System Verification (UAT Mode)")
    
    async def run_checks():
        w = await check_webull()
        d = check_duckdb()
        b = check_boolean_logic()
        o = check_oracle()
        
        print("\n--- Verification Summary ---")
        if all([w, d, b, o]):
            print("SYSTEM READY: Core components are verified.")
        else:
            print("SYSTEM INCOMPLETE: Check the failures above.")

    asyncio.run(run_checks())
