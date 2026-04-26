import asyncio
import structlog
from webull.core.client import ApiClient
from src.core.engine import ScheduledEngine
from src.core.oracle import AccountState
from src.config import settings

# Setup logging
structlog.configure()
logger = structlog.get_logger()

async def main():
    """Async entry point (The Event Loop)"""
    logger.info("Initializing CelestiumQT (Webull Mode)")
    
    # 1. Initialize Webull Client
    api_client = ApiClient(settings.WEBULL_APP_KEY, settings.WEBULL_APP_SECRET, "us")
    
    # Check if UAT is explicitly requested
    is_uat = False 
    if is_uat:
        logger.info("Engine: Running in UAT Environment")
        api_client.add_endpoint("us", "us-openapi-alb.uat.webullbroker.com")
    else:
        logger.warning("Engine: RUNNING IN PRODUCTION ENVIRONMENT (SHADOW MODE ACTIVE)")
    
    # 2. Load Persistent Account State
    state = AccountState.load()
    
    # 3. Initialize the scheduled engine
    engine = ScheduledEngine(api_client, state)
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

if __name__ == "__main__":
    asyncio.run(main())
