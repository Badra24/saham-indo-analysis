
import sys
import os

# Ensure app module can be found
sys.path.append(os.getcwd())

from app.services.market_data import MarketDataService

def test_fetch():
    print("Testing MarketDataService...")
    service = MarketDataService()
    try:
        data = service.get_market_data("BBCA")
        if data:
            print(f"Success! Fetched {data.ticker}")
            print(f"Price: {data.price}")
            print(f"Candles: {len(data.historical_prices)}")
            if len(data.historical_prices) > 0:
                print(f"Sample Candle: {data.historical_prices[0]}")
        else:
            print("Failed to fetch data (Returned None)")
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fetch()
