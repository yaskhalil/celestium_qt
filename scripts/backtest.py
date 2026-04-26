import polars as pl
import os
import json
import structlog
from src.core.backtest_engine import BacktestEngine
from src.features.regime import add_regime_features

from src.config import settings

logger = structlog.get_logger()

def run_backtest():
    """Main entry point for running the recalibrated backtest."""
    data_path = "data/processed/training_data.parquet"
    
    if not os.path.exists(data_path):
        logger.error("Processed data not found. Run training/data prep first.", path=data_path)
        return

    # 1. Load Data
    logger.info("Loading Data", path=data_path)
    df = pl.read_parquet(data_path)
    
    # NORMALIZE FOR $400 ACCOUNT:
    # Divide NQ prices (~18,000) by 400 to simulate a ~$45 stock (e.g. SPLG-like)
    if df["close"].mean() > 1000:
        logger.info("Normalizing NQ prices for $400 Equity Backtest (Price / 400)")
        df = df.with_columns([
            pl.col("open") / 400,
            pl.col("high") / 400,
            pl.col("low") / 400,
            pl.col("close") / 400,
            (pl.col("atr") / 400).alias("atr")
        ])

    # FOR VALIDATION ONLY: Force Hurst and Signal to ensure trades execute
    logger.warning("FORCE BYPASS: Setting Hurst to 0.5 and Signal Threshold to 0.1 for validation")
    df = df.with_columns(pl.lit(0.5).alias("hurst"))
    settings.SIGNAL_THRESHOLD = 0.1

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
