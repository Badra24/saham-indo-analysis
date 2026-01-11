"""
IDX-BEI Client - Direct Access to Indonesia Stock Exchange (IDX) Website API

This is a Python port of the idx-bei Node.js library patterns.
Provides data from idx.co.id without strict API rate limits.

Features:
- Broker Summary (broker buy/sell activity per stock)
- All Listed Companies (956+ emitens)
- Broker Search (all 93+ registered brokers)
- Trading Summary

No API key required - uses browser-like headers for access.
"""

import asyncio
import httpx
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
from functools import lru_cache


# ==================== CONFIGURATION ====================

BASE_URL = "https://www.idx.co.id/primary"

# Browser-like headers to avoid blocking (from idx-bei fetchUtil.js)
DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "id-id,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Referer": "https://www.idx.co.id/en/market-data/trading-summary/broker-summary/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
}

# Rate limiting: 5 requests per second
RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_MS = 1000

# Cache settings
CACHE_TTL_SECONDS = 300  # 5 minutes for broker data
COMPANY_CACHE_TTL_SECONDS = 3600  # 1 hour for company list


# ==================== IN-MEMORY CACHE ====================

class SimpleCache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if entry["expiry"] > time.time():
                return entry["data"]
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, data: Any, ttl_seconds: int = CACHE_TTL_SECONDS):
        self._cache[key] = {
            "data": data,
            "expiry": time.time() + ttl_seconds
        }
    
    def clear(self):
        self._cache.clear()


_cache = SimpleCache()


# ==================== RATE LIMITER ====================

class RateLimiter:
    """Simple rate limiter for API requests"""
    
    def __init__(self, max_requests: int = RATE_LIMIT_MAX_REQUESTS, window_ms: int = RATE_LIMIT_WINDOW_MS):
        self.max_requests = max_requests
        self.window_ms = window_ms
        self._requests: List[float] = []
    
    async def wait(self):
        """Wait if rate limit would be exceeded"""
        now = time.time() * 1000  # Convert to ms
        
        # Remove old requests outside window
        self._requests = [t for t in self._requests if now - t < self.window_ms]
        
        # If at limit, wait for oldest to expire
        if len(self._requests) >= self.max_requests:
            oldest = self._requests[0]
            wait_time = (oldest + self.window_ms - now) / 1000  # Convert to seconds
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self._requests.append(now)


_rate_limiter = RateLimiter()


# ==================== IDX-BEI CLIENT ====================

