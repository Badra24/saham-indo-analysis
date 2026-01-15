
import requests
import os
from dotenv import load_dotenv

# Load env manually or assume it's set
load_dotenv("backend/.env")

TOKEN = os.getenv("STOCKBIT_AUTH_TOKEN")
if not TOKEN:
    print("Error: STOCKBIT_AUTH_TOKEN not found in environment")
    exit(1)

# Ensure 'Bearer ' prefix is present
if not TOKEN.startswith("Bearer "):
    TOKEN = f"Bearer {TOKEN}"

HEADERS = {
    "Authorization": TOKEN,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Origin": "https://stockbit.com",
    "Referer": "https://stockbit.com/",
    "sec-ch-ua": '"Opera GX";v="125", "Not?A_Brand";v="8", "Chromium";v="141"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"'
}

# Testing User Provided "Holy Grail" Endpoint: Market Detectors
# https://exodus.stockbit.com/marketdetectors/BREN?transaction_type=TRANSACTION_TYPE_NET&market_board=MARKET_BOARD_REGULER&investor_type=INVESTOR_TYPE_ALL&limit=25

print("\nTesting Market Detectors Endpoint (The Holy Grail)...")
symbol = "BREN"
base_url = f"https://exodus.stockbit.com/marketdetectors/{symbol}"
params_str = "transaction_type=TRANSACTION_TYPE_NET&market_board=MARKET_BOARD_REGULER&investor_type=INVESTOR_TYPE_ALL&limit=25"
FULL_URL = f"{base_url}?{params_str}"

print(f"Requesting: {FULL_URL}")

try:
    response = requests.get(FULL_URL, headers=HEADERS, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("Success! Data preview:")
        
        # Check for bandar_detector
        if 'data' in data and 'bandar_detector' in data['data']:
            bd = data['data']['bandar_detector']
            print("\n[Bandar Detector Found!]")
            print(f"Acum/Dist Status (Avg5): {bd.get('avg5', {}).get('accdist')}")
            print(f"Top 1 Status: {bd.get('top1', {}).get('accdist')}")
            print(f"Top 1 Amount: {bd.get('top1', {}).get('amount')}")
        
        # Check for broker_summary
        if 'data' in data and 'broker_summary' in data['data']:
            bs = data['data']['broker_summary']
            buyers = bs.get('brokers_buy', [])
            sellers = bs.get('brokers_sell', [])
            print(f"\n[Broker Summary Found!]")
            if buyers:
                print(f"Top Buyer: {buyers[0].get('netbs_broker_code')} (Val: {buyers[0].get('bval')})")
            if sellers:
                print(f"Top Seller: {sellers[0].get('netbs_broker_code')} (Val: {sellers[0].get('sval')})")
            
    else:
        print("Failed!")
        print(response.text)

except Exception as e:
    print(f"Exception: {e}")
