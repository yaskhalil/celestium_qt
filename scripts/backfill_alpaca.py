import asyncio
import structlog
from src.config import settings
from src.execution.alpaca_client import AlpacaClient
from src.data.ingestion import AlpacaIngestor

logger = structlog.get_logger()

async def main():
    logger.info("Initializing Alpaca Backfill...")
    client = AlpacaClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        base_url=settings.ALPACA_BASE_URL
    )
    
    ingestor = AlpacaIngestor(client)
    
    # 30 days = 30 * 24 * 60 minutes
    # We fetch a bit more because Alpaca limits API calls, but the method fetches up to 10000 bars per call
    # Alpaca max limit per request is 10000.
    # We will fetch 9900 minutes (~25 trading days).
    symbol = settings.SYMBOL
    lookback = 9900
    
    try:
        logger.info(f"Fetching {lookback} minutes of data for {symbol}...")
        await ingestor.fetch_and_persist(symbol, lookback_minutes=lookback)
        logger.info("Backfill complete.")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
