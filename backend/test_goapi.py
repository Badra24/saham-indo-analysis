#!/usr/bin/env python3
"""
Test script for GoAPI integration
Run: cd backend && python test_goapi.py
"""

import sys
import os

# Add backend directory to path for module imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Set environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from app.services.goapi_client import get_goapi_client, test_goapi_connection


def main():
    print("=" * 50)
    print("GoAPI Connection Test")
    print("=" * 50)
    
    # Test connection
    result = test_goapi_connection()
    
    print(f"\nConnection Status: {'✅ Connected' if result['connected'] else '❌ Not Connected'}")
    print(f"Message: {result['message']}")
    print(f"Using Demo Data: {'Yes' if result['using_demo'] else 'No'}")
    
    if result.get('sample_data'):
        print("\nSample Broker Summary Data:")
        data = result['sample_data']
        print(f"  Symbol: {data.get('symbol', 'N/A')}")
        print(f"  Status: {data.get('status', 'N/A')}")
        print(f"  Top Buyers: {data.get('top_buyers', [])}")
        print(f"  Top Sellers: {data.get('top_sellers', [])}")
        print(f"  Dominant Player: {data.get('dominant_player', 'N/A')}")
        print(f"  Net Flow: Rp {data.get('net_flow', 0):,.0f}")
    
    print("\n" + "=" * 50)
    
    # Additional tests
    client = get_goapi_client()
    
    print("\nTesting Stock Price API...")
    price = client.get_stock_price("BBCA")
    if price:
        print(f"  BBCA Price: Rp {price.get('close', 'N/A'):,}")
        print(f"  Change: {price.get('change_pct', 0):.2f}%")
    else:
        print("  Could not fetch price data")
    
    print("\nTesting Historical Data API...")
    hist = client.get_historical("BBCA")
    if hist:
        print(f"  Got {len(hist)} historical data points")
        if hist:
            latest = hist[0]
            print(f"  Latest: {latest.get('date')} - Close: Rp {latest.get('close', 'N/A'):,}")
    else:
        print("  Could not fetch historical data")
    
    print("\n" + "=" * 50)
    print("Test Complete!")


if __name__ == "__main__":
    main()
