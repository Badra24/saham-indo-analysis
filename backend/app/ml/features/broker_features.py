"""
Broker Feature Extractor

Extracts numerical features from broker summary data for ML models.
Based on research: "Thesis Broker Summary.pdf"

Features:
    1. HHI (Herfindahl-Hirschman Index) - Concentration measure
    2. BCR (Broker Concentration Ratio) - Top3 Buy/Sell ratio
    3. Retail Flow Ratio - Retail broker participation
    4. Foreign Flow Ratio - Foreign institution participation
    5. Consistency Score - Rolling net buy days
    6. Price Control - Correlation(TopBrokerFlow, PriceChange)
"""

from typing import Dict, List, Optional
import numpy as np


# Broker classification database
BROKER_PROFILES = {
    # Retail-dominated brokers
    "YP": {"type": "RETAIL", "origin": "DOMESTIC", "name": "Mirae Asset"},
    "PD": {"type": "RETAIL", "origin": "DOMESTIC", "name": "Phillip Sekuritas"},
    "XC": {"type": "RETAIL", "origin": "DOMESTIC", "name": "BCA Sekuritas"},
    "XL": {"type": "RETAIL", "origin": "DOMESTIC", "name": "Indo Premier"},
    "NI": {"type": "RETAIL", "origin": "DOMESTIC", "name": "Maybank Kim Eng"},
    
    # Domestic institutions
    "CC": {"type": "INSTITUTION", "origin": "DOMESTIC", "name": "Mandiri Sekuritas"},
    "BK": {"type": "INSTITUTION", "origin": "DOMESTIC", "name": "BNI Sekuritas"},
    "DX": {"type": "INSTITUTION", "origin": "DOMESTIC", "name": "BRI Danareksa"},
    
    # Foreign institutions
    "KZ": {"type": "INSTITUTION", "origin": "FOREIGN", "name": "CLSA Indonesia"},
    "MS": {"type": "INSTITUTION", "origin": "FOREIGN", "name": "Morgan Stanley"},
    "AK": {"type": "INSTITUTION", "origin": "FOREIGN", "name": "Deutsche Sekuritas"},
    "ZP": {"type": "INSTITUTION", "origin": "FOREIGN", "name": "Credit Suisse"},
    "GR": {"type": "INSTITUTION", "origin": "FOREIGN", "name": "Macquarie"},
    "CG": {"type": "INSTITUTION", "origin": "FOREIGN", "name": "Citi"},
}


