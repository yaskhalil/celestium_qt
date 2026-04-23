import os
import structlog
import polars as pl
import asyncio
from dotenv import load_dotenv
from src.execution.webull_client import WebullClient
from src.data.duck_storage import DuckDBStorage
from src.core.oracle import Oracle, AccountState
from src.core.boolean_network import BooleanStateSpace

logger = structlog.get_logger()
load_dotenv()

async def check_webull():
    print("\n--- [1/4] Checking Webull Connectivity ---")
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    account_id = os.getenv("WEBULL_ACCOUNT_ID")
    
    if not app_key or not app_secret or not account_id:
        print("FAILED: Webull credentials missing in .env")
        return False

    client = WebullClient(app_key, app_secret)
    
    try:
        res = await client.get_account_balance(account_id=account_id)
        print(f"SUCCESS: Connected to Webull.")
        # Balance response handling
        balance = res[0] if isinstance(res, list) else res
        print(f"Account ID: {account_id}")
        print(f"Net Liquidity: ${balance.get('net_liquidity', 'N/A')}")
        await client.close()
        return True
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
    bss = BooleanStateSpace()
    # Mock data to test mapping
    df = pl.DataFrame({
        "close": [110.0],
        "sma_20": [100.0],
        "hurst": [0.6],
        "adx": [30.0]
    })
    
    try:
        state = bss.map_to_bits(df)
        is_valid = bss.is_in_attractor(state)
        print(f"Logic Test: Market State {state} is {'in' if is_valid else 'NOT in'} an Attractor.")
        print("SUCCESS: Boolean logic functional.")
        return True
    except Exception as e:
        print(f"FAILED: Boolean Logic Error: {e}")
        return False

def check_oracle():
    print("\n--- [4/4] Checking T+1 Settlement Oracle ---")
    state = AccountState.load()
    oracle = Oracle(state)
    print(f"Settled Cash: ${state.settled_cash}")
    print(f"Unsettled Cash: ${state.unsettled_cash}")
    
    # Test a hypothetical $50 purchase
    can_trade = oracle.validate_trade(quantity=1, price=50.0, side="BUY", current_hurst=0.5)
    print(f"Oracle: Hypothetical $50 trade is {'ALLOWED' if can_trade else 'VETOED'}.")
    return True

if __name__ == "__main__":
    print("CelestiumQT System Verification")
    
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
