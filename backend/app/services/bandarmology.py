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
            "graph_analysis": self.build_broker_graph(broker_data),
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
        return round(score, 2)

    def get_ml_features(self, broker_data: Optional[Dict]) -> Dict:
        """
        Extract numerical features suitable for Machine Learning models.
        
        Returns:
            Dict with numerical keys: 'bcr', 'retail_flow_ratio', 'foreign_flow_ratio'
        """
        summary = self.analyze_broker_summary(broker_data)
        
        # Default neutral values if data invalid
        if summary['status'] == 'DATA_UNAVAILABLE':
            return {
                'bcr': 1.0,
                'retail_flow_ratio': 0.0,
                'foreign_flow_ratio': 0.0,
                'accumulation_score': 0.5 # 0.5 = Neutral
            }
            
        # 1. BCR (Log transform often better for outliers, but raw is ok for Tree models)
        bcr = summary.get('concentration_ratio', 1.0)
        
        # 2. Accumulation Score
        # Map string status to number
        status_map = {
            'BIG_DISTRIBUTION': 0.0,
            'DISTRIBUTION': 0.25,
            'NEUTRAL': 0.5,
            'ACCUMULATION': 0.75,
            'BIG_ACCUMULATION': 1.0,
            'ACCUMULATION_TERSELUBUNG': 0.8 # Hidden acc is bullish
        }
        acc_score = status_map.get(summary.get('status', 'NEUTRAL'), 0.5)
        
        return {
            'bcr': bcr,
            'accumulation_score': acc_score,
            # Placeholder for flows until we ingest full Broker Code clusters
            'retail_flow_ratio': 0.0, 
            'foreign_flow_ratio': 0.0
        }
    
    def calculate_aqs(self, broker_history: List[Dict], price_history: List[float], 
                      current_broker_data: Optional[Dict] = None) -> Dict:
        """
        Calculate Accumulation Quality Score (AQS) - Composite metric.
        
        Formula: AQS = (0.4 × C) + (0.3 × K) + (0.3 × P)
        
        Where:
        - C = Concentration (Top3 Net Buy / Total Volume)
        - K = Consistency (Days with Net Buy > 0 / N days)
        - P = Price Control (Correlation between Top1 flow and price change)
        
        Reference: Research Thesis Section 4.1
        
        Args:
            broker_history: List of daily broker summaries (last 20 days)
            price_history: List of closing prices (last 21 days for diff)
            current_broker_data: Current day broker data for concentration
            
        Returns:
            Dict with aqs score and components
        """
        import numpy as np
        
        try:
            # Default values if insufficient data
            if len(price_history) < 5:
                return {
                    "aqs": 50.0,
                    "grade": "C",
                    "concentration": 0.5,
                    "consistency": 0.5,
                    "price_control": 0.0,
                    "note": "Insufficient historical data"
                }
            
            # C - Concentration (from current day or latest)
            if current_broker_data:
                analysis = self.analyze_broker_summary(current_broker_data)
                bcr = analysis.get('bcr', 1.0)
                concentration = min(bcr / 3.0, 1.0)  # Normalize to 0-1 (BCR 3+ = max)
            else:
                concentration = 0.5
            
            # K - Consistency (rolling N days net buy positive)
            if broker_history and len(broker_history) > 0:
                net_buys = []
                for day in broker_history[-20:]:
                    buyers = day.get('top_buyers', [])
                    sellers = day.get('top_sellers', [])
                    buy_val = sum(float(b.get('value', b.get('val', 0))) for b in buyers[:3])
                    sell_val = sum(float(s.get('value', s.get('val', 0))) for s in sellers[:3])
                    net_buys.append(buy_val - sell_val)
                
                n_days = len(net_buys) if net_buys else 1
                positive_days = sum(1 for nb in net_buys if nb > 0)
                consistency = positive_days / n_days
            else:
                consistency = 0.5
            
            # P - Price Control (correlation between flow and price change)
            if len(price_history) >= 5:
                price_changes = np.diff(price_history[-21:]) if len(price_history) >= 21 else np.diff(price_history)
                
                if broker_history and len(broker_history) >= len(price_changes):
                    # Get top1 flows aligned with price changes
                    top1_flows = []
                    for day in broker_history[-len(price_changes):]:
                        buyers = day.get('top_buyers', [])
                        sellers = day.get('top_sellers', [])
                        top1_buy = float(buyers[0].get('value', 0)) if buyers else 0
                        top1_sell = float(sellers[0].get('value', 0)) if sellers else 0
                        top1_flows.append(top1_buy - top1_sell)
                    
                    if len(top1_flows) == len(price_changes) and len(top1_flows) > 2:
                        corr_matrix = np.corrcoef(top1_flows, price_changes)
                        price_control = corr_matrix[0, 1] if not np.isnan(corr_matrix[0, 1]) else 0
                    else:
                        price_control = 0
                else:
                    price_control = 0
            else:
                price_control = 0
            
            # Calculate AQS (0-100 scale)
            aqs_raw = (0.4 * concentration) + (0.3 * consistency) + (0.3 * max(0, price_control))
            aqs = round(aqs_raw * 100, 2)
            
            # Grade assignment
            if aqs >= 80:
                grade = "A"
            elif aqs >= 60:
                grade = "B"
            elif aqs >= 40:
                grade = "C"
            elif aqs >= 20:
                grade = "D"
            else:
                grade = "E"
            
            return {
                "aqs": aqs,
                "grade": grade,
                "concentration": round(concentration, 3),
                "consistency": round(consistency, 3),
                "price_control": round(price_control, 3),
                "interpretation": self._interpret_aqs(aqs, concentration, consistency, price_control)
            }
            
        except Exception as e:
            return {
                "aqs": 50.0,
                "grade": "C",
                "error": str(e)
            }
    
    def _interpret_aqs(self, aqs: float, c: float, k: float, p: float) -> str:
        """Generate human-readable AQS interpretation."""
        parts = []
        
        if aqs >= 70:
            parts.append("Strong accumulation quality")
        elif aqs >= 50:
            parts.append("Moderate accumulation")
        else:
            parts.append("Weak/No accumulation")
        
        if c >= 0.7:
            parts.append("highly concentrated buying")
        if k >= 0.7:
            parts.append("consistent daily buying")
        if p >= 0.5:
            parts.append("bandar controls price")
        elif p < 0:
            parts.append("price moves against bandar flow")
        
        return "; ".join(parts) if parts else "Neutral"
    
    def calculate_churn_ratio(self, total_volume: float, net_ownership_change: float,
                               price_change_pct: float = 0) -> Dict:
        """
        Detect potential wash trading / churning activity.
        
        Formula: Churn Ratio = Total Volume / |Net Ownership Change|
        
        Interpretation:
        - High Churn + Price Up = Distribution (Fake Move) - BEARISH
        - Low Churn + Price Up = Genuine Accumulation - BULLISH
        - High Churn + Price Flat = Wash Trading - AVOID
        
        Reference: Research Thesis Section 8, Point 2
        
        Args:
            total_volume: Total trading volume
            net_ownership_change: Net change in ownership (buy - sell)
            price_change_pct: Price change percentage (optional, for context)
            
        Returns:
            Dict with churn_ratio and interpretation
        """
        if net_ownership_change == 0:
            return {
                "churn_ratio": float('inf'),
                "level": "EXTREME",
                "warning": "PURE_CHURNING",
                "signal": "AVOID",
                "interpretation": "Zero net change with volume = Pure wash trading"
            }
        
        churn = abs(total_volume / net_ownership_change)
        
        # Determine churn level
        if churn > 10:
            level = "EXTREME"
            base_warning = "EXTREME_CHURN"
        elif churn > 5:
            level = "HIGH"
            base_warning = "HIGH_CHURN_RISK"
        elif churn > 2:
            level = "MODERATE"
            base_warning = "MODERATE_CHURN"
        else:
            level = "LOW"
            base_warning = "GENUINE_ACTIVITY"
        
        # Context with price movement
        if level in ["HIGH", "EXTREME"] and price_change_pct > 1:
            signal = "BEARISH"
            interpretation = f"High churn ({churn:.1f}x) with price up {price_change_pct:.1f}% = Likely distribution/fake move"
        elif level in ["HIGH", "EXTREME"] and price_change_pct < -1:
            signal = "BULLISH_REVERSAL"
            interpretation = f"High churn ({churn:.1f}x) with price down = Possible accumulation shakeout"
        elif level == "LOW" and price_change_pct > 1:
            signal = "BULLISH"
            interpretation = f"Low churn ({churn:.1f}x) with price up = Genuine accumulation"
        elif level == "LOW":
            signal = "NEUTRAL"
            interpretation = f"Low churn ({churn:.1f}x) = Normal trading activity"
        else:
            signal = "CAUTION"
            interpretation = f"Churn ratio {churn:.1f}x - Monitor closely"
        
        return {
            "churn_ratio": round(churn, 2),
            "level": level,
            "warning": base_warning,
            "signal": signal,
            "interpretation": interpretation
        }

    def calculate_hhi(self, broker_data: Dict) -> Dict:
        """
        Calculate Herfindahl-Hirschman Index (HHI) for broker concentration.
        
        Formula: Sum of squared market shares per broker.
        HHI Range: 0 to 10000
        - HHI < 1500: Fragmented (Retail Distributed)
        - 1500 < HHI < 2500: Moderately Concentrated
        - HHI > 2500: Highly Concentrated (Bandar Dominant)
        """
        buyers = broker_data.get('top_buyers', [])
        
        # Calculate Total Buy Value of Top Buyers (as proxy for market accumulation)
        buy_value_total = sum(float(b.get('value', 0)) for b in buyers)
        
        if buy_value_total == 0:
             return {"hhi_buy": 0, "interpretation": "NO DATA"}
             
        # Calculate HHI based on accumulation share
        hhi_buy = sum((float(b['value']) / buy_value_total * 100) ** 2 for b in buyers)
            
        interpretation = "FRAGMENTED"
        if hhi_buy > 2500:
            interpretation = "HIGHLY_CONCENTRATED"
        elif hhi_buy > 1500:
            interpretation = "MODERATE"
            
        return {
            "hhi_buy": round(hhi_buy, 2),
            "interpretation": interpretation
        }

    def calculate_bandar_vwap(self, broker_data: Dict) -> Dict:
        """
        Calculate Volume Weighted Average Price (VWAP) of the Top 3 Net Buyers.
        This acts as the 'Bandar's Average Price' - a dynamic support level.
        """
        top_buyers = broker_data.get('top_buyers', [])[:3] # Focus on Top 3 (Bandar core)
        
        total_vol = 0
        weighted_price_sum = 0
        
        for b in top_buyers:
            vol = float(b.get('volume', 0))
            val = float(b.get('value', 0))
            if vol > 0:
                avg_price = val / vol 
                weighted_price_sum += (avg_price * vol)
                total_vol += vol
                
        if total_vol == 0:
            return {"bandar_vwap": 0}
            
        bandar_vwap = weighted_price_sum / total_vol
        return {"bandar_vwap": int(bandar_vwap)}

    def build_broker_graph(self, broker_data: Dict) -> Dict:
        """
        Builds a Network Graph of Broker Interaction (Phase 18).
        Since we don't have tick-by-tick data, we use 'Value Matching Heuristic'.
        
        Logic:
        - If Broker A Buys 10B and Broker B Sells 10B (+/- 5%) on the same day,
          we infer a HIGH probability of 'Direct Transfer' (Crossing/Nego/Match).
          
        Returns:
            Dict with 'clusters', 'central_node', 'suspicious_edges'.
        """
        import networkx as nx
        
        if not broker_data or not broker_data.get('top_buyers') or not broker_data.get('top_sellers'):
            return {}
            
        buyers = broker_data.get('top_buyers', [])
        sellers = broker_data.get('top_sellers', [])
        
        G = nx.DiGraph()
        
        suspicious_flows = []
        
        # 1. Build Nodes & Heuristic Edges
        for buyer in buyers:
            b_code = buyer['code']
            b_val = float(buyer['value'])
            
            for seller in sellers:
                s_code = seller['code']
                s_val = float(seller['value'])
                
                # Check for Value Match (Cluster)
                # If values match within 5%, assume connection
                if b_val > 0 and s_val > 0:
                    ratio = min(b_val, s_val) / max(b_val, s_val)
                    if ratio > 0.95:
                        G.add_edge(s_code, b_code, weight=s_val)
                        suspicious_flows.append({
                            "from": s_code,
                            "to": b_code,
                            "value": s_val,
                            "type": "POSSIBLE_CROSSING"
                        })

        # 2. Analyze Graph
        if G.number_of_nodes() == 0:
            return {"status": "NO_CLUSTERS", "central_broker": None}
            
        # Centrality (Who is the Kingpin?)
        try:
            centrality = nx.eigenvector_centrality(G, max_iter=1000, tolerance=1e-06)
            central_broker = max(centrality, key=centrality.get)
        except:
             # Fallback if graph is not connected
             degrees = dict(G.degree(weight='weight'))
             central_broker = max(degrees, key=degrees.get) if degrees else None

        # Detect Cycles (Wash Trading: A->B->A)
        try:
            cycles = list(nx.simple_cycles(G))
        except:
            cycles = []
            
        return {
            "graph_summary": f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}",
            "central_broker": central_broker,
            "suspicious_flows": suspicious_flows,
            "wash_trading_loops": cycles
        }

# Global Instance
bandarmology_engine = BandarmologyEngine()
def analyze_broker_summary(broker_data):
    return bandarmology_engine.analyze_broker_summary(broker_data)
