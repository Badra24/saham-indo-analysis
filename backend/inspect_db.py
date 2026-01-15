
import duckdb
import pandas as pd
from app.services.database_service import DatabaseService

# Initialize Service (this handles connection logic)
db = DatabaseService()

def inspect_data():
    conn = db.get_connection()
    if not conn:
        print("Failed to get connection")
        return

    try:
        # Check table schema
        print("\n--- Schema (broker_summary_history) ---")
        # print(conn.execute("DESCRIBE broker_summary_history").df())
        
        # Check Data for BBCA
        print("\n--- Data for BBCA (broker_summary_history) ---")
        df = conn.execute("SELECT ticker, date, broker_code, buy_value, sell_value, source FROM broker_summary_history WHERE ticker LIKE 'BBCA%' ORDER BY date DESC LIMIT 10").df()
        print(df)
        
        print("\n--- Data for BBCA (bandarmology_daily_stats) ---")
        df2 = conn.execute("SELECT ticker, date, status, source FROM bandarmology_daily_stats WHERE ticker LIKE 'BBCA%' ORDER BY date DESC LIMIT 5").df()
        print(df2)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    import os
    # Fix path
    sys.path.append(os.getcwd())
    inspect_data()
