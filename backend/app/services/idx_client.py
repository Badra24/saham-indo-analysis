
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class IDXClient:
    """
    Client for interacting with the local IDX-BEI Scraper Microservice.
    Running on http://localhost:3000
    """
    
    BASE_URL = "http://localhost:3000/api"
    
    def __init__(self, base_url: str = None):
        if base_url:
            self.BASE_URL = base_url
            
    async def get_broker_summary(self, date: str = "") -> Optional[Dict[str, Any]]:
        """
        Get Broker Summary from IDX Scraper.
        
        Args:
            date: YYYYMMDD string (optional)
        """
        url = f"{self.BASE_URL}/broker-summary"
        params = {}
        if date:
            params['date'] = date
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=60.0) # Scraper is slow
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"IDX Scraper Error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to connect to IDX Scraper: {e}")
            return None

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.BASE_URL}/health", timeout=5.0)
                return response.status_code == 200 and response.json().get('status') == 'ok'
        except:
            return False

# Global instance
idx_client = IDXClient()
