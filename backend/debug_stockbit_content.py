
import asyncio
import os
import json
from app.services.stockbit_client import stockbit_client

async def debug_stockbit():
    symbol = "BBCA"
    print(f"Fetching RAW {symbol} from Stockbit...")
    
    # We need the token
    token = os.getenv("STOCKBIT_AUTH_TOKEN")
    if not token:
        print("Token missing")
        return
        
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"
        
    headers = {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    }
    
    url = f"https://exodus.stockbit.com/marketdetectors/{symbol}"
    params = {
            "transaction_type": "TRANSACTION_TYPE_NET",
            "market_board": "MARKET_BOARD_REGULER",
            "investor_type": "INVESTOR_TYPE_ALL",
            "limit": 25
    }
    
    import httpx
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url, params=params)
        raw_data = resp.json()
        
        # Print keys of broker_summary to find totals
        bs = raw_data.get('data', {}).get('broker_summary', {})
        print("Broker Summary Keys:", bs.keys())
        
        # Look for values
        print("Looking for totals...")
        for k, v in bs.items():
            if 'val' in k or 'total' in k:
                print(f"{k}: {v}")
                
        # Also check top buyers to confirm values
        print("Top Buyer 1:", bs.get('brokers_buy', [])[0])

if __name__ == "__main__":
    # Setup path
    import sys
    sys.path.append(os.getcwd())
    
    asyncio.run(debug_stockbit())
