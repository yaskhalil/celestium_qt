from mcp.server.fastmcp import FastMCP
from src.core.oracle import AccountState
import json

# Initialize the MCP Server named 'celestium-state'
mcp = FastMCP("celestium-state")

# In a real app, you'd load this from a JSON file or Redis
state = AccountState(balance=27250.0, daily_pnl=150.0)

@mcp.tool()
def get_account_summary() -> str:
    """Returns a high-level summary of the Apex account status."""
    status = "✅ ACTIVE" if state.is_eligible_for_trade() else "❌ VETOED"
    return f"Balance: ${state.balance} | Day PnL: ${state.daily_pnl} | Status: {status}"

@mcp.resource("account://current_state")
def account_resource() -> str:
    """Provides the full raw JSON state of the account."""
    return state.model_dump_json()

if __name__ == "__main__":
    mcp.run()
