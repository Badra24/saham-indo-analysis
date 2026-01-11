"""
IDX Browser Client - Real-time data from IDX using browser automation

Bypasses IDX anti-bot protection by using a real browser (Playwright).
This is slower than direct API but works reliably.

Features:
- Browser automation with Chromium (headless)
- Intercepts XHR responses for JSON data
- Caching to minimize browser usage
- Rate limiting to avoid detection
"""

import asyncio
import json
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[IDX-BROWSER] Warning: Playwright not installed. Run: pip install playwright && playwright install chromium")


# ==================== CACHE ====================

class BrowserCache:
    """File-based cache for browser-fetched data"""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / "data" / "idx_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key"""
        safe_key = key.replace("/", "_").replace("?", "_").replace("&", "_")
        return self.cache_dir / f"{safe_key}.json"
    
    def get(self, key: str, ttl_seconds: int = 300) -> Optional[Dict]:
        """Get cached data if not expired"""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            
            cached_at = cached.get("_cached_at", 0)
            if time.time() - cached_at > ttl_seconds:
                cache_path.unlink()  # Delete expired
                return None
            
            return cached.get("data")
        except Exception as e:
            print(f"[IDX-BROWSER] Cache read error: {e}")
            return None
    
    def set(self, key: str, data: Any):
        """Save data to cache"""
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'w') as f:
                json.dump({
                    "_cached_at": time.time(),
                    "data": data
                }, f, indent=2)
        except Exception as e:
            print(f"[IDX-BROWSER] Cache write error: {e}")


_cache = BrowserCache()


# ==================== IDX BROWSER CLIENT ====================

