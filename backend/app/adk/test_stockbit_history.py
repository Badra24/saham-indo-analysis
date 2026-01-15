
import asyncio
import os
import httpx
from dotenv import load_dotenv

# Load Env
load_dotenv("backend/.env")

TOKEN = os.getenv("STOCKBIT_AUTH_TOKEN")
if not TOKEN:
    print("Error: STOCKBIT_AUTH_TOKEN not found")
    exit(1)

if not TOKEN.startswith("Bearer "):
    TOKEN = f"Bearer {TOKEN}"

HEADERS = {
    "Authorization": TOKEN,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Origin": "https://stockbit.com",
    "Referer": "https://stockbit.com/"
}

async def test_history():
    symbol = "BBCA"
    
    # Try 1: Standard date param with YYYY-MM-DD
    # Try 2: date param with YYYYMMDD
    # Try 3: startDate / endDate
    
    variations = [
         {"date": "2024-01-10"},
         {"date": "20240110"},
         {"startDate": "2024-01-10", "endDate": "2024-01-10"},
         {"from": "2024-01-10", "to": "2024-01-10"},
         {"date": "2025-01-01"} # A fast forwarded date? Or just a different past date
    ]
    
    url = f"https://exodus.stockbit.com/marketdetectors/{symbol}"
    
    for params in variations:
        p_merged = {
            "transaction_type": "TRANSACTION_TYPE_NET",
            "market_board": "MARKET_BOARD_REGULER",
            "investor_type": "INVESTOR_TYPE_ALL",
            "limit": 1
        }
        p_merged.update(params)
        
        print(f"\nTesting params: {params}")
        
        async with httpx.AsyncClient(headers=HEADERS) as client:
            resp = await client.get(url, params=p_merged)
            if resp.status_code == 200:
                data = resp.json()
                bs = data.get('data', {}).get('broker_summary', {})
                buyers = bs.get('brokers_buy', [])
                if buyers:
                    # Check first buyer's date
                    date_in_resp = buyers[0].get('netbs_date')
                    print(f"Response Date: {date_in_resp}")
                else:
                     print("No buyer data")
            else:
                print(f"Status: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_history())
