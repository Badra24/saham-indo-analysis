import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

class BrowserCache:
    """File-based cache for browser-fetched data"""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            # Determine path relative to project root
            # Assuming this file is in backend/app/services/browser_client/
            # We want to go up to backend/data/idx_cache or similar
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            cache_dir = base_dir / "data" / "idx_cache"
            
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
