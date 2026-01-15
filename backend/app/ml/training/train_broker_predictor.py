"""
Broker Predictor Training Script

Trains a RandomForest/XGBoost classifier to predict:
- Accumulation/Distribution/Neutral patterns
- Based on broker summary features

Usage:
    python -m app.ml.training.train_broker_predictor --data path/to/data.csv

Requirements:
    pip install scikit-learn xgboost pandas joblib
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional

import numpy as np
import pandas as pd

try:
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import classification_report, confusion_matrix
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("sklearn not installed. Run: pip install scikit-learn")

# XGBoost will be imported lazily in train() to avoid libomp requirement
XGBOOST_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.ml.features.broker_features import BrokerFeatureExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BrokerPredictorTrainer:
    """
    Train ML models for broker pattern prediction.
    
    Workflow:
        1. Load historical broker summary data
        2. Extract features using BrokerFeatureExtractor
        3. Label data (ACCUMULATION=2, NEUTRAL=1, DISTRIBUTION=0)
        4. Train RandomForest/XGBoost
        5. Evaluate and save model
    """
    
    MODEL_DIR = Path(__file__).parent.parent / "models"
    
    def __init__(self, model_type: str = "random_forest"):
        """
        Args:
            model_type: "random_forest" or "xgboost"
        """
        self.model_type = model_type
        self.feature_extractor = BrokerFeatureExtractor()
        self.scaler = StandardScaler()
        self.model = None
        
        # Ensure model directory exists
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data from historical broker summary DataFrame.
        
        Expected columns:
            - ticker: Stock code
            - date: Date of record
            - top_buyers: JSON array of {code, value}
            - top_sellers: JSON array of {code, value}
            - price_change_next_day: float (for labeling)
            
        Returns:
            X: Feature matrix
            y: Labels (0=DISTRIBUTION, 1=NEUTRAL, 2=ACCUMULATION)
        """
        import json
        
        features_list = []
        labels = []
        
        for _, row in df.iterrows():
            # Parse broker data
            try:
                top_buyers = json.loads(row['top_buyers']) if isinstance(row['top_buyers'], str) else row['top_buyers']
                top_sellers = json.loads(row['top_sellers']) if isinstance(row['top_sellers'], str) else row['top_sellers']
            except:
                continue
                
            broker_data = {
                'top_buyers': top_buyers,
                'top_sellers': top_sellers
            }
            
            # Extract features
            features = self.feature_extractor.extract(broker_data)
            feature_vec = [features[f] for f in self.feature_extractor.get_feature_names()]
            features_list.append(feature_vec)
            
            # Create label based on next-day price change
            price_change = row.get('price_change_next_day', 0)
            if price_change > 1.5:  # >1.5% up
                label = 2  # ACCUMULATION
            elif price_change < -1.5:  # <-1.5% down
                label = 0  # DISTRIBUTION
            else:
                label = 1  # NEUTRAL
                
            labels.append(label)
            
        return np.array(features_list), np.array(labels)
    
    def train(self, X: np.ndarray, y: np.ndarray, test_size: float = 0.2) -> dict:
        """
        Train the model.
        
        Args:
            X: Feature matrix
            y: Labels
            test_size: Fraction for test set
            
        Returns:
            Dict with training metrics
        """
        logger.info(f"Training {self.model_type} model...")
        logger.info(f"Dataset: {len(X)} samples")
        logger.info(f"Class distribution: {np.bincount(y)}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Create model
        if self.model_type == "xgboost" and XGBOOST_AVAILABLE:
            self.model = XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric='mlogloss'
            )
        else:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                class_weight='balanced'
            )
            
        # Train
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        
        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
        
        metrics = {
            "accuracy": float((y_pred == y_test).mean()),
            "cv_mean": float(cv_scores.mean()),
            "cv_std": float(cv_scores.std()),
            "classification_report": classification_report(
                y_test, y_pred, 
                target_names=["DISTRIBUTION", "NEUTRAL", "ACCUMULATION"]
            ),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "feature_importance": dict(
                zip(
                    self.feature_extractor.get_feature_names(),
                    self.model.feature_importances_.tolist()
                )
            )
        }
        
        logger.info(f"Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"CV Score: {metrics['cv_mean']:.4f} (+/- {metrics['cv_std']:.4f})")
        logger.info(f"\n{metrics['classification_report']}")
        
        return metrics
    
    def save_model(self, name: Optional[str] = None) -> Path:
        """
        Save trained model to disk.
        
        Args:
            name: Model filename (default: broker_predictor_v1.joblib)
            
        Returns:
            Path to saved model
        """
        if self.model is None:
            raise ValueError("No trained model to save")
            
        if name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"broker_predictor_{timestamp}.joblib"
            
        model_path = self.MODEL_DIR / name
        
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_extractor.get_feature_names(),
            'model_type': self.model_type,
            'created_at': datetime.now().isoformat()
        }, model_path)
        
        logger.info(f"Model saved to {model_path}")
        
        # Also save as latest
        latest_path = self.MODEL_DIR / "broker_predictor_v1.joblib"
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_extractor.get_feature_names(),
            'model_type': self.model_type,
            'created_at': datetime.now().isoformat()
        }, latest_path)
        
        return model_path


