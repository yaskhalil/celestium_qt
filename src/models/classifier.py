import xgboost as xgb
import torch
import polars as pl
import numpy as np
import structlog
import os
from src.features.regime import add_regime_features, calculate_hurst_variance_ratio

logger = structlog.get_logger()

class Classifier:
    """Wrapper for XGBoost/PyTorch inference"""
    
    def __init__(self, model_path: str = "models/alpha_v1.ubj"):
        self.model_path = model_path
        self.model = None
        self.load_model()

    def load_model(self):
        """Loads serialized XGBoost/PyTorch models."""
        if not os.path.exists(self.model_path):
            logger.warning("Model file not found", path=self.model_path)
            return

        try:
            self.model = xgb.Booster()
            self.model.load_model(self.model_path)
            logger.info("Model Loaded Successfully", path=self.model_path)
        except Exception as e:
            logger.error("Failed to load model", error=str(e))
            self.model = None

    def predict(self, df: pl.DataFrame) -> float:
        """
        Predicts trade probability (Layer 2 Inference).
        Processes 15m bar history into features.
        """
        if df.is_empty() or len(df) < 100:
            return 0.0
        
        try:
            # 1. Feature Engineering (Layer 1)
            # ADX, ATR, Efficiency Ratio
            df_feats = add_regime_features(df)
            
            # 2. Hurst Exponent (Last 100 bars)
            hurst = calculate_hurst_variance_ratio(df["close"].tail(100))
            
            # 3. Get the latest row for inference
            latest = df_feats.tail(1)
            
            # Construct feature vector matching training
            # Features: ["hurst", "atr", "efficiency_ratio", "volatility", "adx"]
            # Note: add_regime_features calculates volatility (as rolling_sum of abs diff)
            
            feature_data = {
                "hurst": hurst,
                "atr": latest["atr"].item(),
                "efficiency_ratio": latest["efficiency_ratio"].item(),
                "volatility": latest["volatility"].item(),
                "adx": latest["adx"].item()
            }
            
            if self.model is None:
                logger.error("Classifier: Prediction FAILED. Model not loaded.")
                return 0.0
            
            # 4. Inference
            X = np.array([[v for v in feature_data.values()]])
            dmat = xgb.DMatrix(X, feature_names=list(feature_data.keys()))
            prob = self.model.predict(dmat)[0]
            
            logger.info("Classifier: Prediction generated", prob=round(float(prob), 3))
            return float(prob)
            
        except Exception as e:
            logger.error("Inference Error", error=str(e))
            return 0.0