class IDXBrowserClient:
    """
    Fetch data from IDX website using browser automation.
    Bypasses anti-bot protection by using real browser.
    
    Page Structure (discovered):
    - /broker-summary/ -> Searches by BROKER code (e.g., YP, AK)
    - /stock-summary/ -> Searches by STOCK code (e.g., BBCA, TLKM)
    
    API Endpoints intercepted:
    - GetBrokerSummary -> returns broker activity for a stock
    - GetStockSummary -> returns stock trading summary
    """
    
    IDX_BASE_URL = "https://www.idx.co.id"
    
    # Page URLs
    BROKER_SUMMARY_PAGE = "/en/market-data/trading-summary/broker-summary/"
    STOCK_SUMMARY_PAGE = "/en/market-data/trading-summary/stock-summary/"
    
    # Selectors (discovered from browser exploration)
    SEARCH_INPUT_SELECTOR = "#FilterSearch"  # Main search input in tables
    BROKER_SEARCH_SELECTOR = "input[placeholder*='Search Broker']"  # Broker search
    
    # Cache TTL settings
    BROKER_SUMMARY_TTL = 300  # 5 minutes
    STOCK_SUMMARY_TTL = 300  # 5 minutes
    COMPANY_LIST_TTL = 3600  # 1 hour
    
    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0
        self._min_request_interval = 2.0  # seconds between requests
    
    async def _get_browser(self) -> Browser:
        """Get or create browser instance"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed")
        
        if self._browser is None or not self._browser.is_connected():
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            print("[IDX-BROWSER] Browser launched")
        
        return self._browser
    
    async def _rate_limit(self):
        """Ensure minimum time between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    async def _fetch_with_xhr_intercept(
        self, 
        page_url: str,
        api_contains: str,
        search_value: str = None,
        search_selector: str = None,
        cache_key: str = None,
        cache_ttl: int = 300
    ) -> Optional[Dict]:
        """
        Generic method to fetch data by navigating to a page and intercepting XHR.
        
        Args:
            page_url: Full URL to navigate to
            api_contains: String to match in XHR URL (e.g., 'GetBrokerSummary')
            search_value: Value to type in search input (optional)
            search_selector: CSS selector for search input
            cache_key: Key for caching
            cache_ttl: Cache time-to-live in seconds
        """
        # Check cache first
        if cache_key:
            cached = _cache.get(cache_key, cache_ttl)
            if cached:
                print(f"[IDX-BROWSER] Cache hit: {cache_key}")
                return cached
        
        async with self._lock:
            await self._rate_limit()
            
            try:
                browser = await self._get_browser()
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # Storage for intercepted API responses
                api_responses = []
                
                async def handle_response(response):
                    """Intercept XHR responses for API data"""
                    if api_contains in response.url:
                        try:
                            data = await response.json()
                            if data:
                                api_responses.append(data)
                                print(f"[IDX-BROWSER] Intercepted: {api_contains}")
                        except Exception as e:
                            pass
                
                page.on("response", handle_response)
                
                # OPTIMIZATION (Based on "Best Practices" Research): 
                # Block heavy resources (images, fonts, css) to speed up loading
                async def block_media(route):
                    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                        await route.abort()
                    else:
                        await route.continue_()
                
                await page.route("**/*", block_media)
                
                # Navigate to page
                print(f"[IDX-BROWSER] Navigating to: {page_url}")
                await page.goto(page_url, wait_until='networkidle', timeout=60000)
                
                # Wait for initial load
                await page.wait_for_timeout(3000)
                
                # If search value provided, enter it
                if search_value and search_selector:
                    try:
                        # Wait for search input to be visible
                        await page.wait_for_selector(search_selector, timeout=10000)
                        search_input = page.locator(search_selector).first
                        
                        # Clear and type
                        await search_input.clear()
                        
                        # Clear previous responses captured during initial load
                        api_responses.clear()
                        
                        await search_input.fill(search_value)
                        await page.wait_for_timeout(500)
                        await search_input.press('Enter')
                        
                        print(f"[IDX-BROWSER] Searched for: {search_value}")
                        
                        # Wait for results - wait up to 10s for new data
                        for _ in range(20):
                            if api_responses:
                                break
                            await page.wait_for_timeout(500)
                        
                        if not api_responses:
                            # If no new XHR, maybe it was fast or client-side filter
                            # But usually GetStockSummary is re-fetched.
                            await page.wait_for_timeout(2000)
                        
                    except Exception as e:
                        print(f"[IDX-BROWSER] Search error: {e}")
                
                # Close context
                await context.close()
                
                # Return first matching response
                if api_responses:
                    result = api_responses[-1]  # Latest response
                    if cache_key:
                        _cache.set(cache_key, result)
                    return result
                
                print(f"[IDX-BROWSER] No XHR intercepted for {api_contains}")
                return None
                    
            except Exception as e:
                print(f"[IDX-BROWSER] Error: {e}")
                return None
    
    # ==================== BROKER SUMMARY ====================
    
    async def get_broker_summary(
        self, 
        symbol: str, 
        date_str: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get broker buy/sell activity for a specific stock.
        
        Note: The broker summary page on IDX requires searching by BROKER code, not stock.
        For stock-specific broker data, we may need to use a different approach
        or the /stock-summary/ page with additional filtering.
        
        Args:
            symbol: Stock symbol (e.g., 'BBCA')
            date_str: Date in YYYY-MM-DD format
        
        Returns:
            Broker summary data with buy/sell breakdown
        """
        symbol = symbol.upper().replace(".JK", "")
        
        if not date_str:
            date_str = date.today().strftime("%Y-%m-%d")
        
        cache_key = f"broker_summary_{symbol}_{date_str}"
        
        # Use broker summary page with stock filter
        # Note: IDX broker summary page actually needs broker code input
        # We'll intercept the API response from the page
        url = f"{self.IDX_BASE_URL}{self.BROKER_SUMMARY_PAGE}"
        
        result = await self._fetch_with_xhr_intercept(
            page_url=url,
            api_contains="GetBrokerSummary",
            # Don't search - just get page data and look for the API call
            cache_key=cache_key,
            cache_ttl=self.BROKER_SUMMARY_TTL
        )
        
        return result
    
    async def get_stock_summary(
        self, 
        symbol: str = None,
        date_str: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get stock trading summary (price, volume, etc.).
        
        Args:
            symbol: Stock symbol to filter (e.g., 'BBCA'), or None for all
            date_str: Date in YYYY-MM-DD format
        """
        cache_key = f"stock_summary_{symbol or 'all'}_{date_str or 'today'}"
        
        url = f"{self.IDX_BASE_URL}{self.STOCK_SUMMARY_PAGE}"
        
        result = await self._fetch_with_xhr_intercept(
            page_url=url,
            api_contains="GetStockSummary",
            search_value=symbol,
            search_selector=self.SEARCH_INPUT_SELECTOR,
            cache_key=cache_key,
            cache_ttl=self.STOCK_SUMMARY_TTL
        )
        
        return result
    
    async def get_all_brokers(self) -> Optional[List[Dict]]:
        """Get list of all registered brokers."""
        cache_key = "all_brokers"
        
        url = f"{self.IDX_BASE_URL}/en/members-and-participants/exchange-members/"
        
        result = await self._fetch_with_xhr_intercept(
            page_url=url,
            api_contains="GetBrokerSearch",
            cache_key=cache_key,
            cache_ttl=self.COMPANY_LIST_TTL
        )
        
        if result and "data" in result:
            return result.get("data", [])
        return None
    
    async def close(self):
        """Close browser and cleanup"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        print("[IDX-BROWSER] Browser closed")


# ==================== SINGLETON ====================

_idx_browser_client: Optional[IDXBrowserClient] = None


def get_idx_browser_client() -> IDXBrowserClient:
    """Get or create IDX browser client instance"""
    global _idx_browser_client
    if _idx_browser_client is None:
        _idx_browser_client = IDXBrowserClient()
    return _idx_browser_client


# ==================== TESTING ====================

async def test_idx_browser():
    """Test the browser-based IDX client"""
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright not installed. Please run:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return
    
    client = get_idx_browser_client()
    
    print("\n=== Testing IDX Browser Client ===\n")
    
    print("1. Testing Stock Summary for BBCA...")
    result = await client.get_stock_summary("BBCA")
    if result:
        data = result.get("data", [])
        print(f"   Got {len(data)} entries")
        if data:
            print(f"   Sample: {data[0] if isinstance(data[0], dict) else data}")
    else:
        print("   No data")
    
    print("\n2. Testing Broker Summary...")
    result = await client.get_broker_summary("BBCA")
    if result:
        data = result.get("data", [])
        print(f"   Got {len(data)} broker entries")
    else:
        print("   No data")
    
    await client.close()
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_idx_browser())

