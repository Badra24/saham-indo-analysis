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
