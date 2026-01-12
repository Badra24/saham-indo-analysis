import asyncio
import json
import logging
from typing import Optional, Dict, Any, Union

try:
    from playwright.async_api import async_playwright, Browser, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

class IDXBrowser:
    """
    Singleton Browser Manager using Playwright.
    Maintains a persistent browser instance to reduce startup overhead.
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        
    @classmethod
    async def get_instance(cls):
        """Get singleton instance"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    async def _ensure_browser(self):
        """Ensure browser is running"""
        if self._browser is None or not self._browser.is_connected():
            logger.info("[IDX-BROWSER] Launching new browser instance...")
            if self._playwright:
                await self._playwright.stop()
                
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu'
                ]
            )
    
    async def fetch_json(self, url: str, wait_until: str = 'domcontentloaded', timeout: int = 30000) -> Optional[Union[Dict, list]]:
        """
        Fetch JSON data from a URL using the browser.
        This bypasses Cloudflare/Bot detection by using a real browser to hit the API endpoint.
        
        Args:
            url: The API URL to fetch (must return JSON in body)
            wait_until: value for page.goto wait_until
            timeout: timeout in ms
        """
        await self._ensure_browser()
        
        page = await self._browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        try:
            # Optimization: Block resources
            await page.route("**/*", lambda route: route.abort() 
                             if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
                             else route.continue_())
            
            logger.info(f"[IDX-BROWSER] Fetching: {url}")
            response = await page.goto(url, wait_until=wait_until, timeout=timeout)
            
            if not response.ok:
                logger.error(f"[IDX-BROWSER] HTTP Error {response.status} for {url}")
                return None
                
            # Extract JSON from body (pre tag often wraps it in Chrome view-source, but innerText works for raw)
            # For JSON endpoints, innerText of body is usually the JSON string.
            content = await page.evaluate("() => document.body.innerText")
            
            try:
                data = json.loads(content)
                return data
            except json.JSONDecodeError:
                logger.error(f"[IDX-BROWSER] Failed to decode JSON from {url}. Content preview: {content[:100]}")
                return None
                
        except Exception as e:
            logger.error(f"[IDX-BROWSER] Fetch error: {e}")
            return None
        finally:
            await page.close()

    async def close(self):
        """Close browser resources"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