def generate_sample_training_data(n_samples: int = 1000) -> pd.DataFrame:
    """
    Generate synthetic training data for testing.
    In production, replace with real historical data from DuckDB.
    """
    import random
    import json
    
    data = []
    
    for i in range(n_samples):
        # Simulate broker data
        n_buyers = random.randint(5, 15)
        n_sellers = random.randint(5, 15)
        
        # Simulate accumulation scenario (30%)
        is_accumulation = random.random() < 0.3
        is_distribution = random.random() < 0.3 if not is_accumulation else False
        
        if is_accumulation:
            # Concentrated buying
            top_buyers = [
                {"code": random.choice(["KZ", "MS", "AK"]), "value": random.uniform(50e9, 200e9)},
                {"code": random.choice(["BK", "CC"]), "value": random.uniform(20e9, 80e9)},
            ] + [
                {"code": f"B{j}", "value": random.uniform(1e9, 10e9)} 
                for j in range(n_buyers - 2)
            ]
            top_sellers = [
                {"code": random.choice(["YP", "PD", "XC"]), "value": random.uniform(10e9, 50e9)}
                for _ in range(n_sellers)
            ]
            price_change = random.uniform(1.5, 5.0)
        elif is_distribution:
            # Concentrated selling
            top_buyers = [
                {"code": random.choice(["YP", "PD"]), "value": random.uniform(10e9, 40e9)}
                for _ in range(n_buyers)
            ]
            top_sellers = [
                {"code": random.choice(["KZ", "MS"]), "value": random.uniform(50e9, 150e9)},
                {"code": random.choice(["AK", "ZP"]), "value": random.uniform(30e9, 100e9)},
            ] + [
                {"code": f"S{j}", "value": random.uniform(5e9, 20e9)}
                for j in range(n_sellers - 2)
            ]
            price_change = random.uniform(-5.0, -1.5)
        else:
            # Neutral
            top_buyers = [
                {"code": f"B{j}", "value": random.uniform(5e9, 30e9)}
                for j in range(n_buyers)
            ]
            top_sellers = [
                {"code": f"S{j}", "value": random.uniform(5e9, 30e9)}
                for j in range(n_sellers)
            ]
            price_change = random.uniform(-1.0, 1.0)
            
        data.append({
            "ticker": random.choice(["BBCA", "BBRI", "TLKM", "ASII", "BMRI"]),
            "date": f"2025-01-{random.randint(1, 28):02d}",
            "top_buyers": json.dumps(top_buyers),
            "top_sellers": json.dumps(top_sellers),
            "price_change_next_day": price_change
        })
        
    return pd.DataFrame(data)


def main():
    parser = argparse.ArgumentParser(description="Train Broker Predictor Model")
    parser.add_argument("--data", type=str, help="Path to training data CSV")
    parser.add_argument("--model-type", type=str, default="random_forest", 
                        choices=["random_forest", "xgboost"])
    parser.add_argument("--sample", action="store_true", 
                        help="Use synthetic sample data for testing")
    args = parser.parse_args()
    
    if not SKLEARN_AVAILABLE:
        print("ERROR: sklearn required. Run: pip install scikit-learn")
        return
        
    trainer = BrokerPredictorTrainer(model_type=args.model_type)
    
    # Load data
    if args.sample or args.data is None:
        logger.info("Generating synthetic training data...")
        df = generate_sample_training_data(2000)
    else:
        df = pd.read_csv(args.data)
        
    # Prepare features and labels
    X, y = trainer.prepare_data(df)
    
    if len(X) < 100:
        logger.error("Not enough training samples")
        return
        
    # Train model
    metrics = trainer.train(X, y)
    
    # Save model
    model_path = trainer.save_model()
    
    print(f"\n✅ Model trained and saved to: {model_path}")
    print(f"   Accuracy: {metrics['accuracy']:.2%}")
    print(f"   CV Score: {metrics['cv_mean']:.2%} (+/- {metrics['cv_std']:.2%})")


if __name__ == "__main__":
    main()
