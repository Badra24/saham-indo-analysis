"""
API Usage Tracker for GoAPI Rate Limits

Tracks daily and monthly API usage to prevent exceeding:
- 30 hits/day
- 500 hits/month

Stores usage data in a JSON file and resets automatically.
"""

import json
import os
from datetime import datetime, date
from typing import Dict, Optional
from pathlib import Path

# Storage file path
USAGE_FILE = Path(__file__).parent.parent / "data" / "goapi_usage.json"


def _ensure_data_dir():
    """Ensure data directory exists"""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_usage() -> Dict:
    """Load usage data from file"""
    _ensure_data_dir()
    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "daily_count": 0,
        "monthly_count": 0,
        "last_daily_reset": str(date.today()),
        "last_monthly_reset": str(date.today().replace(day=1)),
        "cached_tickers": {}  # ticker -> last_fetch_timestamp
    }


def _save_usage(data: Dict):
    """Save usage data to file"""
    _ensure_data_dir()
    with open(USAGE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _check_and_reset(data: Dict) -> Dict:
    """Check if counters need reset based on date"""
    today = date.today()
    today_str = str(today)
    month_start_str = str(today.replace(day=1))
    
    # Reset daily counter
    if data.get("last_daily_reset") != today_str:
        data["daily_count"] = 0
        data["last_daily_reset"] = today_str
    
    # Reset monthly counter
    if data.get("last_monthly_reset") != month_start_str:
        data["monthly_count"] = 0
        data["last_monthly_reset"] = month_start_str
    
    return data


def can_make_api_call() -> bool:
    """Check if we can make another API call without exceeding limits"""
    data = _check_and_reset(_load_usage())
    
    # Check limits
    daily_ok = data["daily_count"] < 30
    monthly_ok = data["monthly_count"] < 500
    
    return daily_ok and monthly_ok


def record_api_call(ticker: str):
    """Record an API call for a ticker"""
    data = _check_and_reset(_load_usage())
    
    data["daily_count"] += 1
    data["monthly_count"] += 1
    data["cached_tickers"][ticker] = datetime.now().isoformat()
    
    _save_usage(data)


def is_ticker_cached(ticker: str, cache_hours: int = 24) -> bool:
    """
    Check if ticker data is still in cache (not expired).
    
    Args:
        ticker: Stock ticker symbol
        cache_hours: Cache validity in hours (default 24)
    
    Returns:
        True if cached and not expired, False otherwise
    """
    data = _check_and_reset(_load_usage())
    
    if ticker not in data.get("cached_tickers", {}):
        return False
    
    try:
        last_fetch = datetime.fromisoformat(data["cached_tickers"][ticker])
        hours_elapsed = (datetime.now() - last_fetch).total_seconds() / 3600
        return hours_elapsed < cache_hours
    except (ValueError, KeyError):
        return False


def get_usage_status() -> Dict:
    """Get current usage status"""
    data = _check_and_reset(_load_usage())
    
    return {
        "daily_used": data["daily_count"],
        "daily_limit": 30,
        "daily_remaining": 30 - data["daily_count"],
        "monthly_used": data["monthly_count"],
        "monthly_limit": 500,
        "monthly_remaining": 500 - data["monthly_count"],
        "warning": data["daily_count"] >= 25 or data["monthly_count"] >= 450,
        "cached_tickers_count": len(data.get("cached_tickers", {}))
    }


def clear_expired_cache():
    """Remove expired cache entries to keep file small"""
    data = _load_usage()
    now = datetime.now()
    
    valid_cache = {}
    for ticker, timestamp_str in data.get("cached_tickers", {}).items():
        try:
            last_fetch = datetime.fromisoformat(timestamp_str)
            if (now - last_fetch).total_seconds() / 3600 < 24:
                valid_cache[ticker] = timestamp_str
        except ValueError:
            pass
    
    data["cached_tickers"] = valid_cache
    _save_usage(data)
