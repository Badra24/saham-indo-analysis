import random
from datetime import date, timedelta
from typing import List, Dict
from app.services.idx_static_data import BROKER_CLASSIFICATION

class MockDataGenerator:
    """
    Generates realistic Mock Broker Summary History
    when API rate limits are reached.
    
    Phases:
    1. Accumulation (Big Players buy, Retail sell)
    2. Markup (Price up, Mixed)
    3. Distribution (Big Players sell, Retail buy)
    """
    
    def generate_mock_history(self, ticker: str, days: int = 30) -> List[Dict]:
        """
        Generate a list of daily stats for the last N days.
        """
        history = []
        end_date = date.today()
        
        # Define a consistent "Scenario" for the ticker based on hash
        # so it doesn't change on every refresh
        seed = sum(ord(c) for c in ticker)
        random.seed(seed)
        
        # Assign a random phase sequence
        phase_map = ["ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN"]
        current_phase = phase_map[seed % 4]
        
        for i in range(days):
            day = end_date - timedelta(days=days-i-1)
            
            # Skip weekends
            if day.weekday() > 4:
                continue
                
            # Generate daily data based on phase
            daily_data = self._generate_daily_data(ticker, day, current_phase)
            history.append(daily_data)
            
            # Possibility to switch phase every 5-7 days
            if i % 7 == 0 and random.random() > 0.7:
                 current_phase = random.choice(phase_map)
                 
        return history
        
    def _generate_daily_data(self, ticker: str, date_obj: date, phase: str) -> Dict:
        """
        Create a single day's broker summary logic.
        """
        
        # Brokers
        institutions = [k for k,v in BROKER_CLASSIFICATION.items() if v['type'] == 'INSTITUTION']
        retails = [k for k,v in BROKER_CLASSIFICATION.items() if v['type'] == 'RETAIL']
        
        # Default Logic
        if phase == "ACCUMULATION":
            # Inst Buy, Retail Sell
            buyers = random.sample(institutions, 3)
            sellers = random.sample(retails, 3)
            buy_power = random.uniform(5000000000, 15000000000) # 5-15B
            sell_power = buy_power * 0.6 # Low supply
            
        elif phase == "DISTRIBUTION":
            # Inst Sell, Retail Buy
            buyers = random.sample(retails, 3)
            sellers = random.sample(institutions, 3)
            sell_power = random.uniform(5000000000, 15000000000)
            buy_power = sell_power * 0.7
            
        else: # Neutral/Markup
            mixed = institutions + retails
            buyers = random.sample(mixed, 3)
            sellers = random.sample(mixed, 3)
            buy_power = random.uniform(2000000000, 5000000000)
            sell_power = buy_power * random.uniform(0.9, 1.1)
            
        # Construct Broker Rows
        top_buyers = []
        for b in buyers:
            val = buy_power * random.uniform(0.2, 0.5)
            top_buyers.append({
                "code": b,
                "value": int(val),
                "volume": int(val / 500), # Assume px 500
                "type": BROKER_CLASSIFICATION[b]['type'],
                "is_foreign": BROKER_CLASSIFICATION[b]['is_foreign']
            })
            
        top_sellers = []
        for s in sellers:
            val = sell_power * random.uniform(0.2, 0.5)
            top_sellers.append({
                "code": s,
                "value": int(val),
                "volume": int(val / 500),
                "type": BROKER_CLASSIFICATION[s]['type'],
                "is_foreign": BROKER_CLASSIFICATION[s]['is_foreign']
            })
            
        # Calculate Stats
        total_buy = sum(b['value'] for b in top_buyers)
        total_sell = sum(s['value'] for s in top_sellers)
        
        # Calc BCR
        bcr = 1.0
        if total_sell > 0:
            bcr = total_buy / total_sell
            
        # Net Flows
        inst_net_flow = 0
        retail_net_flow = 0
        foreign_net_flow = 0
        
        for b in top_buyers:
            if b['type'] == 'INSTITUTION': inst_net_flow += b['value']
            if b['type'] == 'RETAIL': retail_net_flow += b['value']
            if b['is_foreign']: foreign_net_flow += b['value']
            
        for s in top_sellers:
            if s['type'] == 'INSTITUTION': inst_net_flow -= s['value']
            if s['type'] == 'RETAIL': retail_net_flow -= s['value']
            if s['is_foreign']: foreign_net_flow -= s['value']
            
        return {
            "date": date_obj,
            "status": phase,
            "concentration_ratio": bcr * 30, # Scale to %
            "top_buyers": top_buyers,
            "top_sellers": top_sellers,
            "institutional_net_flow": inst_net_flow,
            "retail_net_flow": retail_net_flow,
            "foreign_net_flow": foreign_net_flow,
            "source": "mock"
        }

mock_generator = MockDataGenerator()
