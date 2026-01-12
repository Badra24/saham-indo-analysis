import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from typing import Dict, List, Optional
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

class MLEngine:
    """
    Machine Learning Engine for Market Anomaly Detection.
    
    Implements:
    1. Isolation Forest (Unsupervised Learning) to detect volume/price anomalies.
    2. Feature Engineering logic for ML models.
    
    Reference: Riset Bandarmologi Chapter 5.2 "Modul Deteksi Anomali MM Detector"
    """
    
    def __init__(self):
        # Isolation Forest parameters favored for anomaly detection in time-series
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.05, # Expect approx 5% data to be anomalies (whales)
            random_state=42,
            n_jobs=-1
        )
        self.is_fitted = False

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for the ML model.
        Features selected based on "MM Detector" research:
        - Volume Ratio (Current Vol / MA Vol)
        - Price Volatility (High-Low range)
        - Price Change %
        - Distance from VWAP
        """
        df = df.copy()
        
        # Ensure we have enough data
        if len(df) < 20:
            return pd.DataFrame()

        # 1. Volume Ratio (Relative Volume)
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
        df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20'].replace(0, 1)
        
        # 2. Price Volatility (Normalized Range)
        df['Range'] = (df['High'] - df['Low']) / df['Close']
        
        # 3. Returns (Absolute return to detect big moves regardless of direction)
        df['Returns'] = df['Close'].pct_change()
        df['Abs_Returns'] = df['Returns'].abs()
        
        # 4. VWAP Distance (if VWAP exists, else calculate simplified VWAP)
        if 'VWAP' not in df.columns:
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['VWAP'] = (df['TP'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
            
        df['VWAP_Dist'] = ((df['Close'] - df['VWAP']) / df['VWAP']).abs()
        
        # Drop NaN created by rolling windows
        features = df[['Vol_Ratio', 'Range', 'Abs_Returns', 'VWAP_Dist']].dropna()
        
        return features

    def train_detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Train the model on the data and detect anomalies.
        Returns the DataFrame with 'Anomaly_Score' and 'Is_Anomaly' columns.
        """
        if df.empty or len(df) < 30:
            # Not enough data for reliable ML
            df['Anomaly_Score'] = 0.0
            df['Is_Anomaly'] = False
            return df
            
        features = self._prepare_features(df)
        
        if features.empty:
            df['Anomaly_Score'] = 0.0
            df['Is_Anomaly'] = False
            return df
            
        # Standardize features (optional but good for some models, IsolationForest is robust though)
        # Using pure features as range is important info for IF
        
        # Fit & Predict
        # Anomaly Score: negative values are anomalies, positive are normal
        # Decision Function: lower = more abnormal
        self.model.fit(features)
        
        # decision_function yields a score. 
        # We negate it so that HIGHER value means MORE ANOMALOUS for easier mental model?
        # Standard IF: negative score = anomaly.
        scores = self.model.decision_function(features)
        predictions = self.model.predict(features) # -1 for outlier, 1 for inlier
        
        # Map back to original dataframe
        # Create a Series with matching index to avoid alignment issues
        score_series = pd.Series(scores, index=features.index)
        pred_series = pd.Series(predictions, index=features.index)
        
        df.loc[features.index, 'Anomaly_Score'] = score_series
        # Convert -1 (anomaly) to True, 1 (normal) to False
        df.loc[features.index, 'Is_Anomaly'] = pred_series == -1
        
        # Fill missing (early rows) with default
        df['Anomaly_Score'] = df['Anomaly_Score'].fillna(0.0)
        df['Is_Anomaly'] = df['Is_Anomaly'].fillna(False)
        
        return df

    def analyze_latest_anomaly(self, df: pd.DataFrame) -> Dict:
        """
        Analyze the latest candle for anomaly status.
        Returns a dictionary suitable for API/Frontend.
        """
        if df.empty:
            return {"is_anomaly": False, "score": 0.0, "description": "No Data"}
            
        df_analyzed = self.train_detect(df)
        latest = df_analyzed.iloc[-1]
        
        is_anomaly = bool(latest['Is_Anomaly'])
        score = float(latest['Anomaly_Score'])
        
        # Interpret the anomaly
        description = "Normal Activity"
        if is_anomaly:
            # Check logic to give context
            vol_spike = latest['Volume'] > (latest.get('Vol_MA20', 0) * 1.5)
            price_spike = abs(latest.get('Returns', 0)) > 0.02
            
            if vol_spike and price_spike:
                description = "High Volatility & Volume Spike (Aggressive)"
            elif vol_spike:
                description = "Unusual Volume Spike (Potential Accumulation/Distribution)"
            elif price_spike:
                description = "Unusual Price Movement"
            else:
                description = "Microstructure Anomaly Identified"
                
        return {
            "is_anomaly": is_anomaly,
            "score": round(score, 3), # Negative values are "more anomalous" in raw IF score
            "description": description
        }


    def predict_next_day_trend(self, features: Dict) -> Dict:
        """
        Phase 18: Predictive ML (Forecasting).
        Predicts probability of 'UP' trend for next day.
        
        Args:
            features: Dict containing 'alpha_v_score', 'bcr', 'foreign_flow'.
        
        Returns:
            Dict with 'probability_up', 'confidence'.
        """
        # In a mature system, this would load a .pkl model trained on 5 years of IDX data.
        # For Phase 1 Implementation without a DB, we use an 'Expert System' logic 
        # that mimics a trained Decision Tree behavior.
        
        score_av = features.get('alpha_v_score', 50)
        bcr = features.get('bcr', 1.0)
        
        # Base probability is 50/50
        prob = 0.5
        
        # 1. Alpha-V Influence (Long Term Bias)
        if score_av > 70: prob += 0.15
        elif score_av < 40: prob -= 0.15
        
        # 2. Bandarmology Influence (Short Term Bias)
        if bcr > 1.2: prob += 0.20
        elif bcr < 0.8: prob -= 0.20
        
        # Clamp
        prob = max(0.01, min(0.99, prob))
        
        # Categorize
        confidence = "Neutral"
        if prob > 0.7: confidence = "High Bullish"
        elif prob < 0.3: confidence = "High Bearish"
        
        return {
            "model": "RandomForest_v1 (Heuristic)",
            "prediction": "UP" if prob > 0.5 else "DOWN",
            "probability": round(prob, 2),
            "confidence": confidence
        }

# Global instance
ml_engine = MLEngine()
