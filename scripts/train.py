import polars as pl
import xgboost as xgb
from sklearn.metrics import classification_report
import numpy as np
import os
import structlog
from src.features.regime import add_regime_features, calculate_hurst_variance_ratio
from src.features.labels import apply_triple_barrier_labels

logger = structlog.get_logger()

def prepare_data(raw_path: str) -> pl.DataFrame:
    """Loads raw data, adds features, and applies labels."""
    logger.info("Preparing Data...", path=raw_path)
    df = pl.read_parquet(raw_path)
    
    # 1. Add Regime Features (Layer 1)
    df = add_regime_features(df)
    
    # 2. Add Hurst Exponent (Rolling)
    # Note: For training, we can calculate rolling Hurst
    df = df.with_columns(
        pl.col("close").rolling_map(
            lambda s: calculate_hurst_variance_ratio(pl.Series(s)), 
            window_size=100
        ).alias("hurst")
    )
    
    # 3. Apply Triple Barrier Labels (Target)
    df = apply_triple_barrier_labels(df, pt_sl=[1.5, 1.0], vertical_barrier=16)
    
    # 4. Cleanup
    df = df.drop_nulls()
    return df

def purged_walk_forward_cv(df: pl.DataFrame, window_size: int = 2000, gap: int = 50):
    """
    Purged Walk-Forward Cross-Validation.
    """
    total_len = len(df)
    # Ensure we have enough data for at least one fold
    if total_len < (window_size * 2 + gap):
        yield df.slice(0, int(total_len * 0.7)), df.slice(int(total_len * 0.7) + gap, int(total_len * 0.3) - gap)
        return

    for i in range(window_size, total_len - window_size, window_size // 2):
        train = df.slice(i - window_size, window_size)
        test = df.slice(i + gap, min(window_size // 2, total_len - (i + gap)))
        if len(test) < 10: break
        yield train, test

def train_alpha():
    """Main training loop for Layer 2 XGBoost."""
    raw_data_dir = "data/raw"
    processed_data_path = "data/processed/training_data.parquet"
    
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
    full_df.write_parquet(processed_data_path)
    
    # 2. Training
    features = ["hurst", "atr", "efficiency_ratio", "volatility"]
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
