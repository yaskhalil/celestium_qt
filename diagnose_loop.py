import asyncio
import structlog
import os
from src.config import settings
from src.core.logging_setup import setup_logging
from src.core.engine import ScheduledEngine
from src.execution.alpaca_client import AlpacaClient

setup_logging()
logger = structlog.get_logger()

async def run_diagnostics():
    print("Starting diagnostics harness...")
    # Overriding setting to test if it's the threshold
    settings.SIGNAL_THRESHOLD = 0.4
    
    # Initialize Alpaca client
    alpaca_client = AlpacaClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        base_url=settings.ALPACA_BASE_URL
    )
    
    engine = ScheduledEngine(alpaca_client)
    
    print("Running tick_signal()...")
    await engine.tick_signal()
    
    print("Veto logs:", engine.veto_logs)

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
