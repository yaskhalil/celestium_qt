import websockets
import asyncio
import json
import structlog
from src.config import settings

logger = structlog.get_logger()

class Ingestion:
    """Async WebSocket/Rithmic client"""
    
    def __init__(self, uri: str = "wss://api.rithmic.com/v1/stream"):
        self.uri = uri
        self.connection = None
        self.running = False

    async def connect(self):
        """Establishes connection to Rithmic."""
        logger.info("Connecting to Rithmic API...", uri=self.uri)
        try:
            self.connection = await websockets.connect(self.uri)
            logger.info("Connection established.")
        except Exception as e:
            logger.error("Failed to connect", error=str(e))

    async def stream_data(self, symbols: list):
        """Streams real-time market data."""
        if not self.connection:
            await self.connect()
        
        self.running = True
        while self.running:
            try:
                # Mock Rithmic subscribe and receive logic
                # message = await self.connection.recv()
                # data = json.loads(message)
                # logger.debug("Received Tick", data=data)
                
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error("Streaming error", error=str(e))
                await asyncio.sleep(5) # Retry after 5 seconds

    def stop(self):
        self.running = False
