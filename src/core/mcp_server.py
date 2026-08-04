from mcp.server.fastmcp import FastMCP
from src.core.oracle import AccountState
import json

# Initialize the MCP Server named 'celestium-state'
mcp = FastMCP("celestium-state")

# Load the persisted account state (falls back to a fresh default state
# when data/account_state.json does not exist yet).
state = AccountState.load()

@mcp.tool()
def get_account_summary() -> str:
    """Returns a high-level summary of the Apex account status."""
    status = "✅ ACTIVE" if state.is_trading_allowed() else "❌ VETOED"
    return f"Balance: ${state.balance} | Day PnL: ${state.current_daily_pnl} | Status: {status}"

@mcp.resource("account://current_state")
def account_resource() -> str:
    """Provides the full raw JSON state of the account."""
    return state.model_dump_json()

if __name__ == "__main__":
    mcp.run()
