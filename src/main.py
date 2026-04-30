import asyncio
import structlog
from src.execution.webull_client import WebullClient
from src.core.engine import ScheduledEngine
from src.core.oracle import AccountState
from src.config import settings

# Setup logging
structlog.configure()
logger = structlog.get_logger()

def verify_timezone():
    """Verify that the required timezone data is available."""
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("America/New_York")
    except Exception:
        logger.error("Timezone data missing. Please install 'tzdata' package: pip install tzdata")
        raise RuntimeError("Missing timezone data for America/New_York")

async def main():
    """Async entry point (The Event Loop)"""
    verify_timezone()
    logger.info("Initializing CelestiumQT (Hybrid Mode: Databento + Webull)")
    
    # 1. Initialize native WebullClient
    webull_client = WebullClient(
        app_key=settings.WEBULL_APP_KEY,
        app_secret=settings.WEBULL_APP_SECRET,
        access_token=settings.WEBULL_ACCESS_TOKEN
    )
    
    # 2. Load Persistent Account State
    state = AccountState.load()
    
    # 3. Initialize the scheduled engine
    engine = ScheduledEngine(webull_client, state)
    engine.start()
    
    # Start the event loop
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("CelestiumQT shutting down...")
    except Exception as e:
        logger.error("Critical failure", error=str(e))
    finally:
        # Stop scheduler and save state
        await engine.stop()
        state.save()
        await webull_client.close()

if __name__ == "__main__":
    asyncio.run(main())
