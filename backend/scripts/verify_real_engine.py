import sys
import os
import pandas as pd
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ml_engine import ml_engine
from app.services.bandarmology import bandarmology_engine
from app.services.indicators import calculate_vpvr
# Mock data for testing
def create_mock_historical_data():
    dates = pd.date_range(end=datetime.now(), periods=100)
    data = {
        'Open': [1000 + i for i in range(100)],
        'High': [1020 + i for i in range(100)],
        'Low': [990 + i for i in range(100)],
        'Close': [1010 + i for i in range(100)],
        'Volume': [10000 * (1 + (i % 5)) for i in range(100)] # Varied volume
    }
    df = pd.DataFrame(data, index=dates)
    return df

def test_ml_engine():
    print("\n--- Testing ML Engine ---")
    df = create_mock_historical_data()
    result = ml_engine.analyze_latest_anomaly(df)
    print(f"Result: {result}")
    assert 'is_anomaly' in result
    assert 'score' in result
    print("✅ ML Engine Test Passed")

def test_vpvr():
    print("\n--- Testing VPVR Calculation ---")
    df = create_mock_historical_data()
    df_vpvr = calculate_vpvr(df, bins=10)
    
    print(f"Columns: {df_vpvr.columns}")
    assert 'VPVR_POC' in df_vpvr.columns
    assert 'VPVR_VAH' in df_vpvr.columns
    assert 'VPVR_VAL' in df_vpvr.columns
    
    poc = df_vpvr['VPVR_POC'].iloc[-1]
    print(f"POC: {poc}")
    assert not pd.isna(poc)
    print("✅ VPVR Test Passed")

def test_bandarmology_real():
    print("\n--- Testing Real Bandarmology (No Dummy) ---")
    
    # Test with Empty/None data (Should return Unavailable, NOT dummy)
    result_empty = bandarmology_engine.analyze_broker_summary(None)
    print(f"Empty Input Result: {result_empty['status']}")
    assert result_empty['status'] == 'DATA_UNAVAILABLE'
    
    # Test with Mock Real Data
    mock_real_data = {
        'top_buyers': [{'code': 'AK', 'value': 100, 'type': 'INSTITUTION'}, {'code': 'ZP', 'value': 50}],
        'top_sellers': [{'code': 'YP', 'value': 20}, {'code': 'PD', 'value': 10}],
        'foreign_net_flow': 50
    }
    result_real = bandarmology_engine.analyze_broker_summary(mock_real_data)
    print(f"Real Input Status: {result_real['status']}")
    print(f"BCR: {result_real['concentration_ratio']}")
    
    # BCR = (100+50) / (20+10) = 150/30 = 5.0 -> ACCUMULATION
    assert result_real['status'] in ['ACCUMULATION', 'BIG_ACCUMULATION']
    print("✅ Bandarmology Test Passed")

if __name__ == "__main__":
    try:
        test_ml_engine()
        test_vpvr()
        test_bandarmology_real()
        print("\n🎉 ALL REAL ENGINE TESTS PASSED")
    except Exception as e:
        print(f"\n❌ TESTS FAILED: {e}")
        import traceback
        traceback.print_exc()
