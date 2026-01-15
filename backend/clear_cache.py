
import duckdb
import os

# Explicitly target the backend DB file
DB_PATH = "backend/saham_indo.duckdb"

def clear_cache():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB File not found at {DB_PATH}")
        # Try local path if running from backend dir
        if os.path.exists("saham_indo.duckdb"):
            print("Found saham_indo.duckdb in current dir")
            DB_PATH_LOCAL = "saham_indo.duckdb"
        else:
            return
    else:
        DB_PATH_LOCAL = DB_PATH

    print(f"Opening DB at: {DB_PATH_LOCAL}")
    conn = duckdb.connect(DB_PATH_LOCAL)
    
    try:
        # Check count before
        count_hist = conn.execute("SELECT COUNT(*) FROM broker_summary_history WHERE ticker LIKE 'BBCA%'").fetchone()[0]
        count_stats = conn.execute("SELECT COUNT(*) FROM bandarmology_daily_stats WHERE ticker LIKE 'BBCA%'").fetchone()[0]
        print(f"Found {count_hist} history rows and {count_stats} stats rows for BBCA before delete.")
        
        # DELETE
        conn.execute("DELETE FROM broker_summary_history WHERE ticker LIKE 'BBCA%'")
        conn.execute("DELETE FROM bandarmology_daily_stats WHERE ticker LIKE 'BBCA%'")
        
        print("✅ Deleted BBCA records.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    clear_cache()
