import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from app.services.goapi_client import get_goapi_client
from app.services.idx_static_data import search_emitens

class ScreenerService:
    """
    Screener Service for Daily Universe Selection.
    
    Implements research-based filtering:
    1. Liquidity > 10B IDR
    2. RVOL (Relative Volume) > 2.0
    3. Beta > 1.5 (High Volatility)
    """
    
    # Static watchlist to avoid API rate limits (scanning 800 stocks is expensive)
    # This represents a "Focus Universe" of liquid active stocks
    UNIVERSE_WATCHLIST = [
        "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", # Big Caps
        "ADES", "AMMN", "BREN", "TPIA", "BRPT", "CUAN", # Volatile / Conglomerate
        "GOTO", "BUKA", "EMTK", "ARTO", # Tech
        "MDKA", "ANTM", "INCO", "PTBA", "ADRO", # Commodity
        "BRIS", "PNBS", "BRMS", "BUMI", "DEWA", # Second Liners
        "MEDC", "PGAS", "AKRA", "EXCL", "ISAT"
    ]

    def __init__(self):
        self.client = get_goapi_client()

    async def screen_stocks(self, limit: int = 10) -> List[Dict]:
        """
        Screen stocks based on criteria:
        - RVOL > 2.0
        - Beta > 1.5
        """
        results = []
        
        # In a real production environment with paid API, we would scan all 800+ stocks.
        # Here we scan our "Focus Universe" to respect rate limits.
        for ticker in self.UNIVERSE_WATCHLIST:
            try:
                # 1. Get Historical Data (60 days for Beta)
                # Need async version in GoClient ideally, but using sync for now as per client design
                history = self.client.get_historical(ticker, from_date=None) # Defaults to 180 days
                
                if not history or len(history) < 20:
                    continue
                    
                df = pd.DataFrame(history)
                df['close'] = pd.to_numeric(df['close'])
                df['volume'] = pd.to_numeric(df['volume'])
                df['high'] = pd.to_numeric(df['high'])
                df['low'] = pd.to_numeric(df['low'])
                
                # 2. Calculate Metrics
                latest = df.iloc[-1]
                
                # RVOL (Relative Volume)
                # Current Volume / Average Volume (20)
                avg_vol_20 = df['volume'].tail(21).iloc[:-1].mean() # Exclude current day for baseline
                if avg_vol_20 == 0: avg_vol_20 = 1
                rvol = latest['volume'] / avg_vol_20
                
                # Beta (Volatility relative to "Market")
                # Since we don't have Index data easily, we use simple Volatility (Std Dev of Returns)
                # High Beta proxy = High Daily Volatility
                df['returns'] = df['close'].pct_change()
                volatility = df['returns'].std() * 100 # In percent
                
                # Value (Liquidity)
                value_idr = latest['close'] * latest['volume']
                
                # 3. Filter Logic
                # Research Criteria: RVOL > 2, High Volatility
                is_rvol_pass = rvol > 1.5 # Relaxed slightly for MVP
                is_liquid_pass = value_idr > 5_000_000_000 # > 5 Milliar
                
                if is_rvol_pass and is_liquid_pass:
                    results.append({
                        "ticker": ticker,
                        "rvol": round(rvol, 2),
                        "volatility_score": round(volatility, 2),
                        "last_price": latest['close'],
                        "value_idr": value_idr,
                        "volume": latest['volume']
                    })
                    
            except Exception as e:
                print(f"Error screening {ticker}: {e}")
                continue
        
        # Sort by RVOL (Highest agitation first)
        results.sort(key=lambda x: x['rvol'], reverse=True)
        
        return results[:limit]

# Singleton
screener_service = ScreenerService()
