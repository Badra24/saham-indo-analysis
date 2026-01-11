"""
IDX Broker Aggregator - Wrapper for GoAPI Broker Summary

IMPORTANT DISCOVERY:
The IDX website does NOT provide a public API for per-stock broker breakdown!
- /TradingSummary/GetBrokerSummary only returns TOTAL per broker (not per stock)
- There is no endpoint like /GetBrokerSummaryByStock

Therefore, we use GoAPI as the primary (and only) source for stock-specific 
broker data (who's buying/selling BBCA, etc.)

This module is a simple wrapper around goapi_client for compatibility.
"""

from typing import Optional, Dict, List
from datetime import date, timedelta

from app.services.goapi_client import get_goapi_client


# ==================== SIMPLE WRAPPER ====================

class IDXBrokerAggregatorFast:
    """
    Wrapper for GoAPI broker summary.
    
    Note: Despite the name, this uses GoAPI because IDX doesn't 
    provide per-stock broker breakdown via public API.
    """
    
    def __init__(self):
        self._goapi = get_goapi_client()
    
    async def get_broker_summary_for_stock(
        self,
        stock_code: str,
        date_str: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict:
        """
        Get broker summary for a specific stock.
        
        This directly uses GoAPI's get_broker_summary method.
        
        Args:
            stock_code: Stock ticker (e.g., 'BBCA')
            date_str: Date in YYYYMMDD format (optional)
            use_cache: Whether to use cached results
        
        Returns:
            Broker summary with top buyers, sellers, net flow, status
        """
        stock_code = stock_code.upper().replace(".JK", "")
        
        # Format date for GoAPI (YYYY-MM-DD)
        if date_str:
            # Convert YYYYMMDD to YYYY-MM-DD
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        else:
            # Use today or last trading day
            today = date.today()
            if today.weekday() >= 5:  # Weekend
                diff = today.weekday() - 4
                today = today - timedelta(days=diff)
            formatted_date = today.strftime("%Y-%m-%d")
        
        print(f"[BROKER-AGG] Fetching broker summary for {stock_code} ({formatted_date}) via GoAPI...")
        
        # Get data from GoAPI
        result = self._goapi.get_broker_summary(stock_code, formatted_date)
        
        if result.get("is_demo"):
            print(f"[BROKER-AGG] ⚠️ Daily Limit Reached for {stock_code}. Please upload Broker Summary file to calculate.")
        else:
            print(f"[BROKER-AGG] ✅ Got real data for {stock_code}")
        
        # Add source info
        result["source"] = "goapi"
        
        return result
    
    async def close(self):
        """No resources to cleanup for GoAPI wrapper"""
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
    
    async def test():
        print("=" * 60)
        print("BROKER AGGREGATOR TEST (GoAPI Backend)")
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
        print(f"  Is Demo: {result.get('is_demo')}")
        print(f"  Net Flow: {result.get('net_flow', 0):,.0f}")
        
        if result.get('top_buyers'):
            print(f"  Top Buyers: {len(result['top_buyers'])}")
            for i, buyer in enumerate(result['top_buyers'][:3]):
                print(f"    {i+1}. {buyer.get('code', 'N/A')} - {buyer.get('value', 0):,.0f}")
        
        if result.get('top_sellers'):
            print(f"  Top Sellers: {len(result['top_sellers'])}")
        
        print()
        print("=" * 60)
        
        await agg.close()
    
    asyncio.run(test())
