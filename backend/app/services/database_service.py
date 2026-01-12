import duckdb
import os
from datetime import datetime, date
import json
from typing import List, Dict, Optional, Any

class DatabaseService:
    """
    DuckDB Database Service for Saham-Indo.
    Stores persistent broker summary history for Deep Analysis.
    """
    
    DB_PATH = "saham_indo.duckdb"
    
    def __init__(self):
        self._conn = None
        # Lazy initialization - Do NOT connect in __init__
        # This prevents lock issues during import/worker spawn
        
    def get_connection(self, read_only=False):
        # 1. Reuse existing connection if available
        # This prevents "Conflicting lock" if we try to open a 2nd connection in the same process
        if self._conn is not None:
             return self._conn

        # 2. Connect (with Retry Logic for Restarts)
        import time
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # Try opening normally (Read/Write)
                self._conn = duckdb.connect(self.DB_PATH, read_only=False)
                self.init_db() 
                return self._conn
            except Exception as e:
                if "Conflicting lock" in str(e):
                    if attempt < max_retries - 1:
                        print(f"⚠️ Main DB locked, retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        # Final attempt failed - Fallback to Read Only
                        print(f"⚠️ Main DB locked after retries. Falling back to READ_ONLY connection: {e}")
                        try:
                            self._conn = duckdb.connect(self.DB_PATH, read_only=True)
                            print("✅ READ_ONLY connection established.")
                            return self._conn
                        except Exception as e2:
                             print(f"❌ DB Connection Critical Failure: {e2}")
                             raise e2 # Cannot recover
                else:
                    raise e
                    
        return self._conn
        
    def close(self):
        """Explicitly close connection"""
        if self._conn:
            try:
                self._conn.close()
                self._conn = None
                print("[DB] Connection closed cleanly.")
            except Exception as e:
                print(f"⚠️ Error closing DB: {e}")

    def init_db(self):
        """Initialize database schema - Called internally by get_connection"""
        # Do not call get_connection() here recursively
        if self._conn is None:
             return
             
        conn = self._conn
        
        # Table: broker_summary_history
        # Stores daily net buy/sell for each broker per stock
        conn.execute("""
            CREATE TABLE IF NOT EXISTS broker_summary_history (
                date DATE,
                ticker VARCHAR,
                broker_code VARCHAR,
                buy_value DOUBLE,
                sell_value DOUBLE,
                net_value DOUBLE generated always as (buy_value - sell_value),
                buy_volume BIGINT,
                sell_volume BIGINT,
                net_volume BIGINT generated always as (buy_volume - sell_volume),
                broker_type VARCHAR, -- RETAIL, INSTITUTION
                is_foreign BOOLEAN,
                source VARCHAR, -- 'goapi', 'upload', 'mock'
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, ticker, broker_code)
            )
        """)
        
        # Table: bandarmology_daily_stats
        # Stores computed stats (BCR, Status) per day
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bandarmology_daily_stats (
                date DATE,
                ticker VARCHAR,
                status VARCHAR, -- ACCUMULATION, DISTRIBUTION
                bcr DOUBLE,
                top1_buyer VARCHAR,
                top1_seller VARCHAR,
                institutional_net_flow DOUBLE,
                retail_net_flow DOUBLE,
                foreign_net_flow DOUBLE,
                source VARCHAR,
                PRIMARY KEY (date, ticker)
            )
        """)
        
        # Table: financial_reports (Persistent storage for Alpha-V)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS financial_reports (
                ticker VARCHAR,
                period VARCHAR,
                report_type VARCHAR,
                
                -- Valuation
                per DOUBLE,
                pbv DOUBLE,
                pcf DOUBLE,
                ev_ebitda DOUBLE,
                peg DOUBLE,
                
                -- Quality
                roe DOUBLE,
                roa DOUBLE,
                npm DOUBLE,
                opm DOUBLE,
                
                -- Solvency
                der DOUBLE,
                current_ratio DOUBLE,
                quick_ratio DOUBLE,
                
                -- Raw / Other
                net_income DOUBLE,
                ocf DOUBLE,
                revenue_growth DOUBLE,
                earnings_growth DOUBLE,
                sector VARCHAR,
                
                source VARCHAR,
                file_name VARCHAR,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, period)
            )
        """)
        
    def insert_broker_summary(self, ticker: str, date_str: str, data: Dict, source: str = 'goapi'):
        """
        Insert parsed broker summary data into DuckDB.
        Handles both raw broker rows and computed stats.
        """
        conn = self.get_connection()
        
        # 1. Parse Date
        if isinstance(date_str, str):
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
            except:
                dt = date.today()
        else:
            dt = date_str
            
        # 2. Prepare Broker Rows
        # Data format from GoAPI/Bandarmology: top_buyers List[Dict], top_sellers List[Dict]
        # We need to merge them by broker code because a broker can be both buyer and seller
        
        brokers_map = {} # code -> {buy_val, sell_val, ...}
        
        for b in data.get('top_buyers', []):
            code = b['code']
            if code not in brokers_map:
                brokers_map[code] = {'buy_val':0, 'sell_val':0, 'buy_vol':0, 'sell_vol':0, 'type': b.get('type', 'UNKNOWN'), 'foreign': b.get('is_foreign', False)}
            brokers_map[code]['buy_val'] = float(b.get('value', 0))
            brokers_map[code]['buy_vol'] = int(b.get('volume', 0))
            
        for s in data.get('top_sellers', []):
            code = s['code']
            if code not in brokers_map:
                brokers_map[code] = {'buy_val':0, 'sell_val':0, 'buy_vol':0, 'sell_vol':0, 'type': s.get('type', 'UNKNOWN'), 'foreign': s.get('is_foreign', False)}
            brokers_map[code]['sell_val'] = float(s.get('value', 0))
            brokers_map[code]['sell_vol'] = int(s.get('volume', 0))
            
        # Bulk Insert Broker Rows
        for code, info in brokers_map.items():
            conn.execute("""
                INSERT OR REPLACE INTO broker_summary_history 
                (date, ticker, broker_code, buy_value, sell_value, buy_volume, sell_volume, broker_type, is_foreign, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dt, ticker, code, 
                info['buy_val'], info['sell_val'], 
                info['buy_vol'], info['sell_vol'],
                info['type'], info['foreign'],
                source
            ))
            
        # 3. Insert Daily Stats
        conn.execute("""
            INSERT OR REPLACE INTO bandarmology_daily_stats
            (date, ticker, status, bcr, top1_buyer, top1_seller, institutional_net_flow, retail_net_flow, foreign_net_flow, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dt, ticker, 
            data.get('status', 'NEUTRAL'),
            data.get('concentration_ratio', 0) / 30.0 if data.get('concentration_ratio') else 1.0, # Approximate reverse of scale
            data['top_buyers'][0]['code'] if data.get('top_buyers') else None,
            data['top_sellers'][0]['code'] if data.get('top_sellers') else None,
            data.get('institutional_net_flow', 0),
            data.get('retail_net_flow', 0),
            data.get('foreign_net_flow', 0),
            source
        ))
        
        print(f"[DB] Saved stats for {ticker} on {dt}")

    def get_history(self, ticker: str, days: int = 30) -> List[Dict]:
        """Get historical stats for charts"""
        conn = self.get_connection(read_only=True)
        query = """
            SELECT date, status, bcr, institutional_net_flow, retail_net_flow, foreign_net_flow, top1_buyer, top1_seller
            FROM bandarmology_daily_stats
            WHERE ticker = ? 
            ORDER BY date DESC
            LIMIT ?
        """
        result = conn.execute(query, (ticker, days)).fetchall()
        
        # Convert to list of dicts
        history = []
        for row in result:
             history.append({
                 "date": str(row[0]),
                 "status": row[1],
                 "bcr": row[2],
                 "institutional_flow": row[3],
                 "retail_flow": row[4],
                 "foreign_flow": row[5],
                 "top_buyer": row[6],
                 "top_seller": row[7]
             })
        return history[::-1] # Return chronological order

    def get_broker_summary_by_date(self, ticker: str, date_str: str) -> Optional[Dict]:
        """
        Try to retrieve full broker summary from DB for a specific date.
        Used to optimize API calls.
        """
        conn = self.get_connection(read_only=True)
        
        # 1. Get Daily Stats
        stats_query = """
            SELECT status, bcr, institutional_net_flow, retail_net_flow, foreign_net_flow, source
            FROM bandarmology_daily_stats
            WHERE ticker = ? AND date = ?
        """
        stats_row = conn.execute(stats_query, (ticker, date_str)).fetchone()
        
        if not stats_row:
            return None
            
        result = {
            "status": stats_row[0], # Index 0 is status
            "concentration_ratio": stats_row[1] * 30.0 if stats_row[1] else 0, # Index 1 is bcr
            # Actually, standard GoAPI returns 0-100 logic or similar. The DB stores normalized. 
            # In insert: data.get('concentration_ratio', 0) / 30.0
            # So restore: * 30.0
            "institutional_net_flow": stats_row[2],
            "retail_net_flow": stats_row[3],
            "foreign_net_flow": stats_row[4],
            "source": f"{stats_row[5]} (DB)", # Mark as from DB
            "top_buyers": [],
            "top_sellers": []
        }
        
        # 2. Get Broker Rows
        brokers_query = """
            SELECT broker_code, buy_value, sell_value, buy_volume, sell_volume, broker_type, is_foreign
            FROM broker_summary_history
            WHERE ticker = ? AND date = ?
        """
        rows = conn.execute(brokers_query, (ticker, date_str)).fetchall()
        
        # 3. Reconstruct Top Buyers/Sellers & Calculate Totals
        buyers = []
        sellers = []
        
        total_buy = 0.0
        total_sell = 0.0
        
        for r in rows:
            code, b_val, s_val, b_vol, s_vol, b_type, is_for = r
            
            total_buy += b_val
            total_sell += s_val
            
            # Buyer Entry
            if b_val > 0:
                buyers.append({
                    "code": code,
                    "value": b_val,
                    "volume": b_vol,
                    "type": b_type,
                    "is_foreign": is_for
                })
            
            # Seller Entry
            if s_val > 0:
                sellers.append({
                    "code": code,
                    "value": s_val,
                    "volume": s_vol,
                    "type": b_type,
                    "is_foreign": is_for
                })
                
        # Sort
        buyers.sort(key=lambda x: x['value'], reverse=True)
        sellers.sort(key=lambda x: x['value'], reverse=True)
        
        result["top_buyers"] = buyers
        result["top_sellers"] = sellers
        result["buy_value"] = total_buy
        result["sell_value"] = total_sell
        result["net_value"] = total_buy - total_sell
        
        return result
        
    def insert_financial_report(self, ticker: str, data: Dict):
        """
        Insert parsed financial report data into DuckDB.
        """
        conn = self.get_connection()
        dt = date.today()
        
        # Ensure schema exists (if added later)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS financial_reports (
                ticker VARCHAR,
                period VARCHAR,
                report_type VARCHAR,
                
                -- Valuation
                per DOUBLE,
                pbv DOUBLE,
                pcf DOUBLE,
                ev_ebitda DOUBLE,
                peg DOUBLE,
                
                -- Quality
                roe DOUBLE,
                roa DOUBLE,
                npm DOUBLE,
                opm DOUBLE,
                
                -- Solvency
                der DOUBLE,
                current_ratio DOUBLE,
                quick_ratio DOUBLE,
                
                -- Raw / Other
                net_income DOUBLE,
                ocf DOUBLE,
                revenue_growth DOUBLE,
                earnings_growth DOUBLE,
                sector VARCHAR,
                
                source VARCHAR,
                file_name VARCHAR,
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, period)
            )
        """)
        
        # Insert
        conn.execute("""
            INSERT OR REPLACE INTO financial_reports 
            (ticker, period, report_type, per, pbv, pcf, ev_ebitda, peg, roe, roa, npm, opm, 
             der, current_ratio, quick_ratio, net_income, ocf, revenue_growth, earnings_growth, sector, source, file_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker, 
            data.get('period', 'UNKNOWN'),
            data.get('report_type', 'quarterly'),
            data.get('per'), data.get('pbv'), data.get('pcf'), data.get('ev_ebitda'), data.get('peg'),
            data.get('roe'), data.get('roa'), data.get('npm'), data.get('opm'),
            data.get('der'), data.get('current_ratio'), data.get('quick_ratio'),
            data.get('net_income'), data.get('ocf'),
            data.get('revenue_growth'), data.get('earnings_growth'),
            data.get('sector'),
            data.get('source', 'upload'),
            data.get('file_name')
        ))
        
        print(f"[DB] Saved financial report for {ticker} ({data.get('period')})")

    def get_financial_report(self, ticker: str) -> Optional[Dict]:
        """
        Get latest financial report for a ticker.
        """
        conn = self.get_connection(read_only=True)
        
        # Check if table exists first (migration safety)
        try:
           conn.execute("SELECT 1 FROM financial_reports LIMIT 1")
        except:
           return None

        query = """
            SELECT * FROM financial_reports 
            WHERE ticker = ? 
            ORDER BY inserted_at DESC 
            LIMIT 1
        """
        row = conn.execute(query, (ticker,)).fetchone()
        
        if not row:
            return None
            
        columns = [desc[0] for desc in conn.description]
        result = dict(zip(columns, row))
        
        return result

# Global Singleton
db_service = DatabaseService()
