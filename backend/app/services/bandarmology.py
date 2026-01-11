from typing import Dict, List, Optional
import math

class BandarmologyEngine:
    """
    Real Bandarmology Engine (No Mock Data).
    
    Implements:
    1. Broker Concentration Ratio (BCR) Analysis
    2. Retail Disguise Detection (YP/PD/XC buying huge value)
    3. Smart Money Flow Estimation (Chaikin Money Flow / Lee-Ready Proxy)
    
    Adheres strictly to research: "Bandar Saham_ Advanced Identification & Expert Insights.txt"
    """

    def analyze_broker_summary(self, broker_data: Optional[Dict]) -> Dict:
        """
        Analyze Broker Summary Data (from API or Upload).
        
        Args:
            broker_data: Dictionary containing top_buyers, top_sellers (list of dicts with 'code', 'value').
            
        Returns:
            Dict with 'status', 'bcr', 'signals'.
            Returns status='DATA_UNAVAILABLE' if input is invalid.
        """
        if not broker_data or not broker_data.get('top_buyers') or not broker_data.get('top_sellers'):
             return {
                "status": "DATA_UNAVAILABLE",
                "concentration_ratio": 0.0,
                "top_buyers": [],
                "top_sellers": [],
                "dominant_player": "UNKNOWN",
                "signals": ["No broker data available for analysis."]
            }

        # Extract data
        top_buyers = broker_data.get('top_buyers', [])
        top_sellers = broker_data.get('top_sellers', [])
        
        # Calculate Top 3 Values (using first 3 items)
        buy_value_top3 = sum(float(b.get('value', 0)) for b in top_buyers[:3])
        sell_value_top3 = sum(float(s.get('value', 0)) for s in top_sellers[:3])
        
        total_buy_value = sum(float(b.get('value', 0)) for b in top_buyers)
        total_sell_value = sum(float(s.get('value', 0)) for s in top_sellers)
        
        # 1. Calculate BCR (Broker Concentration Ratio)
        # Avoid division by zero
        if sell_value_top3 == 0:
            bcr = 99.0 if buy_value_top3 > 0 else 1.0
        else:
            bcr = buy_value_top3 / sell_value_top3
            
        # 2. Determine Status (Accumulation vs Distribution)
        status = "NEUTRAL"
        signals = []
        
        if bcr >= 1.2:
            status = "ACCUMULATION"
            signals.append(f"Strong Accumulation (BCR {bcr:.2f})")
            if total_buy_value > total_sell_value * 1.5:
                status = "BIG_ACCUMULATION"
                signals.append("Aggressive Buying > 1.5x Selling")
        elif bcr <= 0.8:
            status = "DISTRIBUTION"
            signals.append(f"Distribution Detect (BCR {bcr:.2f})")
            if total_sell_value > total_buy_value * 1.5:
                status = "BIG_DISTRIBUTION"
                signals.append("Aggressive Selling > 1.5x Buying")
                
        # 3. Detect Retail Disguise (Retail brokers in Top 3 Buyers with huge value)
        retail_brokers = ["YP", "PD", "XC", "XL", "CC", "NI"] 
        # Note: CC/NI sometimes mixed, but in "Disguise" context often used by retail-like accounts
        
        retail_buy_val_top3 = sum(
            float(b.get('value', 0)) 
            for b in top_buyers[:3] 
            if b.get('code') in retail_brokers or b.get('type') == 'RETAIL'
        )
        
        # If Retail is dominant buyer in Accumulation phase -> Suspect "Retail Disguise"
        if status in ["ACCUMULATION", "BIG_ACCUMULATION"] and retail_buy_val_top3 > (buy_value_top3 * 0.5):
             signals.append("WARNING: Retail Disguise Pattern (Retail Brokers dominant in Top 3 Buys)")
             status = "ACCUMULATION_TERSELUBUNG" # Hidden Accumulation
             
        # 4. Dominant Player
        dom_player = "INSTITUTION" # Default assumption
        if retail_buy_val_top3 > (buy_value_top3 * 0.5):
            dom_player = "RETAIL"
            if bcr > 1.5: dom_player = "WHALE_IN_RETAIL" # Smart Money using retail
            
        return {
            "status": status,
            "concentration_ratio": round(bcr, 2),
            "top_buyers": [b.get('code') for b in top_buyers[:3]],
            "top_sellers": [s.get('code') for s in top_sellers[:3]],
            "dominant_player": dom_player,
            "signals": signals,
            "broker_data_available": True
        }

    def calculate_smart_money_flow_proxy(self, df_history: List[Dict]) -> float:
        """
        Calculate Smart Money Flow Score (0-100) using Price/Volume data.
        Proxy method when real broker data is missing.
        
        Uses Chaikin Money Flow (CMF) logic over last 20 periods.
        """
        if not df_history or len(df_history) < 20:
            return 50.0 # Neutral
            
        # Convert to list of dicts if needed, assuming input is list of dicts from API
        # Need to handle if input is DataFrame? The type hint says List[Dict]
        
        mf_volume_sum = 0
        volume_sum = 0
        
        for candle in df_history[-20:]:
            high = float(candle.get('high', 0) or candle.get('High', 0))
            low = float(candle.get('low', 0) or candle.get('Low', 0))
            close = float(candle.get('close', 0) or candle.get('Close', 0))
            volume = float(candle.get('volume', 0) or candle.get('Volume', 0))
            
            if high == low:
                continue
                
            # Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)
            mf_mult = ((close - low) - (high - close)) / (high - low)
            mf_volume = mf_mult * volume
            
            mf_volume_sum += mf_volume
            volume_sum += volume
            
        if volume_sum == 0:
            return 50.0
            
        cmf = mf_volume_sum / volume_sum
        
        # Normalize CMF (-1 to 1) to Score (0-100)
        # CMF > 0.2 is very bullish (approx score 80-100)
        # CMF < -0.2 is very bearish (approx score 0-20)
        
        score = 50 + (cmf * 250) # Scale: 0.2 -> 100, -0.2 -> 0
        score = max(0, min(100, score)) # Clamp
        
        return round(score, 2)

# Global Instance
bandarmology_engine = BandarmologyEngine()
def analyze_broker_summary(broker_data):
    return bandarmology_engine.analyze_broker_summary(broker_data)
