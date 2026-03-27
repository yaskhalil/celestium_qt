import asyncio
import structlog
from src.core.engine import Engine
from src.config import settings

# Setup logging
structlog.configure()
logger = structlog.get_logger()

async def main():
    """Async entry point (The Event Loop)"""
    logger.info("Initializing CelestiumQT", user=settings.RITHMIC_USERNAME)
    
    # Initialize the core engine
    engine = Engine()
    
    # Start the event loop
    try:
        await engine.run()
    except asyncio.CancelledError:
        logger.info("CelestiumQT shutting down...")
    except Exception as e:
        logger.error("Critical failure", error=str(e))

if __name__ == "__main__":
    asyncio.run(main())
