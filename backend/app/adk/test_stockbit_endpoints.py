"""
Stockbit API Endpoint Explorer

This script systematically tests various Stockbit API endpoints
to discover what data is available for OrderFlow, OrderBook, and Running Trade.

Usage:
    python test_stockbit_endpoints.py
"""

import asyncio
import httpx
import os
import json
from dotenv import load_dotenv
from pathlib import Path

# Load token from .env
env_path = Path(__file__).parent.parent.parent / ".env"
print(f"Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("STOCKBIT_AUTH_TOKEN", "").strip().strip('"')
if TOKEN and not TOKEN.startswith("Bearer "):
    TOKEN = f"Bearer {TOKEN}"

BASE_URL = "https://exodus.stockbit.com"
SYMBOL = "BBCA"  # Test symbol

HEADERS = {
    "Authorization": TOKEN,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# List of endpoints to explore
ENDPOINTS_TO_TEST = [
    # Running Trade / Tick Data
    f"/running-trade/{SYMBOL}",
    f"/running-trade/chart/{SYMBOL}",
    f"/runningtrade/{SYMBOL}",
    f"/trade/{SYMBOL}",
    f"/trades/{SYMBOL}",
    
    # Order Book / Market Depth
    f"/orderbook/{SYMBOL}",
    f"/order-book/{SYMBOL}",
    f"/depth/{SYMBOL}",
    f"/market-depth/{SYMBOL}",
    f"/bid-ask/{SYMBOL}",
    
    # Price / Chart Data
    f"/chart/{SYMBOL}",
    f"/tradingview/history?symbol={SYMBOL}&resolution=1&from=1700000000&to=1705000000",
    f"/price/{SYMBOL}",
    f"/quote/{SYMBOL}",
    f"/stock/{SYMBOL}",
    
    # Broker Activity
    f"/broker/SQ/running-trade/{SYMBOL}",
    f"/broker-activity/{SYMBOL}",
    
    # Market Detectors (already working)
    f"/marketdetectors/{SYMBOL}",
    
    # Intraday
    f"/intraday/{SYMBOL}",
    f"/tick/{SYMBOL}",
]


async def test_endpoint(client: httpx.AsyncClient, endpoint: str) -> dict:
    """Test a single endpoint and return result"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        response = await client.get(url, headers=HEADERS, timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            # Check if response has meaningful data
            has_data = bool(data.get("data")) if isinstance(data, dict) else bool(data)
            return {
                "endpoint": endpoint,
                "status": "✅ SUCCESS",
                "has_data": has_data,
                "keys": list(data.get("data", {}).keys()) if isinstance(data, dict) and data.get("data") else list(data.keys()) if isinstance(data, dict) else "array",
                "sample": str(data)[:200] + "..." if len(str(data)) > 200 else str(data)
            }
        elif response.status_code == 401:
            return {"endpoint": endpoint, "status": "🔒 UNAUTHORIZED", "has_data": False}
        elif response.status_code == 404:
            return {"endpoint": endpoint, "status": "❌ NOT FOUND", "has_data": False}
        else:
            return {"endpoint": endpoint, "status": f"⚠️ HTTP {response.status_code}", "has_data": False}
            
    except httpx.TimeoutException:
        return {"endpoint": endpoint, "status": "⏱️ TIMEOUT", "has_data": False}
    except Exception as e:
        return {"endpoint": endpoint, "status": f"💥 ERROR: {e}", "has_data": False}


async def main():
    print("=" * 60)
    print("🔍 STOCKBIT API ENDPOINT EXPLORER")
    print("=" * 60)
    print(f"Symbol: {SYMBOL}")
    print(f"Token: {TOKEN[:30]}..." if TOKEN else "❌ NO TOKEN")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        results = []
        
        for endpoint in ENDPOINTS_TO_TEST:
            result = await test_endpoint(client, endpoint)
            results.append(result)
            
            # Print result immediately
            if result["status"].startswith("✅"):
                print(f"\n{result['status']} {endpoint}")
                print(f"   Keys: {result['keys']}")
                print(f"   Sample: {result['sample'][:100]}...")
            else:
                print(f"{result['status']} {endpoint}")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 SUMMARY: Working Endpoints")
        print("=" * 60)
        
        working = [r for r in results if r["status"].startswith("✅")]
        for r in working:
            print(f"  - {r['endpoint']}")
            print(f"    Keys: {r['keys']}")
        
        if not working:
            print("  No working endpoints found beyond /marketdetectors")


if __name__ == "__main__":
    asyncio.run(main())
