import polars as pl
import xgboost as xgb
from sklearn.metrics import classification_report
import numpy as np
import os
import structlog
from src.features.regime import add_regime_features
from src.features.labels import apply_triple_barrier_labels

logger = structlog.get_logger()

def prepare_data(raw_path: str) -> pl.DataFrame:
    """Loads raw data, adds features, and applies labels."""
    logger.info("Preparing Data...", path=raw_path)
    df = pl.read_parquet(raw_path)
    
    # Extract symbol from filename
    symbol = os.path.basename(raw_path).split("_")[0]
    df = df.with_columns(pl.lit(symbol).alias("symbol"))
    
    # Normalize timestamp
    df = df.with_columns(
        pl.col("timestamp").dt.cast_time_unit("us").dt.replace_time_zone(None)
    )
    
    # FILTER: Remove ghost prices (NQ should be between 10k and 30k in 2026)
    df = df.filter(
        (pl.col("close") > 10000) & (pl.col("close") < 30000)
    )
    
    # Sort by timestamp to ensure chronological order
    df = df.sort("timestamp")
    
    # 1. Add Regime Features (Layer 1) - Per Symbol
    df = add_regime_features(df)
    
    # 2. Apply Triple Barrier Labels (Target)
    # Tighter barriers for real market noise: 1.0 ATR Target, 0.5 ATR Stop
    df = apply_triple_barrier_labels(df, pt_sl=[1.0, 0.5], vertical_barrier=16)
    
    # 3. Cleanup
    df = df.drop_nulls()
    return df

def purged_walk_forward_cv(df: pl.DataFrame, window_size: int = 2000, gap: int = 50):
    """
    Purged Walk-Forward Cross-Validation.
    """
    total_len = len(df)
    if total_len < (window_size * 2 + gap):
        # Fallback for small datasets (like our synthetic 3900 rows)
        train_size = int(total_len * 0.7)
        yield df.slice(0, train_size), df.slice(train_size + gap, total_len - (train_size + gap))
        return

    for i in range(window_size, total_len - window_size, window_size // 2):
        train = df.slice(i - window_size, window_size)
        test = df.slice(i + gap, min(window_size // 2, total_len - (i + gap)))
        if len(test) < 10: break
        yield train, test

def train_alpha():
    """Main training loop for Layer 2 XGBoost."""
    raw_data_dir = "data/raw"
    processed_data_dir = "data/processed"
    processed_data_path = os.path.join(processed_data_dir, "training_data.parquet")
    
    # 1. Data Ingestion
    all_dfs = []
    if not os.path.exists(raw_data_dir):
        os.makedirs(raw_data_dir, exist_ok=True)
        
    for file in os.listdir(raw_data_dir):
        if file.endswith(".parquet"):
            all_dfs.append(prepare_data(os.path.join(raw_data_dir, file)))
            
    if not all_dfs:
        logger.warning("No raw data found in data/raw/. Training aborted.")
        return

    full_df = pl.concat(all_dfs)
    os.makedirs(processed_data_dir, exist_ok=True)
    full_df.write_parquet(processed_data_path)
    
    # 2. Training
    features = ["hurst", "hurst_gradient", "atr", "efficiency_ratio", "volatility", "adx", "vol_adj_momentum"]
    target = "label"
    
    logger.info("Starting Walk-Forward Training", rows=len(full_df))
    
    best_model = None
    
    for fold, (train, test) in enumerate(purged_walk_forward_cv(full_df)):
        X_train = train.select(features).to_numpy()
        y_train = train.select(target).to_numpy().flatten()
        
        X_test = test.select(features).to_numpy()
        y_test = test.select(target).to_numpy().flatten()
        
        params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "max_depth": 5,
            "eta": 0.03,
            "subsample": 0.7,
            "colsample_bytree": 0.7,
            "nthread": 4
        }
        
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dtest = xgb.DMatrix(X_test, label=y_test)
        
        model = xgb.train(params, dtrain, num_boost_round=150)
        best_model = model # Simplified: take the last one or implement tracking
        
        preds = model.predict(dtest)
        y_pred = (preds > 0.5).astype(int)
        
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        logger.info(f"Fold {fold} Result", precision=report["1"]["precision"], recall=report["1"]["recall"])

    # 3. Save Final Model
    if best_model:
        model_path = "models/alpha_v1.ubj"
        os.makedirs("models", exist_ok=True)
        best_model.save_model(model_path)
        logger.info("Alpha Model Saved", path=model_path)

if __name__ == "__main__":
    train_alpha()
