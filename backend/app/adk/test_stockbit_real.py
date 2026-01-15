"""
Stockbit API REAL Endpoints Test
Based on actual network traffic capture from stockbit.com

Key Discoveries:
- OrderBook: /company-price-feed/v2/orderbook/companies/{symbol}
- Running Trade: /order-trade/running-trade?symbols[]={symbol}
- Trade Book Chart: /order-trade/trade-book/chart?symbol={symbol}
- Running Trade Chart: /order-trade/running-trade/chart/{symbol}
- Foreign/Domestic: /findata-view/foreign-domestic/v1/chart-data/{symbol}
- Historical: /company-price-feed/historical/summary/{symbol}
- Broker List: /findata-view/marketdetectors/brokers
"""

import asyncio
import httpx
import os
import json
from dotenv import load_dotenv
from pathlib import Path

# Load token
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("STOCKBIT_AUTH_TOKEN", "").strip().strip('"')
BASE_URL = "https://exodus.stockbit.com"
SYMBOL = "BREN"  # Use BREN as test (from network capture)

HEADERS = {
    "Authorization": TOKEN,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# REAL endpoints from network traffic
REAL_ENDPOINTS = [
    # ===== ORDER BOOK =====
    {
        "name": "OrderBook V2",
        "path": f"/company-price-feed/v2/orderbook/companies/{SYMBOL}",
        "params": {}
    },
    {
        "name": "OrderBook V2 (Full Price Tick)",
        "path": f"/company-price-feed/v2/orderbook/companies/{SYMBOL}",
        "params": {"with_full_price_tick": "false"}
    },
    
    # ===== RUNNING TRADE =====
    {
        "name": "Running Trade",
        "path": "/order-trade/running-trade",
        "params": {"sort": "DESC", "limit": "50", "order_by": "RUNNING_TRADE_ORDER_BY_TIME", "symbols[]": SYMBOL}
    },
    {
        "name": "Running Trade Chart (1 Day)",
        "path": f"/order-trade/running-trade/chart/{SYMBOL}",
        "params": {"period": "RT_PERIOD_LAST_1_DAY"}
    },
    {
        "name": "Running Trade Chart (1 Month)",
        "path": f"/order-trade/running-trade/chart/{SYMBOL}",
        "params": {"period": "RT_PERIOD_LAST_1_MONTH"}
    },
    
    # ===== TRADE BOOK =====
    {
        "name": "Trade Book Chart (1m)",
        "path": "/order-trade/trade-book/chart",
        "params": {"symbol": SYMBOL, "time_interval": "1m"}
    },
    
    # ===== HISTORICAL =====
    {
        "name": "Historical Summary (Daily)",
        "path": f"/company-price-feed/historical/summary/{SYMBOL}",
        "params": {"period": "HS_PERIOD_DAILY", "start_date": "2025-01-13", "end_date": "2026-01-13", "limit": "12", "page": "1"}
    },
    
    # ===== FOREIGN/DOMESTIC FLOW =====
    {
        "name": "Foreign Domestic Flow",
        "path": f"/findata-view/foreign-domestic/v1/chart-data/{SYMBOL}",
        "params": {"market_type": "MARKET_TYPE_REGULAR", "period": "PERIOD_RANGE_1D"}
    },
    
    # ===== BROKER LIST =====
    {
        "name": "Broker List",
        "path": "/findata-view/marketdetectors/brokers",
        "params": {"page": "1", "limit": "150", "group": "GROUP_UNSPECIFIED"}
    },
    
    # ===== EMITEN INFO =====
    {
        "name": "Emiten Info",
        "path": f"/emitten/{SYMBOL}/info",
        "params": {}
    },
    {
        "name": "Emiten Contact",
        "path": f"/emitten/{SYMBOL}/contact",
        "params": {}
    },
    
    # ===== CHARTS =====
    {
        "name": "Daily Chart",
        "path": f"/charts/{SYMBOL}/daily",
        "params": {"timeframe": "today"}
    },
    
    # ===== MARKET DETECTORS (Already Working) =====
    {
        "name": "Market Detectors (Bandarmology)",
        "path": f"/marketdetectors/{SYMBOL}",
        "params": {"transaction_type": "TRANSACTION_TYPE_NET", "market_board": "MARKET_BOARD_REGULER", "investor_type": "INVESTOR_TYPE_ALL", "limit": "25"}
    },
    
    # ===== RESEARCH/RESEARCH =====
    {
        "name": "Research Indicator",
        "path": f"/research/indicator/new",
        "params": {"symbol": SYMBOL}
    },
]


async def test_endpoint(client: httpx.AsyncClient, endpoint: dict) -> dict:
    """Test a single endpoint"""
    url = f"{BASE_URL}{endpoint['path']}"
    
    try:
        response = await client.get(url, headers=HEADERS, params=endpoint['params'], timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            # Extract key info
            data_preview = str(data)[:300] + "..." if len(str(data)) > 300 else str(data)
            
            return {
                "name": endpoint['name'],
                "status": "✅ SUCCESS",
                "path": endpoint['path'],
                "data_keys": list(data.get("data", data).keys()) if isinstance(data.get("data", data), dict) else "list/array",
                "preview": data_preview
            }
        elif response.status_code == 401:
            return {"name": endpoint['name'], "status": "🔒 UNAUTHORIZED", "path": endpoint['path']}
        elif response.status_code == 404:
            return {"name": endpoint['name'], "status": "❌ NOT FOUND", "path": endpoint['path']}
        else:
            return {"name": endpoint['name'], "status": f"⚠️ HTTP {response.status_code}", "path": endpoint['path'], "body": response.text[:100]}
            
    except Exception as e:
        return {"name": endpoint['name'], "status": f"💥 ERROR: {e}", "path": endpoint['path']}


async def main():
    print("=" * 80)
    print("🔍 STOCKBIT REAL API ENDPOINTS TEST")
    print("=" * 80)
    print(f"Testing {len(REAL_ENDPOINTS)} endpoints for symbol: {SYMBOL}")
    print("=" * 80)
    
    async with httpx.AsyncClient() as client:
        results = []
        
        for endpoint in REAL_ENDPOINTS:
            result = await test_endpoint(client, endpoint)
            results.append(result)
            
            # Print result
            print(f"\n{result['status']} {result['name']}")
            print(f"   Path: {result['path']}")
            if result['status'].startswith("✅"):
                print(f"   Keys: {result.get('data_keys', 'N/A')}")
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY: Working Endpoints for Integration")
        print("=" * 80)
        
        working = [r for r in results if r["status"].startswith("✅")]
        for r in working:
            print(f"  ✅ {r['name']}")
            print(f"     {r['path']}")
            print(f"     Keys: {r.get('data_keys', 'N/A')}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
