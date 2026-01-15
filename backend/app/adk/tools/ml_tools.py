"""
ML Tools for ADK Agent Integration

These tools allow LLM agents to call ML models for fast numeric predictions.
The LLM interprets the results and generates human-readable analysis.

Usage in ADK Agent:
    @tool
    def predict_accumulation(ticker: str, broker_data: dict) -> dict:
        return ml_predict_accumulation(ticker, broker_data)
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def ml_predict_accumulation(ticker: str, broker_data: Dict) -> Dict:
    """
    Tool for ADK Agent to get ML-based accumulation prediction.
    
    Args:
        ticker: Stock ticker code
        broker_data: Dict with 'top_buyers', 'top_sellers'
        
    Returns:
        Prediction dict with:
            - accumulation_probability: float (0-1)
            - price_direction: str (UP/DOWN/FLAT)
            - confidence: float (0-1)
            - pattern: str (ACCUMULATION/DISTRIBUTION/NEUTRAL)
            - interpretation: str (human-readable summary)
    """
    try:
        from app.ml.inference.predictor import get_predictor
        
        predictor = get_predictor()
        result = predictor.predict(broker_data)
        
        # Add interpretation for LLM context
        acc_prob = result['accumulation_probability']
        pattern = result['pattern']
        confidence = result['confidence']
        
        if pattern == "ACCUMULATION":
            interpretation = (
                f"ML model detects {pattern} pattern with {acc_prob:.1%} probability. "
                f"Confidence: {confidence:.1%}. Institutional buying appears concentrated."
            )
        elif pattern == "DISTRIBUTION":
            interpretation = (
                f"ML model detects {pattern} pattern with {(1-acc_prob):.1%} probability. "
                f"Confidence: {confidence:.1%}. Selling pressure from institutions."
            )
        else:
            interpretation = (
                f"ML model shows NEUTRAL pattern. No clear accumulation or distribution. "
                f"Confidence: {confidence:.1%}."
            )
            
        result['interpretation'] = interpretation
        result['ticker'] = ticker
        
        return result
        
    except Exception as e:
        logger.error(f"ML prediction failed: {e}")
        return {
            "error": str(e),
            "fallback": True,
            "interpretation": "ML prediction unavailable. Using qualitative analysis."
        }


def ml_get_feature_analysis(broker_data: Dict) -> Dict:
    """
    Tool for ADK Agent to get detailed feature breakdown.
    
    Returns individual feature values for LLM to analyze.
    """
    try:
        from app.ml.features.broker_features import BrokerFeatureExtractor
        
        extractor = BrokerFeatureExtractor()
        features = extractor.extract(broker_data)
        
        # Add interpretations for each feature
        analysis = {
            "features": features,
            "interpretations": {}
        }
        
        # HHI interpretation
        hhi = features.get('hhi', 0)
        if hhi > 2500:
            analysis['interpretations']['hhi'] = "Highly concentrated (Bandar dominant)"
        elif hhi > 1500:
            analysis['interpretations']['hhi'] = "Moderately concentrated"
        else:
            analysis['interpretations']['hhi'] = "Fragmented (retail dominated)"
            
        # BCR interpretation
        bcr = features.get('bcr', 1)
        if bcr > 1.5:
            analysis['interpretations']['bcr'] = "Strong buying pressure"
        elif bcr < 0.7:
            analysis['interpretations']['bcr'] = "Strong selling pressure"
        else:
            analysis['interpretations']['bcr'] = "Balanced flow"
            
        # Foreign flow
        foreign = features.get('foreign_flow_ratio', 0)
        if foreign > 0.3:
            analysis['interpretations']['foreign'] = "High foreign participation (positive signal)"
        elif foreign > 0.1:
            analysis['interpretations']['foreign'] = "Moderate foreign activity"
        else:
            analysis['interpretations']['foreign'] = "Domestically driven"
            
        return analysis
        
    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        return {"error": str(e)}


# Export tools for ADK registration
ML_TOOLS = [
    ml_predict_accumulation,
    ml_get_feature_analysis
]
