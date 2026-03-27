import polars as pl
import xgboost as xgb
from sklearn.metrics import classification_report
import numpy as np
import os
import structlog

logger = structlog.get_logger()

def purged_walk_forward_cv(df: pl.DataFrame, window_size: int = 1000, gap: int = 15):
    """
    Purged Walk-Forward Cross-Validation.
    Prevents data leakage by ensuring gap between train and test sets.
    """
    total_len = len(df)
    for i in range(window_size, total_len - window_size, window_size):
        train = df.slice(i - window_size, window_size)
        test = df.slice(i + gap, window_size)
        yield train, test

def train_model():
    """Builds and trains the Layer 2 XGBoost Alpha."""
    
    # 1. Load Feature-Engineered Data
    data_path = "data/processed/training_data.parquet"
    if not os.path.exists(data_path):
        logger.error("No training data found in data/processed/")
        return

    df = pl.read_parquet(data_path)
    
    # 2. Define Features and Target
    features = ["hurst", "atr", "efficiency_ratio", "volatility"]
    target = "label" # 1 for Long, 0 for Flat/Short
    
    # 3. Walk-Forward Training
    for train, test in purged_walk_forward_cv(df):
        X_train = train.select(features).to_numpy()
        y_train = train.select(target).to_numpy().flatten()
        
        X_test = test.select(features).to_numpy()
        y_test = test.select(target).to_numpy().flatten()
        
        # XGBoost Params for 2026 High-Frequency
        params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "max_depth": 4,
            "eta": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "nthread": 4
        }
        
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dtest = xgb.DMatrix(X_test, label=y_test)
        
        model = xgb.train(params, dtrain, num_boost_round=100)
        
        preds = model.predict(dtest)
        y_pred = (preds > 0.5).astype(int)
        
        logger.info("Fold Result", report=classification_report(y_test, y_pred, output_dict=True))

    # 4. Final Model Save
    # model.save_model("models/alpha_v1.ubj")
    logger.info("Alpha Training Complete.")

if __name__ == "__main__":
    train_model()