class BrokerFeatureExtractor:
    """
    Extract ML-ready features from broker summary data.
    
    Usage:
        extractor = BrokerFeatureExtractor()
        features = extractor.extract(broker_data, price_history)
    """
    
    def __init__(self):
        self.broker_profiles = BROKER_PROFILES
        
    def extract(self, broker_data: Dict, price_history: Optional[List[Dict]] = None) -> Dict[str, float]:
        """
        Extract all features from broker data.
        
        Args:
            broker_data: Dict with 'top_buyers', 'top_sellers' lists
            price_history: Optional list of OHLCV dicts for price-related features
            
        Returns:
            Dict of feature_name -> float value
        """
        features = {}
        
        # Basic validation
        if not broker_data or not broker_data.get('top_buyers'):
            return self._neutral_features()
            
        top_buyers = broker_data.get('top_buyers', [])
        top_sellers = broker_data.get('top_sellers', [])
        
        # 1. HHI - Herfindahl-Hirschman Index
        features['hhi'] = self._calculate_hhi(top_buyers)
        
        # 2. BCR - Broker Concentration Ratio
        features['bcr'] = self._calculate_bcr(top_buyers, top_sellers)
        
        # 3. Retail Flow Ratio
        features['retail_flow_ratio'] = self._calculate_retail_flow(top_buyers)
        
        # 4. Foreign Flow Ratio
        features['foreign_flow_ratio'] = self._calculate_foreign_flow(top_buyers)
        
        # 5. Top3 Dominance
        features['top3_dominance'] = self._calculate_top3_dominance(top_buyers)
        
        # 6. Buy-Sell Imbalance
        features['buy_sell_imbalance'] = self._calculate_imbalance(top_buyers, top_sellers)
        
        # 7. Broker Count Asymmetry (fewer buyers = more concentrated)
        features['buyer_count'] = len(top_buyers)
        features['seller_count'] = len(top_sellers)
        
        return features
    
    def _calculate_hhi(self, buyers: List[Dict]) -> float:
        """
        Calculate Herfindahl-Hirschman Index.
        
        HHI = Σ(market_share_i)²
        Range: 0-10000 (higher = more concentrated)
        """
        total_value = sum(float(b.get('value', 0)) for b in buyers)
        
        if total_value == 0:
            return 0.0
            
        hhi = sum((float(b.get('value', 0)) / total_value * 100) ** 2 for b in buyers)
        return round(min(hhi, 10000), 2)
    
    def _calculate_bcr(self, buyers: List[Dict], sellers: List[Dict]) -> float:
        """
        Calculate Broker Concentration Ratio.
        
        BCR = Top3 Buy Value / Top3 Sell Value
        """
        buy_top3 = sum(float(b.get('value', 0)) for b in buyers[:3])
        sell_top3 = sum(float(s.get('value', 0)) for s in sellers[:3])
        
        if sell_top3 == 0:
            return 99.0 if buy_top3 > 0 else 1.0
            
        return round(buy_top3 / sell_top3, 3)
    
    def _calculate_retail_flow(self, buyers: List[Dict]) -> float:
        """
        Calculate ratio of retail broker participation.
        
        Range: 0.0 - 1.0 (higher = more retail dominated)
        """
        total_value = sum(float(b.get('value', 0)) for b in buyers)
        
        if total_value == 0:
            return 0.5
            
        retail_brokers = {"YP", "PD", "XC", "XL", "NI"}
        retail_value = sum(
            float(b.get('value', 0)) 
            for b in buyers 
            if b.get('code') in retail_brokers
        )
        
        return round(retail_value / total_value, 4)
    
    def _calculate_foreign_flow(self, buyers: List[Dict]) -> float:
        """
        Calculate ratio of foreign institution participation.
        
        Range: 0.0 - 1.0 (higher = more foreign dominated)
        """
        total_value = sum(float(b.get('value', 0)) for b in buyers)
        
        if total_value == 0:
            return 0.0
            
        foreign_brokers = {"KZ", "MS", "AK", "ZP", "GR", "CG"}
        foreign_value = sum(
            float(b.get('value', 0)) 
            for b in buyers 
            if b.get('code') in foreign_brokers
        )
        
        return round(foreign_value / total_value, 4)
    
    def _calculate_top3_dominance(self, buyers: List[Dict]) -> float:
        """
        Calculate how much Top 3 buyers dominate total flow.
        
        Range: 0.0 - 1.0 (higher = more concentrated)
        """
        total_value = sum(float(b.get('value', 0)) for b in buyers)
        
        if total_value == 0:
            return 0.0
            
        top3_value = sum(float(b.get('value', 0)) for b in buyers[:3])
        return round(top3_value / total_value, 4)
    
    def _calculate_imbalance(self, buyers: List[Dict], sellers: List[Dict]) -> float:
        """
        Calculate buy-sell imbalance.
        
        Range: -1.0 to 1.0 (positive = buy pressure, negative = sell pressure)
        """
        total_buy = sum(float(b.get('value', 0)) for b in buyers)
        total_sell = sum(float(s.get('value', 0)) for s in sellers)
        total = total_buy + total_sell
        
        if total == 0:
            return 0.0
            
        return round((total_buy - total_sell) / total, 4)
    
    def _neutral_features(self) -> Dict[str, float]:
        """Return neutral feature values when data is unavailable."""
        return {
            'hhi': 0.0,
            'bcr': 1.0,
            'retail_flow_ratio': 0.5,
            'foreign_flow_ratio': 0.0,
            'top3_dominance': 0.33,
            'buy_sell_imbalance': 0.0,
            'buyer_count': 0,
            'seller_count': 0,
        }
    
    def get_feature_names(self) -> List[str]:
        """Return list of feature names for model training."""
        return [
            'hhi', 'bcr', 'retail_flow_ratio', 'foreign_flow_ratio',
            'top3_dominance', 'buy_sell_imbalance', 'buyer_count', 'seller_count'
        ]
