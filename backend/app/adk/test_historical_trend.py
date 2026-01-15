"""
Test if Stockbit provides historical bandarmology data (30-day trend).
"""

import asyncio
import httpx
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# Load token
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("STOCKBIT_AUTH_TOKEN", "").strip().strip('"')
BASE_URL = "https://exodus.stockbit.com"
SYMBOL = "BBCA"

HEADERS = {
    "Authorization": TOKEN,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
}


async def test_historical_bandarmology():
    """Test if marketdetectors endpoint accepts historical date ranges"""
    
    async with httpx.AsyncClient() as client:
        # Test 1: Get data for 7 days ago
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        print(f"Testing date range: {seven_days_ago} to {today}")
        
        url = f"{BASE_URL}/marketdetectors/{SYMBOL}"
        params = {
            "transaction_type": "TRANSACTION_TYPE_NET",
            "market_board": "MARKET_BOARD_REGULER",
            "investor_type": "INVESTOR_TYPE_ALL",
            "limit": 25,
            "from": seven_days_ago,
            "to": today
        }
        
        resp = await client.get(url, headers=HEADERS, params=params, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Historical bandarmology works!")
            print(f"   From: {data.get('data', {}).get('from')}")
            print(f"   To: {data.get('data', {}).get('to')}")
            
            bd = data.get('data', {}).get('bandar_detector', {})
            print(f"   Top1 Status: {bd.get('top1', {}).get('accdist')}")
            print(f"   Top1 Amount: {bd.get('top1', {}).get('amount')}")
        else:
            print(f"❌ Failed: {resp.status_code}")
            print(resp.text[:200])
        
        print("\n" + "="*60)
        
        # Test 2: Running Trade Chart (already has period support)
        print("\nTesting Running Trade Chart (1 Month)...")
        url2 = f"{BASE_URL}/order-trade/running-trade/chart/{SYMBOL}"
        params2 = {"period": "RT_PERIOD_LAST_1_MONTH"}
        
        resp2 = await client.get(url2, headers=HEADERS, params=params2, timeout=10.0)
        if resp2.status_code == 200:
            data2 = resp2.json()
            broker_data = data2.get('data', {}).get('broker_chart_data', [])
            print(f"✅ Running Trade Chart (1 Month) works!")
            print(f"   From: {data2.get('data', {}).get('from')}")
            print(f"   To: {data2.get('data', {}).get('to')}")
            print(f"   Broker data points: {len(broker_data)}")
            if broker_data:
                print(f"   Sample: {broker_data[0]}")
        else:
            print(f"❌ Failed: {resp2.status_code}")
        
        print("\n" + "="*60)
        
        # Test 3: Historical Summary (OHLCV with foreign flow)
        print("\nTesting Historical Summary (30 days)...")
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        url3 = f"{BASE_URL}/company-price-feed/historical/summary/{SYMBOL}"
        params3 = {
            "period": "HS_PERIOD_DAILY",
            "start_date": thirty_days_ago,
            "end_date": today,
            "limit": 30,
            "page": 1
        }
        
        resp3 = await client.get(url3, headers=HEADERS, params=params3, timeout=10.0)
        if resp3.status_code == 200:
            data3 = resp3.json()
            results = data3.get('data', {}).get('result', [])
            print(f"✅ Historical Summary works!")
            print(f"   Days returned: {len(results)}")
            if results:
                print(f"   First day: {results[0].get('date')}")
                print(f"   Last day: {results[-1].get('date')}")
                # Check if foreign data is included
                if 'fbuy' in results[0]:
                    print(f"   ✅ Foreign Buy/Sell data available!")
                    print(f"   Sample: fbuy={results[0].get('fbuy')}, fsell={results[0].get('fsell')}")
        else:
            print(f"❌ Failed: {resp3.status_code}")


if __name__ == "__main__":
    asyncio.run(test_historical_bandarmology())
