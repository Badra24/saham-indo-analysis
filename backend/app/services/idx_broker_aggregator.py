"""
IDX Broker Aggregator - Wrapper for Stockbit Broker Summary

MIGRATION NOTE:
Formerly wrapped GoAPI. Now wraps StockbitClient (Free & More Accurate).
"""

from typing import Optional, Dict, List
import logging
from app.services.stockbit_client import stockbit_client

logger = logging.getLogger(__name__)

# ==================== STOCKBIT WRAPPER ====================

class IDXBrokerAggregatorFast:
    """
    Wrapper for Stockbit broker summary.
    Replaces the old GoAPI implementation.
    """
    
    def __init__(self):
        self._client = stockbit_client
    
    async def get_broker_summary_for_stock(
        self,
        stock_code: str,
        date_str: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict:
        """
        Get broker summary for a specific stock via Stockbit.
        
        Args:
            stock_code: Stock ticker (e.g., 'BBCA')
            date_str: Ignored for now (Stockbit endpoint is real-time/daily)
            use_cache: Ignored
        
        Returns:
            Broker summary in standardized format.
        """
        stock_code = stock_code.upper().replace(".JK", "")
        
        # print(f"[BROKER-AGG] Fetching broker summary for {stock_code} via Stockbit...")
        
        try:
            # Fetch from Stockbit
            data = await self._client.get_bandarmology(stock_code)
            
            if not data:
                return self._empty_response(stock_code)
                
            # Map Stockbit response to our standardized APP format
            # Stockbit returns: top_buyers list with {code, val}
            
            top_buyers = []
            for b in data.get('top_buyers', []):
                top_buyers.append({
                    "code": b['code'],
                    "value": b['val'],
                    "volume": 0 # Stockbit summary above doesn't give volume, only val. Acceptable.
                })

            top_sellers = []
            for s in data.get('top_sellers', []):
                top_sellers.append({
                    "code": s['code'],
                    "value": abs(s['val']), # Stockbit sends sellers as negative value in some contexts, but let's ensure positive for "value" field
                    "volume": 0
                })
                
            # Calculate Net Flow (Bandar Volume)
            # We use the top1_amount provided by Stockbit as a proxy for main flow
            net_flow = data.get('total_buyer', 0) # This might be count.
            # actually data['top1_amount'] is the net value of Top 1. 
            # But let's use the sum of Top 5 Net for a broader view if needed.
            # For compatibility, let's trust Stockbit's "bandar detector" status more than raw flow numbers.
            
            return {
                "symbol": stock_code,
                "status": data.get('avg5_status', 'NEUTRAL').upper().replace(" ", "_"), # Big Acc -> BIG_ACC
                "net_flow": data.get('net_value', data.get('top1_amount', 0)), # Use calculated net val if available
                "buy_value": data.get('buy_value', 0),
                "sell_value": data.get('sell_value', 0),
                "top_buyers": top_buyers[:5], # We only show top 5 in UI summary usually
                "top_sellers": top_sellers[:5], 
                "source": "stockbit",
                "is_demo": False,
                "timestamp": date_str
            }
            
        except Exception as e:
            logger.error(f"Stockbit Aggregator failed for {stock_code}: {e}")
            return self._empty_response(stock_code)
    
    async def get_broker_history(self, stock_code: str, broker_code: str, days: int = 30) -> Dict:
        """
        Get broker activity for the last N days using Stockbit's from/to parameters.
        
        OPTIMIZED: Uses SINGLE API call instead of 30 parallel calls.
        Stockbit automatically aggregates data for the date range.
        """
        from datetime import datetime, timedelta
        
        stock_code = stock_code.upper().replace(".JK", "")
        broker_code = broker_code.upper()
        
        # Limit days
        days = min(max(days, 5), 60)
        
        # Calculate date range
        today = datetime.now()
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        try:
            # SINGLE API CALL for cumulative data
            data = await self._client.get_bandarmology(
                stock_code, 
                start_date=start_date, 
                end_date=end_date
            )
            
            if not data:
                return self._empty_broker_history(stock_code, broker_code, days)
            
            # Find broker in top_buyers or top_sellers
            broker_buy_val = 0
            broker_sell_val = 0
            broker_found = False
            
            for b in data.get('top_buyers', []):
                if b['code'] == broker_code:
                    broker_buy_val = float(b['val'])
                    broker_found = True
                    break
            
            for s in data.get('top_sellers', []):
                if s['code'] == broker_code:
                    broker_sell_val = abs(float(s['val']))
                    broker_found = True
                    break
            
            net_total = broker_buy_val - broker_sell_val
            
            # Determine Trend
            if net_total > 1_000_000_000:
                trend = "AKUMULASI_AKTIF"
            elif net_total < -1_000_000_000:
                trend = "DISTRIBUSI_AKTIF"
            else:
                trend = "NETRAL"
            
            return {
                "broker_code": broker_code,
                "broker_name": broker_code,
                "broker_type": "UNKNOWN",
                "is_foreign": broker_code in ["CC", "ML", "YP", "CS", "DB", "GS", "JP", "MS", "UB"],
                "symbol": stock_code,
                "period": f"{start_date} to {end_date}",
                "days_analyzed": days,
                "active_days": days if broker_found else 0,
                "running_buy": broker_buy_val,
                "running_sell": broker_sell_val,
                "running_position": net_total,
                "trend": trend,
                "source": "stockbit",
                "is_demo": False,
                # Additional context from overall market
                "market_buy_value": data.get('buy_value', 0),
                "market_sell_value": data.get('sell_value', 0),
                "market_net_value": data.get('net_value', 0),
                "top1_status": data.get('top1_status', 'NEUTRAL'),
                "avg5_status": data.get('avg5_status', 'NEUTRAL'),
            }
            
        except Exception as e:
            logger.error(f"Broker history fetch failed for {broker_code}@{stock_code}: {e}")
            return self._empty_broker_history(stock_code, broker_code, days)
    
    def _empty_broker_history(self, stock_code: str, broker_code: str, days: int) -> Dict:
        return {
            "broker_code": broker_code,
            "symbol": stock_code,
            "days_analyzed": days,
            "running_buy": 0,
            "running_sell": 0,
            "running_position": 0,
            "trend": "DATA_UNAVAILABLE",
            "source": "stockbit_error",
            "is_demo": False
        }
    
    def _empty_response(self, symbol: str) -> Dict:
        return {
            "symbol": symbol,
            "status": "DATA_UNAVAILABLE",
            "net_flow": 0,
            "top_buyers": [],
            "top_sellers": [],
            "source": "stockbit_error",
            "is_demo": False
        }
    
    async def close(self):
        pass


# Singleton
_aggregator: Optional[IDXBrokerAggregatorFast] = None

def get_broker_aggregator() -> IDXBrokerAggregatorFast:
    """Get singleton aggregator"""
    global _aggregator
    if _aggregator is None:
        _aggregator = IDXBrokerAggregatorFast()
    return _aggregator


# ==================== TEST ====================

if __name__ == "__main__":
    import asyncio
    import time
    import sys
    import os
    
    # Add project root to sys.path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
    
    from dotenv import load_dotenv
    
    # Load Env for test
    load_dotenv("backend/.env")
    
    async def test():
        print("=" * 60)
        print("BROKER AGGREGATOR TEST (Stockbit Backend)")
        print("=" * 60)
        print()
        
        agg = get_broker_aggregator()
        
        start = time.time()
        result = await agg.get_broker_summary_for_stock("BBCA")
        elapsed = time.time() - start
        
        print()
        print(f"Result for BBCA:")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Status: {result.get('status')}")
        print(f"  Source: {result.get('source')}")
        print(f"  Net Flow: {result.get('net_flow', 0):,.0f}")
        
        if result.get('top_buyers'):
            print(f"  Top Buyers: {len(result['top_buyers'])}")
            for i, buyer in enumerate(result['top_buyers'][:3]):
                print(f"    {i+1}. {buyer.get('code', 'N/A')} - {buyer.get('value', 0):,.0f}")
        
        print()
        print("=" * 60)
    
    asyncio.run(test())
