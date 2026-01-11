"""
Simple In-Memory Cache for ADK Tools

Provides caching for stable data like market analysis to
reduce API calls and improve response times.

Thread-safe with asyncio for concurrent access.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable, Awaitable, TypeVar
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Individual cache entry with TTL tracking."""
    value: Any
    created_at: datetime
    ttl_seconds: int
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()


class SimpleCache:
    """
    Simple async-safe in-memory cache with TTL support.
    
    Usage:
        cache = SimpleCache()
        
        # Direct set/get
        cache.set("key", data, ttl=300)
        data = cache.get("key")
        
        # Fetch-or-cache pattern
        data = await cache.get_or_fetch(
            "analysis_BBCA",
            fetch_func=lambda: get_full_analysis_data("BBCA"),
            ttl=300
        )
    """
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value from cache if exists and not expired.
        
        Returns dict with value, from_cache flag, and metadata.
        """
        entry = self._cache.get(key)
        
        if entry is None:
            return None
            
        if entry.is_expired:
            # Clean up expired entry
            del self._cache[key]
            return None
        
        return {
            "data": entry.value,
            "from_cache": True,
            "fetched_at": entry.created_at.isoformat(),
            "data_age_seconds": round(entry.age_seconds, 1)
        }
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Data to cache
            ttl: Time-to-live in seconds
        """
        self._cache[key] = CacheEntry(
            value=value,
            created_at=datetime.now(timezone.utc),
            ttl_seconds=ttl
        )
        logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
    
    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable[[], Awaitable[T]],
        ttl: int = 300
    ) -> Dict[str, Any]:
        """
        Get from cache or fetch if missing/expired.
        
        Thread-safe for concurrent access.
        
        Args:
            key: Cache key
            fetch_func: Async function to call if cache miss
            ttl: Time-to-live for new entries
            
        Returns:
            Dict with data, from_cache flag, and metadata
        """
        # Check cache first (without lock for performance)
        cached = self.get(key)
        if cached is not None:
            logger.debug(f"Cache HIT: {key}")
            return cached
        
        # Cache miss - fetch with lock to prevent thundering herd
        async with self._lock:
            # Double-check in case another coroutine fetched while waiting
            cached = self.get(key)
            if cached is not None:
                return cached
            
            # Fetch fresh data
            logger.debug(f"Cache MISS: {key} - fetching...")
            fetched_at = datetime.now(timezone.utc)
            
            try:
                data = await fetch_func()
                self.set(key, data, ttl)
                
                return {
                    "data": data,
                    "from_cache": False,
                    "fetched_at": fetched_at.isoformat(),
                    "data_age_seconds": 0
                }
            except Exception as e:
                logger.error(f"Cache fetch error for {key}: {e}")
                return {
                    "data": {"error": str(e)},
                    "from_cache": False,
                    "fetched_at": fetched_at.isoformat(),
                    "data_age_seconds": 0,
                    "fetch_error": True
                }
    
    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache INVALIDATE: {key}")
            return True
        return False
    
    def clear(self) -> int:
        """Clear all cache entries. Returns count of cleared entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache CLEAR: {count} entries removed")
        return count
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        entries = []
        
        for key, entry in self._cache.items():
            entries.append({
                "key": key,
                "age_seconds": round(entry.age_seconds, 1),
                "ttl_seconds": entry.ttl_seconds,
                "expired": entry.is_expired
            })
        
        return {
            "total_entries": len(self._cache),
            "entries": entries
        }


# Global cache instance
_cache_instance: Optional[SimpleCache] = None


def get_cache() -> SimpleCache:
    """Get the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SimpleCache()
    return _cache_instance
