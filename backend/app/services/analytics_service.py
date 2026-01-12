from app.services.database_service import db_service, DatabaseService
from typing import List, Dict

class AnalyticsService:
    """
    Analytics Service for Deep Analysis Features.
    Queries DuckDB to provide Trend and Heatmap data.
    """
    
    def __init__(self, db: DatabaseService = db_service):
        self.db = db
        
    def get_net_flow_trend(self, ticker: str, days: int = 30) -> List[Dict]:
        """
        Get Daily Net Flow Trend for Institutional, Retail, Foreign.
        """
        conn = self.db.get_connection()
        query = """
            SELECT date, institutional_net_flow, retail_net_flow, foreign_net_flow, status, bcr
            FROM bandarmology_daily_stats
            WHERE ticker = ? 
            ORDER BY date ASC -- Chronological for Chart
            LIMIT ?
        """
        rows = conn.execute(query, (ticker, days)).fetchall()
        
        results = []
        cumulative_inst = 0
        cumulative_foreign = 0
        
        for row in rows:
            inst_flow = row[1] or 0
            foreign_flow = row[3] or 0
            
            cumulative_inst += inst_flow
            cumulative_foreign += foreign_flow
            
            results.append({
                "date": str(row[0]),
                "institutional_flow": inst_flow,
                "retail_flow": row[2] or 0,
                "foreign_flow": foreign_flow,
                "cumulative_institutional": cumulative_inst,
                "cumulative_foreign": cumulative_foreign,
                "status": row[4],
                "bcr": row[5]
            })
            
        return results

    def get_broker_heatmap(self, ticker: str, days: int = 30) -> List[Dict]:
        """
        Get Aggregated Buy/Sell Value per Broker for Heatmap.
        """
        conn = self.db.get_connection()
        query = """
            SELECT 
                broker_code, 
                SUM(buy_value) as total_buy, 
                SUM(sell_value) as total_sell, 
                SUM(net_value) as total_net,
                MAX(broker_type) as type,
                BOOL_OR(is_foreign) as is_foreign
            FROM broker_summary_history
            WHERE ticker = ? 
            GROUP BY broker_code
            ORDER BY ABS(total_net) DESC -- Most active accumulation/distribution
            LIMIT 50
        """
        rows = conn.execute(query, (ticker,)).fetchall() # Limit in query
        
        results = []
        for row in rows:
            results.append({
                "broker_code": row[0],
                "total_buy": row[1],
                "total_sell": row[2],
                "net_value": row[3],
                "type": row[4],
                "is_foreign": row[5]
            })
            
        return results

analytics_service = AnalyticsService()
