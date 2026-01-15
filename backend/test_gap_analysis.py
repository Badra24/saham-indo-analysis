

import asyncio
import json
from app.services.wyckoff_detector import get_wyckoff_detector
from app.services.bandarmology import bandarmology_engine
from app.services.alert_engine import AlertEngine

def test_gap_analysis():
    print("Testing Gap Analysis Features...")
    
    # 1. Test Wyckoff Detector
    print("- Testing Wyckoff Detector...")
    detector = get_wyckoff_detector()
    
    # Simple data for syntax check mostly
    dummy_prices = [{'close': 1000, 'low': 950, 'high': 1050, 'volume': 1000} for _ in range(20)]
    dummy_broker = {'top_buyers': [{'code': 'KZ', 'value': 100}], 'top_sellers': [{'code': 'YP', 'value': 50}]}
    
    result = detector.detect(dummy_prices, dummy_broker)
    print(f"  Result: {result.pattern}")

    # 2. Test AQS
    print("- Testing AQS...")
    aqs = bandarmology_engine.calculate_aqs([], [1000.0]*20, dummy_broker)
    print(f"  AQS Score: {aqs['aqs']} (Grade {aqs['grade']})")

    # 3. Test Churn
    print("- Testing Churn Ratio...")
    churn = bandarmology_engine.calculate_churn_ratio(1000, 100) # 10x churn
    print(f"  Churn: {churn['churn_ratio']}x ({churn['level']})")
    
    
    print("\n3. Testing HHI Calculation...")
    # Create distinct sample data for HHI/VWAP
    sample_broker_data = {
        'top_buyers': [
            {'code': 'KZ', 'value': 100000000, 'volume': 10000},  # Big accumulator
            {'code': 'ZP', 'value': 45000000, 'volume': 5000},
            {'code': 'CC', 'value': 5000000, 'volume': 500}
        ], 
        'top_sellers': []
    }
    
    hhi_result = bandarmology_engine.calculate_hhi(sample_broker_data)
    print(f"HHI Result: {json.dumps(hhi_result, indent=2)}")

    print("\n4. Testing Bandar VWAP...")
    vwap_result = bandarmology_engine.calculate_bandar_vwap(sample_broker_data)
    print(f"Bandar VWAP Result: {json.dumps(vwap_result, indent=2)}")

    print("\n✅ Verification Complete!")


if __name__ == "__main__":
    test_gap_analysis()

