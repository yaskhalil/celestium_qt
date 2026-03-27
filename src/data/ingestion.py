import asyncio
import structlog
from datetime import datetime
from async_rithmic import RithmicClient
from src.config import settings
from src.data.pipeline import LiveBuffer

logger = structlog.get_logger()

class RithmicIngestor:
    """
    The 'Eyes': Establishes connection to Apex's servers via Rithmic protocol.
    Handles authentication and pushes incoming 1m bars into the LiveBuffer.
    """
    
    def __init__(self, buffer: LiveBuffer):
        self.buffer = buffer
        self.client: RithmicClient = None
        self.is_running = False

    async def connect(self):
        """Authenticates with Rithmic."""
        logger.info("Ingestor: Connecting to Rithmic...", user=settings.RITHMIC_USERNAME)
        
        # Note: System name for Apex is typically "Rithmic Paper Trading" 
        # or "Apex" depending on the specific environment provided by Rithmic.
        self.client = RithmicClient(
            user=settings.RITHMIC_USERNAME,
            password=settings.RITHMIC_PASSWORD,
            system_name=settings.RITHMIC_SYSTEM_NAME
        )
        
        try:
            await self.client.connect()
            logger.info("Ingestor: Rithmic Connected.")
        except Exception as e:
            logger.error("Ingestor: Connection Failed", error=str(e))
            raise

    async def _on_bar_update(self, bar):
        """Callback for incoming 1m bar data."""
        try:
            # Rithmic bar object structure (Simplified based on async_rithmic docs)
            # Typically contains: timestamp, open, high, low, close, volume
            self.buffer.add_bar(
                timestamp=bar.timestamp,
                o=bar.open,
                h=bar.high,
                l=bar.low,
                c=bar.close,
                v=bar.volume
            )
            logger.debug("Ingestor: 1m Bar Received", timestamp=bar.timestamp, close=bar.close)
        except Exception as e:
            logger.error("Ingestor: Error processing bar", error=str(e))

    async def start_streaming(self, symbol: str = settings.SYMBOL, exchange: str = settings.EXCHANGE):
        """Subscribes to 1m bars for the target symbol."""
        if not self.client:
            await self.connect()
            
        logger.info("Ingestor: Subscribing to 1m bars", symbol=symbol)
        
        # Using the history plant to stream real-time bars (some Rithmic setups use ticker for ticks)
        # async_rithmic often provides a dedicated bar subscription method
        try:
            await self.client.history.subscribe_bars(
                symbol=symbol,
                exchange=exchange,
                bar_type="MINUTE",
                bar_count=1,
                callback=self._on_bar_update
            )
            self.is_running = True
            
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error("Ingestor: Streaming failed", error=str(e))
            self.is_running = False

    def stop(self):
        self.is_running = False
        if self.client:
             # In a real scenario, we'd call await self.client.disconnect()
             pass
