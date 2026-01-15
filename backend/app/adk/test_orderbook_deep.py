"""
Test specific Stockbit endpoints with various parameter combinations
"""

import asyncio
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

# Load token
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("STOCKBIT_AUTH_TOKEN", "").strip().strip('"')
BASE_URL = "https://exodus.stockbit.com"

HEADERS = {
    "Authorization": TOKEN,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


async def test_orderbook_variations():
    """Test orderbook endpoint with various parameters"""
    variations = [
        # Different path structures
        ("/orderbook/BBCA", {}),
        ("/orderbook?symbol=BBCA", {}),
        ("/orderbook", {"symbol": "BBCA"}),
        ("/orderbook/BBCA", {"market_board": "MARKET_BOARD_REGULER"}),
        
        # Try stock details endpoints
        ("/stock/BBCA/orderbook", {}),
        ("/stocks/BBCA/orderbook", {}),
        ("/stockdetail/BBCA", {}),
        ("/stock-detail/BBCA", {}),
        
        # Try with .JK suffix
        ("/orderbook/BBCA.JK", {}),
        
        # Running trade variations (webSocket-based usually)
        ("/runningtrade", {"symbol": "BBCA"}),
        ("/running-trade", {"symbol": "BBCA"}),
        ("/stream/BBCA", {}),
        
        # General stock info
        ("/v1/stock/BBCA", {}),
        ("/api/stock/BBCA", {}),
        ("/company/BBCA", {}),
        ("/profile/BBCA", {}),
        
        # Try different base paths  
        ("/api/v1/orderbook/BBCA", {}),
        ("/api/v2/orderbook/BBCA", {}),
    ]
    
    async with httpx.AsyncClient() as client:
        for path, params in variations:
            url = f"{BASE_URL}{path}"
            try:
                resp = await client.get(url, headers=HEADERS, params=params, timeout=10.0)
                if resp.status_code == 200:
                    print(f"✅ {path} (params={params})")
                    data = resp.json()
                    print(f"   Response: {str(data)[:150]}...")
                elif resp.status_code == 400:
                    print(f"⚠️ HTTP 400 {path} - Needs params?")
                    # Try to get error message
                    try:
                        err = resp.json()
                        print(f"   Error: {err}")
                    except:
                        print(f"   Body: {resp.text[:100]}")
                else:
                    print(f"❌ HTTP {resp.status_code} {path}")
            except Exception as e:
                print(f"💥 {path}: {e}")


async def explore_websocket():
    """Check if there's a WebSocket endpoint for real-time data"""
    # Stockbit likely uses WebSocket for running trade
    # We can't test WS with httpx, but we can find the endpoint
    print("\n--- WebSocket Exploration ---")
    print("Stockbit likely uses WebSocket for real-time running trade.")
    print("Common WebSocket patterns:")
    print("  wss://exodus.stockbit.com/ws")
    print("  wss://stream.stockbit.com/")
    print("  wss://realtime.stockbit.com/")
    print("\nNote: WebSocket requires a different client (websockets library)")


if __name__ == "__main__":
    print("=" * 60)
    print("🔬 STOCKBIT ORDERBOOK DEEP DIVE")
    print("=" * 60)
    asyncio.run(test_orderbook_variations())
    asyncio.run(explore_websocket())
