import asyncio
from datetime import date
from typing import Optional, Dict, List, Any

from .browser import IDXBrowser
from .cache import BrowserCache

class IDXBrowserClient:
    """
    Client for interacting with IDX data via Browser Automation.
    Optimized to hit JSON endpoints directly where possible.
    """
    
    IDX_BASE_URL = "https://www.idx.co.id"
    
    # Endpoints
    API_BROKER_SUMMARY = "https://www.idx.co.id/primary/TradingSummary/GetBrokerSummary"
    API_STOCK_SUMMARY = "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
    API_BROKE_SEARCH = "https://www.idx.co.id/primary/MemberParticipants/GetBrokerSearch"
    
    # Cache TTLs
    TTL_BROKER_SUMMARY = 300   # 5 mins
    TTL_STOCK_SUMMARY = 300    # 5 mins
    TTL_COMPANY_LIST = 3600    # 1 hour
    
    def __init__(self):
        self.browser_manager = None # Lazy init via get_instance
        self.cache = BrowserCache()
        
    async def _get_browser(self):
        if not self.browser_manager:
            self.browser_manager = await IDXBrowser.get_instance()
        return self.browser_manager

    async def get_broker_summary(self, symbol: str, date_str: Optional[str] = None) -> Optional[Dict]:
        """
        Get Broker Summary.
        
        NOTE: The IDX API endpoint returns the summary of ALL BROKERS (Total Buy/Sell Value).
        It does NOT currently support filtering by Stock Symbol via this endpoint.
        The 'symbol' argument is kept for compatibility but currently ignored by IDXs public API.
        
        Args:
            symbol: (Ignored by API) Stock symbol 
            date_str: Date in YYYY-MM-DD format
        """
        if not date_str:
            date_str = date.today().strftime("%Y-%m-%d")
            
        # Cache Key (Symbol is included in key to separate cache if future impl supports it, 
        # but realistically it's the same data for all calls on same date)
        # Using 'global' to indicate it's global data
        cache_key = f"broker_summary_global_{date_str}"
        
        cached = self.cache.get(cache_key, self.TTL_BROKER_SUMMARY)
        if cached:
            return cached
            
        browser = await self._get_browser()
        
        # params: length=9999&start=0&date=YYYYMMDD
        # Date format for API seems to be YYYYMMDD based on idx-bei/getBrokerSummary.js
        # Wait, getBrokerSummary.js uses YYYYMMDD?
        # Let's check the date format passed. The python client passed YYYY-MM-DD to the PAGE.
        # But `getBrokerSummary.js` does `date` param.
        # I will assume YYYY-MM-DD or YYYYMMDD.
        # Let's try to match what the page typically expects. 
        # Actually `date_str` passed to this function is usually YYYY-MM-DD.
        
        # API usually expects YYYYMMDD for JSON endpoints? 
        # The node js code says: "date... (format: YYYYMMDD)" in docstring.
        date_param = date_str.replace("-", "")
        
        url = f"{self.API_BROKER_SUMMARY}?length=9999&start=0&date={date_param}"
        
        data = await browser.fetch_json(url)
        
        if data:
            self.cache.set(cache_key, data)
            
        return data

    async def get_stock_summary(self, symbol: str = None, date_str: Optional[str] = None) -> Optional[Dict]:
        """
        Get Stock Summary.
        Only returns data for the specific symbol if provided.
        Otherwise triggers full fetch and filters.
        """
        if not date_str:
            date_str = date.today().strftime("%Y-%m-%d")
            
        # We fetch ALL stocks because the API supports it efficiently
        cache_key_all = f"stock_summary_all_{date_str}"
        
        data = self.cache.get(cache_key_all, self.TTL_STOCK_SUMMARY)
        
        if not data:
            browser = await self._get_browser()
            date_param = date_str.replace("-", "")
            url = f"{self.API_STOCK_SUMMARY}?length=9999&start=0&date={date_param}"
            
            data = await browser.fetch_json(url)
            if data:
                 self.cache.set(cache_key_all, data)
        
        if not data:
            return None
            
        # If symbol requested, filtering
        if symbol:
            symbol_clean = symbol.replace(".JK", "").upper()
            results = data.get("data", [])
            # Filter
            filtered = [s for s in results if s.get("StockCode") == symbol_clean or s.get("KodeSaham") == symbol_clean]
            
            # Construct a response looking like the full one but limited results
            return {
                "recordsTotal": len(filtered),
                "recordsFiltered": len(filtered),
                "data": filtered,
                "draw": data.get("draw", 0)
            }
            
        return data

    async def get_all_brokers(self) -> Optional[List[Dict]]:
        """Get list of all brokers"""
        cache_key = "all_brokers"
        cached = self.cache.get(cache_key, self.TTL_COMPANY_LIST)
        if cached:
            return cached
            
        browser = await self._get_browser()
        # length=999 is guess, usually needed for DataTables endpoints
        url = f"{self.API_BROKE_SEARCH}?length=1000&start=0"
        
        data = await browser.fetch_json(url)
        if data and "data" in data:
            brokers = data["data"]
            self.cache.set(cache_key, brokers)
            return brokers
            
        return None

    async def close(self):
        if self.browser_manager:
            await self.browser_manager.close()

# Singleton
_client: Optional[IDXBrowserClient] = None

def get_idx_browser_client() -> IDXBrowserClient:
    global _client
    if _client is None:
        _client = IDXBrowserClient()
    return _client

async def test_client():
    """Test the client"""
    client = get_idx_browser_client()
    print("Testing IDXBrowserClient...")
    
    try:
        # 1. Test Stock Summary (cached global + filter)
        print("\n1. Fetching Stock Summary for BBCA...")
        summary = await client.get_stock_summary("BBCA")
        if summary:
            print(f"   Success! Data: {summary.get('data', [])[:1]}")
        else:
            print("   Failed.")

        # 2. Test Broker Summary
        print("\n2. Fetching Broker Summary (Global)...")
        # Trying with a symbol just to show api call works
        bsul = await client.get_broker_summary("BBCA") 
        if bsul:
            print(f"   Success! Records: {len(bsul.get('data', []))}")
            if bsul.get('data'):
                print(f"   Sample: {bsul.get('data')[0]}")
        else:
            print("   Failed.")
            
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_client())
