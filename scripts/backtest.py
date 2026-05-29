import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
import json
import structlog
from src.core.backtest_engine import BacktestEngine
from src.features.regime import add_regime_features

from src.config import settings

logger = structlog.get_logger()

def run_backtest():
    """Main entry point for running the recalibrated backtest."""
    # 1. Load Data from Databento Parquet
    data_path = f"data/processed/databento_{settings.SYMBOL.lower()}.parquet"
    
    if not os.path.exists(data_path):
        logger.warning(f"Data missing at {data_path}. Running Databento ingestion...")
        from scripts.ingest_databento import ingest_historical_data
        ingest_historical_data(days=365)
        
    if not os.path.exists(data_path):
        logger.error("Data ingestion failed. Check your DATABENTO_API_KEY.")
        return

    logger.info("Loading Data from Databento Parquet", path=data_path)
    df = pl.read_parquet(data_path)

    # Run with actual model predictions and actual Hurst exponent
    settings.SIGNAL_THRESHOLD = 0.5

    # Ensure features are present
    if "atr" not in df.columns:
        df = add_regime_features(df)

    # 2. Initialize Engine (Uses settings.STARTING_BALANCE)
    engine = BacktestEngine()
    
    # 3. Run Simulation
    report = engine.run(df)
    
    # 4. Save and Print Report
    report_path = "data/backtest_report.json"
    trades_path = "data/trades.json"
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)
        
    with open(trades_path, "w") as f:
        # Convert datetime objects to strings for JSON serialization
        serialized_trades = []
        for t in engine.trades:
            trade_copy = t.copy()
            trade_copy["entry_time"] = trade_copy["entry_time"].isoformat()
            trade_copy["exit_time"] = trade_copy["exit_time"].isoformat()
            serialized_trades.append(trade_copy)
        json.dump(serialized_trades, f, indent=4)
        
    logger.info("Backtest Complete", report=report, trades_saved=len(engine.trades))
    print("\n--- APEX AUDIT REPORT ---")
    for k, v in report.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    run_backtest()
