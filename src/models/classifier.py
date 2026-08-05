import xgboost as xgb
import polars as pl
import numpy as np
import structlog
import os
from src.features.regime import add_regime_features

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
        if df.is_empty() or len(df) < 110: # Need extra for gradient/momentum shifts
            return 0.0
        
        try:
            # 1. Feature Engineering (Layer 1)
            # Now includes Hurst, Hurst Gradient, ADX, ATR, Efficiency Ratio, Vol-Adj Momentum
            df_feats = add_regime_features(df)
            
            # 2. Get the latest row for inference
            latest = df_feats.tail(1)
            
            # Construct feature vector matching training
            # Features: ["hurst", "hurst_gradient", "atr", "efficiency_ratio", "volatility", "adx", "vol_adj_momentum"]
            features = ["hurst", "hurst_gradient", "atr", "efficiency_ratio", "volatility", "adx", "vol_adj_momentum"]
            
            feature_data = {f: latest[f].item() for f in features}
            
            if self.model is None:
                logger.error("Classifier: Prediction FAILED. Model not loaded.")
                return 0.0
            
            # 3. Inference
            X = np.array([[v for v in feature_data.values()]])
            dmat = xgb.DMatrix(X, feature_names=list(feature_data.keys()))
            prob = self.model.predict(dmat)[0]
            
            logger.info("Classifier: Prediction generated", prob=round(float(prob), 3))
            return float(prob)
            
        except Exception as e:
            logger.error("Inference Error", error=str(e))
            return 0.0

    def predict_features(self, feature_data: dict) -> float:
        """
        Fast path for Backtester. Features are already calculated.
        """
        if self.model is None:
            return 0.0
        try:
            features = ["hurst", "hurst_gradient", "atr", "efficiency_ratio", "volatility", "adx", "vol_adj_momentum"]
            X = np.array([[feature_data.get(f, 0.0) for f in features]])
            dmat = xgb.DMatrix(X, feature_names=features)
            prob = self.model.predict(dmat)[0]
            # using debug logger so we don't spam 27000 logs
            logger.debug("Classifier: Prediction generated", prob=round(float(prob), 3))
            return float(prob)
        except Exception as e:
            logger.error("Inference Error", error=str(e))
            return 0.0
