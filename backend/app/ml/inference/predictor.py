"""
Broker Predictor - ML Inference Service

Provides fast predictions for:
1. Accumulation/Distribution classification
2. Price direction (T+1)
3. Confidence scores

Integrates with ADK Agent as a tool for numeric predictions.
"""

import os
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

import numpy as np

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False

from ..features.broker_features import BrokerFeatureExtractor

logger = logging.getLogger(__name__)


class BrokerPredictor:
    """
    ML-based broker activity predictor.
    
    Uses trained RandomForest/XGBoost models to predict:
    - Accumulation probability (0-1)
    - Price direction (UP/DOWN/FLAT)
    
    Usage:
        predictor = BrokerPredictor.load("broker_predictor_v1.joblib")
        result = predictor.predict(broker_data)
    """
    
    MODEL_DIR = Path(__file__).parent.parent / "models"
    
    def __init__(self, model=None, scaler=None):
        """
        Initialize predictor with optional pre-loaded model.
        
        Args:
            model: Trained sklearn model (RandomForest, XGBoost, etc.)
            scaler: Optional feature scaler (StandardScaler, etc.)
        """
        self.model = model
        self.scaler = scaler
        self.feature_extractor = BrokerFeatureExtractor()
        self._is_trained = model is not None
        
    @classmethod
    def load(cls, model_name: str = "broker_predictor_v1.joblib") -> "BrokerPredictor":
        """
        Load a trained model from disk.
        
        Args:
            model_name: Filename of the saved model
            
        Returns:
            BrokerPredictor instance with loaded model
        """
        if not JOBLIB_AVAILABLE:
            logger.warning("joblib not installed. Using rule-based fallback.")
            return cls(model=None)
            
        model_path = cls.MODEL_DIR / model_name
        
        if not model_path.exists():
            logger.warning(f"Model not found at {model_path}. Using rule-based fallback.")
            return cls(model=None)
            
        try:
            saved = joblib.load(model_path)
            return cls(
                model=saved.get('model'),
                scaler=saved.get('scaler')
            )
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return cls(model=None)
    
    def predict(self, broker_data: Dict, price_history: Optional[list] = None) -> Dict:
        """
        Predict accumulation pattern and price direction.
        
        Args:
            broker_data: Dict with 'top_buyers', 'top_sellers'
            price_history: Optional OHLCV history
            
        Returns:
            Dict with predictions:
                - accumulation_probability: float (0-1)
                - price_direction: str (UP/DOWN/FLAT)
                - confidence: float (0-1)
                - pattern: str (ACCUMULATION/DISTRIBUTION/NEUTRAL)
        """
        # Extract features
        features = self.feature_extractor.extract(broker_data, price_history)
        
        # If no trained model, use rule-based fallback
        if not self._is_trained:
            return self._rule_based_prediction(features)
            
        # Prepare feature vector
        feature_names = self.feature_extractor.get_feature_names()
        X = np.array([[features[f] for f in feature_names]])
        
        # Scale if scaler available
        if self.scaler:
            X = self.scaler.transform(X)
            
        # Get prediction probabilities
        try:
            proba = self.model.predict_proba(X)[0]
            pred_class = self.model.predict(X)[0]
            
            # Map class to pattern
            class_map = {0: "DISTRIBUTION", 1: "NEUTRAL", 2: "ACCUMULATION"}
            pattern = class_map.get(pred_class, "NEUTRAL")
            
            # Accumulation probability (class 2)
            acc_prob = proba[2] if len(proba) > 2 else proba[1]
            
            # Confidence is the max probability
            confidence = float(max(proba))
            
            # Price direction based on pattern
            if pattern == "ACCUMULATION" and confidence > 0.6:
                direction = "UP"
            elif pattern == "DISTRIBUTION" and confidence > 0.6:
                direction = "DOWN"
            else:
                direction = "FLAT"
                
            return {
                "accumulation_probability": round(float(acc_prob), 4),
                "price_direction": direction,
                "confidence": round(confidence, 4),
                "pattern": pattern,
                "features": features,
                "model_version": "v1"
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return self._rule_based_prediction(features)
    
    def _rule_based_prediction(self, features: Dict) -> Dict:
        """
        Rule-based fallback when no ML model is available.
        Uses research-based thresholds.
        """
        hhi = features.get('hhi', 0)
        bcr = features.get('bcr', 1)
        foreign_ratio = features.get('foreign_flow_ratio', 0)
        imbalance = features.get('buy_sell_imbalance', 0)
        
        # Calculate accumulation probability using research rules
        acc_score = 0.5  # Start neutral
        
        # HHI contribution (high concentration = accumulation sign)
        if hhi > 2500:
            acc_score += 0.2
        elif hhi > 1500:
            acc_score += 0.1
            
        # BCR contribution
        if bcr > 1.5:
            acc_score += 0.15
        elif bcr > 1.2:
            acc_score += 0.08
        elif bcr < 0.8:
            acc_score -= 0.15
            
        # Foreign flow contribution
        if foreign_ratio > 0.3:
            acc_score += 0.1
            
        # Imbalance contribution
        acc_score += imbalance * 0.15
        
        # Clamp to 0-1
        acc_prob = max(0, min(1, acc_score))
        
        # Determine pattern
        if acc_prob > 0.65:
            pattern = "ACCUMULATION"
            direction = "UP"
        elif acc_prob < 0.35:
            pattern = "DISTRIBUTION"
            direction = "DOWN"
        else:
            pattern = "NEUTRAL"
            direction = "FLAT"
            
        confidence = abs(acc_prob - 0.5) * 2  # Distance from neutral
        
        return {
            "accumulation_probability": round(acc_prob, 4),
            "price_direction": direction,
            "confidence": round(confidence, 4),
            "pattern": pattern,
            "features": features,
            "model_version": "rule_based",
            "note": "Using rule-based prediction. Train a model for better accuracy."
        }
    
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get feature importance from trained model."""
        if not self._is_trained or not hasattr(self.model, 'feature_importances_'):
            return None
            
        feature_names = self.feature_extractor.get_feature_names()
        importance = self.model.feature_importances_
        
        return dict(sorted(
            zip(feature_names, importance),
            key=lambda x: x[1],
            reverse=True
        ))


# Singleton instance
_predictor_instance: Optional[BrokerPredictor] = None


def get_predictor() -> BrokerPredictor:
    """Get or create singleton predictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = BrokerPredictor.load()
    return _predictor_instance
