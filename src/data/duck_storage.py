import duckdb
import polars as pl
import os
import structlog
from src.config import settings

logger = structlog.get_logger()

class DuckDBStorage:
    """
    DuckDB Storage Layer: Manages persistence of OHLCV data.
    Native integration with Polars/Arrow for high-speed I/O.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DUCKDB_PATH
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = duckdb.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        """Initializes the OHLCV table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                timestamp TIMESTAMP_NS,
                symbol VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (timestamp, symbol)
            )
        """)
        logger.info("DuckDB: Storage initialized", path=self.db_path)

    def insert_ohlcv(self, df: pl.DataFrame):
        """Inserts OHLCV data into DuckDB from a Polars DataFrame."""
        if df.is_empty():
            return
        
        # Use DuckDB's native Polars integration
        # We use 'ON CONFLICT DO UPDATE' or similar if we want to handle duplicates
        # But for now, we'll use a simple insert or replace logic
        try:
            # Register the Polars DataFrame as a virtual table
            self.conn.register("df_temp", df)
            
            # Insert with conflict handling (timestamp + symbol is PK)
            self.conn.execute("""
                INSERT OR REPLACE INTO ohlcv 
                SELECT timestamp, symbol, open, high, low, close, volume FROM df_temp
            """)
            logger.info("DuckDB: Data inserted", count=len(df))
        except Exception as e:
            logger.error("DuckDB: Insertion failed", error=str(e))
        finally:
            self.conn.unregister("df_temp")

    def fetch_ohlcv(self, symbol: str, limit: int = 150) -> pl.DataFrame:
        """Fetches the last N bars for a symbol as a Polars DataFrame."""
        query = f"""
            SELECT * FROM ohlcv 
            WHERE symbol = '{symbol}'
            ORDER BY timestamp DESC
            LIMIT {limit}
        """
        try:
            # DuckDB's pl() method returns a Polars DataFrame directly
            return self.conn.execute(query).pl().sort("timestamp")
        except Exception as e:
            logger.error("DuckDB: Fetch failed", error=str(e))
            return pl.DataFrame()

    def close(self):
        self.conn.close()