class IDXBEIClient:
    """
    Client for accessing IDX website API directly.
    No API key required - simulates browser requests.
    """
    
    def __init__(self):
        self.base_url = BASE_URL
        self.headers = DEFAULT_HEADERS.copy()
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            )
        return self._http_client
    
    async def _request(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None,
        cache_key: Optional[str] = None,
        cache_ttl: int = CACHE_TTL_SECONDS,
        retries: int = 3
    ) -> Optional[Dict]:
        """
        Make request to IDX API with caching and retry logic.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            cache_key: Optional cache key (auto-generated if not provided)
            cache_ttl: Cache TTL in seconds
            retries: Number of retry attempts
        """
        # Generate cache key
        if cache_key is None:
            param_str = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
            cache_key = f"{endpoint}?{param_str}"
        
        # Check cache
        cached = _cache.get(cache_key)
        if cached is not None:
            print(f"[IDX-BEI] Cache hit: {cache_key[:50]}...")
            return cached
        
        # Rate limiting
        await _rate_limiter.wait()
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                client = await self._get_client()
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    _cache.set(cache_key, data, cache_ttl)
                    print(f"[IDX-BEI] Fetched: {endpoint}")
                    return data
                    
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 2 ** attempt
                    print(f"[IDX-BEI] Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    
                else:
                    print(f"[IDX-BEI] HTTP {response.status_code} for {endpoint}")
                    
            except Exception as e:
                print(f"[IDX-BEI] Error (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(1)
        
        return None
    
    # ==================== BROKER SUMMARY ====================
    
    async def get_broker_summary(
        self, 
        symbol: str, 
        date_str: Optional[str] = None,
        investor: str = "ALL"
    ) -> Optional[Dict]:
        """
        Get broker summary for a stock on a given date.
        
        This shows which brokers are buying/selling the stock.
        Equivalent to: /TradingSummary/GetBrokerSummary in idx-bei
        
        Args:
            symbol: Stock symbol (e.g., 'BBCA')
            date_str: Date in YYYYMMDD format (default: today)
            investor: 'LOCAL', 'FOREIGN', or 'ALL'
        
        Returns:
            Broker summary data with buy/sell sides
        """
        symbol = symbol.upper().replace(".JK", "")
        
        if not date_str:
            # Use today's date
            date_str = date.today().strftime("%Y%m%d")
        else:
            # Convert YYYY-MM-DD to YYYYMMDD if needed
            date_str = date_str.replace("-", "")
        
        params = {
            "code": symbol,
            "date": date_str,
            "investor": investor,
            "length": 9999,
            "start": 0
        }
        
        result = await self._request(
            "/TradingSummary/GetBrokerSummary",
            params=params,
            cache_ttl=CACHE_TTL_SECONDS
        )
        
        # If today has no data, try yesterday
        if result is None or not result.get("data"):
            yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
            params["date"] = yesterday
            result = await self._request(
                "/TradingSummary/GetBrokerSummary",
                params=params,
                cache_ttl=CACHE_TTL_SECONDS
            )
        
        return result
    
    # ==================== STOCK SUMMARY ====================
    
    async def get_stock_summary(
        self, 
        date_str: Optional[str] = None,
        board: str = ""
    ) -> Optional[Dict]:
        """
        Get stock summary for all stocks on a given date.
        
        Args:
            date_str: Date in YYYYMMDD format
            board: Board filter (empty for all)
        """
        if not date_str:
            date_str = date.today().strftime("%Y%m%d")
        else:
            date_str = date_str.replace("-", "")
        
        params = {
            "date": date_str,
            "board": board,
            "length": 9999,
            "start": 0
        }
        
        return await self._request(
            "/TradingSummary/GetStockSummary",
            params=params,
            cache_ttl=CACHE_TTL_SECONDS
        )
    
    # ==================== BROKER SEARCH (All Brokers) ====================
    
    async def get_broker_search(self) -> Optional[Dict]:
        """
        Get list of all registered brokers/securities firms.
        
        Returns all 93+ brokers with their codes, names, and licenses.
        """
        params = {
            "option": 0,
            "license": "",
            "start": 0,
            "length": 9999
        }
        
        return await self._request(
            "/ExchangeMember/GetBrokerSearch",
            params=params,
            cache_ttl=COMPANY_CACHE_TTL_SECONDS  # Cache longer - rarely changes
        )
    
    async def get_broker_detail(self, code: str) -> Optional[Dict]:
        """Get detailed info for a specific broker"""
        params = {"code": code.upper()}
        return await self._request(
            "/ExchangeMember/GetBrokerDetail",
            params=params,
            cache_ttl=COMPANY_CACHE_TTL_SECONDS
        )
    
    # ==================== COMPANY PROFILES (All Emitens) ====================
    
    async def get_all_companies(self) -> Optional[Dict]:
        """
        Get list of all listed companies (956+ emitens).
        
        Returns complete company data including:
        - KodeEmiten (ticker)
        - NamaEmiten (company name)
        - Sektor (sector)
        - SubSektor (sub-sector)
        - TanggalPencatatan (listing date)
        """
        params = {
            "start": 0,
            "length": 9999
        }
        
        return await self._request(
            "/ListedCompany/GetListedCompany",
            params=params,
            cache_ttl=COMPANY_CACHE_TTL_SECONDS
        )
    
    async def get_company_profile(self, symbol: str) -> Optional[Dict]:
        """Get detailed profile for a specific company"""
        symbol = symbol.upper().replace(".JK", "")
        params = {"kodeEmiten": symbol}
        return await self._request(
            "/ListedCompany/GetCompanyProfile",
            params=params,
            cache_ttl=COMPANY_CACHE_TTL_SECONDS
        )
    
    # ==================== TRADING SUMMARY ====================
    
    async def get_trade_summary(self, date_str: Optional[str] = None) -> Optional[Dict]:
        """Get overall market trading summary"""
        if not date_str:
            date_str = date.today().strftime("%Y%m%d")
        else:
            date_str = date_str.replace("-", "")
        
        params = {"date": date_str}
        return await self._request(
            "/TradingSummary/GetTradeSummary",
            params=params,
            cache_ttl=CACHE_TTL_SECONDS
        )
    
    # ==================== INDEX SUMMARY ====================
    
    async def get_index_summary(self) -> Optional[Dict]:
        """Get summary of all indices (IHSG, LQ45, etc.)"""
        params = {"length": 9999, "start": 0}
        return await self._request(
            "/TradingSummary/GetIndexSummary",
            params=params,
            cache_ttl=CACHE_TTL_SECONDS
        )
    
    # ==================== CLEANUP ====================
    
    async def close(self):
        """Close the HTTP client"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


# ==================== SINGLETON INSTANCE ====================

_idx_bei_client: Optional[IDXBEIClient] = None


def get_idx_bei_client() -> IDXBEIClient:
    """Get or create IDX-BEI client instance"""
    global _idx_bei_client
    if _idx_bei_client is None:
        _idx_bei_client = IDXBEIClient()
    return _idx_bei_client


def clear_idx_bei_cache():
    """Clear all cached data"""
    _cache.clear()
    print("[IDX-BEI] Cache cleared")


# ==================== TESTING ====================

async def test_idx_bei():
    """Test the IDX-BEI client"""
    client = get_idx_bei_client()
    
    print("\n=== Testing IDX-BEI Client ===\n")
    
    # Test broker summary
    print("1. Testing Broker Summary for BBCA...")
    broker_data = await client.get_broker_summary("BBCA")
    if broker_data:
        results = broker_data.get("data", [])
        print(f"   Got {len(results)} broker entries")
        if results:
            print(f"   Sample: {results[0]}")
    else:
        print("   Failed to get broker summary")
    
    # Test all brokers
    print("\n2. Testing Broker Search (all brokers)...")
    brokers = await client.get_broker_search()
    if brokers:
        broker_list = brokers.get("data", [])
        print(f"   Got {len(broker_list)} brokers")
        if broker_list:
            print(f"   First broker: {broker_list[0]}")
    else:
        print("   Failed to get broker list")
    
    # Test all companies
    print("\n3. Testing Company List (all emitens)...")
    companies = await client.get_all_companies()
    if companies:
        company_list = companies.get("data", [])
        print(f"   Got {len(company_list)} companies")
        if company_list:
            print(f"   First company: {company_list[0].get('KodeEmiten')}")
    else:
        print("   Failed to get company list")
    
    await client.close()
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_idx_bei())
