import asyncio
import structlog
from async_rithmic import RithmicClient
from src.core.engine import Engine
from src.core.oracle import AccountState
from src.config import settings

# Setup logging
structlog.configure()
logger = structlog.get_logger()

async def main():
    """Async entry point (The Event Loop)"""
    logger.info("Initializing CelestiumQT", user=settings.RITHMIC_USERNAME)
    
    # 1. Initialize Rithmic Client
    client = RithmicClient(
        user=settings.RITHMIC_USERNAME,
        password=settings.RITHMIC_PASSWORD,
        system_name="Rithmic Paper Trading"
    )
    
    # 2. Load Persistent Account State
    state = AccountState.load()
    
    # 3. Initialize the core engine with components
    engine = Engine(client, state)
    
    # Start the event loop
    try:
        # In a real run, you'd await client.connect() here
        await engine.run(symbol="NQZ4")
    except asyncio.CancelledError:
        logger.info("CelestiumQT shutting down...")
    except Exception as e:
        logger.error("Critical failure", error=str(e))
    finally:
        # Save state on exit
        state.save()

if __name__ == "__main__":
    asyncio.run(main())
