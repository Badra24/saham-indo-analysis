"""
GoAPI Client for Indonesia Stock Exchange (IDX) Data

Provides real-time data from GoAPI including:
- Broker Summary (Buy/Sell activity by broker)
- Stock Prices
- Historical Data

With graceful fallback to demo data when API is unavailable.

Documentation: https://goapi.io/docs/#/docs/api-market-data-idx
"""

import httpx
from typing import Optional, Dict, List
from datetime import date, timedelta
from app.core.config import settings


# ==================== BROKER CLASSIFICATION DATABASE ====================
# Based on research: "Riset Broker Summary & Bandarmology Saham.txt"

BROKER_TYPES = {
    # === INSTITUTIONAL / SMART MONEY (Foreign) ===
    'AK': {'name': 'UBS Sekuritas', 'type': 'INSTITUTION', 'is_foreign': True, 'weight': 2},
    'BK': {'name': 'JP Morgan', 'type': 'INSTITUTION', 'is_foreign': True, 'weight': 2},
    'KZ': {'name': 'CLSA', 'type': 'INSTITUTION', 'is_foreign': True, 'weight': 2},
    'RX': {'name': 'Macquarie', 'type': 'INSTITUTION', 'is_foreign': True, 'weight': 2},
    'YU': {'name': 'CGS International', 'type': 'INSTITUTION', 'is_foreign': True, 'weight': 2},
    
    # === INSTITUTIONAL / SMART MONEY (Local) ===
    'ZP': {'name': 'Maybank Sekuritas', 'type': 'INSTITUTION', 'is_foreign': False, 'weight': 2},
    'SQ': {'name': 'BCA Sekuritas', 'type': 'INSTITUTION', 'is_foreign': False, 'weight': 2},
    'OD': {'name': 'BRI Danareksa', 'type': 'INSTITUTION', 'is_foreign': False, 'weight': 2},
    'DR': {'name': 'RHB Sekuritas', 'type': 'INSTITUTION', 'is_foreign': False, 'weight': 1},
    'TP': {'name': 'OCBC Sekuritas', 'type': 'INSTITUTION', 'is_foreign': False, 'weight': 1},
    
    # === RETAIL (Mass Market) ===
    'YP': {'name': 'Mirae Asset', 'type': 'RETAIL', 'is_foreign': False, 'weight': -1},
    'PD': {'name': 'Indo Premier (IPOT)', 'type': 'RETAIL', 'is_foreign': False, 'weight': -1},
    'XC': {'name': 'Ajaib Sekuritas', 'type': 'RETAIL', 'is_foreign': False, 'weight': -1},
    'XL': {'name': 'Stockbit Sekuritas', 'type': 'RETAIL', 'is_foreign': False, 'weight': -1},
    'MG': {'name': 'Valbury Sekuritas', 'type': 'RETAIL', 'is_foreign': False, 'weight': -1},
    
    # === MIXED (Both Institutional and Retail) ===
    'CC': {'name': 'Mandiri Sekuritas', 'type': 'MIXED', 'is_foreign': False, 'weight': 0},
    'NI': {'name': 'BNI Sekuritas', 'type': 'MIXED', 'is_foreign': False, 'weight': 0},
    'PP': {'name': 'Aldiracita Sekuritas', 'type': 'MIXED', 'is_foreign': False, 'weight': 0},
    'MS': {'name': 'Morgan Stanley', 'type': 'MIXED', 'is_foreign': True, 'weight': 1},
}

# Status levels (6-tier system from research)
STATUS_LEVELS = {
    'BIG_ACCUMULATION': {'signal': 2, 'label': 'Big Accumulation', 'color': 'green', 'description': 'Institusi agresif membeli'},
    'ACCUMULATION': {'signal': 1, 'label': 'Accumulation', 'color': 'lightgreen', 'description': 'Akumulasi moderat'},
    'NEUTRAL': {'signal': 0, 'label': 'Neutral', 'color': 'gray', 'description': 'Tidak ada arah jelas'},
    'DISTRIBUTION': {'signal': -1, 'label': 'Distribution', 'color': 'orange', 'description': 'Distribusi moderat'},
    'BIG_DISTRIBUTION': {'signal': -2, 'label': 'Big Distribution', 'color': 'red', 'description': 'Institusi agresif menjual'},
    'CHURNING': {'signal': 0, 'label': 'Churning', 'color': 'purple', 'description': 'Wash trading terdeteksi'},
}


# ==================== DEMO DATA (Fallback) ====================

DEMO_BROKER_SUMMARY = {
    "status": "ACCUMULATION",
    "signal_strength": 1,
    "top_buyers": [
        {"code": "AK", "name": "UBS Sekuritas", "type": "INSTITUTION", "value": 50000000000, "is_foreign": True},
        {"code": "ZP", "name": "Maybank", "type": "INSTITUTION", "value": 40000000000, "is_foreign": False},
        {"code": "CC", "name": "Mandiri", "type": "MIXED", "value": 30000000000, "is_foreign": False},
        {"code": "YP", "name": "Mirae Asset", "type": "RETAIL", "value": 20000000000, "is_foreign": False},
        {"code": "XL", "name": "Stockbit", "type": "RETAIL", "value": 10000000000, "is_foreign": False},
    ],
    "top_sellers": [
        {"code": "YP", "name": "Mirae Asset", "type": "RETAIL", "value": 35000000000, "is_foreign": False},
        {"code": "XL", "name": "Stockbit", "type": "RETAIL", "value": 30000000000, "is_foreign": False},
        {"code": "PD", "name": "Indo Premier", "type": "RETAIL", "value": 25000000000, "is_foreign": False},
        {"code": "NI", "name": "BNI Sekuritas", "type": "MIXED", "value": 15000000000, "is_foreign": False},
        {"code": "XC", "name": "Ajaib", "type": "RETAIL", "value": 10000000000, "is_foreign": False},
    ],
    "concentration_ratio": 42.5,
    "dominant_player": "INSTITUTION",
    "institutional_net_flow": 50000000000,
    "retail_net_flow": -45000000000,
    "foreign_net_flow": 30000000000,
    "buy_value": 150000000000,
    "sell_value": 120000000000,
    "net_flow": 30000000000,
    "churn_detected": False,
    "churning_brokers": [],
    "is_demo": True
}


class GoAPIClient:
    """Client for GoAPI Indonesia Stock API with fallback support"""
    
    BASE_URL = "https://api.goapi.io/stock/idx"
    
    def __init__(self):
        self.api_key = settings.GO_API_KEY
        self.headers = {
            "accept": "application/json",
            "X-API-KEY": self.api_key
        }
        self._is_available = None  # Cache availability status
    
    def _request_sync(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make sync request to GoAPI"""
        if not self.api_key:
            return {"status": "error", "message": "No API key configured", "data": None}
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = httpx.get(url, headers=self.headers, params=params, timeout=15.0)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            print(f"GoAPI timeout for {endpoint}")
            return {"status": "error", "message": "Request timeout", "data": None}
        except httpx.HTTPStatusError as e:
            print(f"GoAPI HTTP error: {e.response.status_code}")
            return {"status": "error", "message": f"HTTP {e.response.status_code}", "data": None}
        except Exception as e:
            print(f"GoAPI request error: {e}")
            return {"status": "error", "message": str(e), "data": None}
    
    async def _request_async(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make async request to GoAPI"""
        if not self.api_key:
            return {"status": "error", "message": "No API key configured", "data": None}
        
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"GoAPI async request error: {e}")
                return {"status": "error", "message": str(e), "data": None}
    
    def check_availability(self) -> bool:
        """Test if GoAPI is reachable and API key is valid"""
        try:
            result = self._request_sync("/companies")
            self._is_available = result.get("status") == "success"
            return self._is_available
        except Exception:
            self._is_available = False
            return False

    # ==================== BROKER SUMMARY ====================
    
    def get_broker_summary(
        self, 
        symbol: str, 
        date_str: Optional[str] = None,
        investor: str = "ALL"
    ) -> Dict:
        """
        Get broker summary for a stock with fallback to demo data
        
        Args:
            symbol: Stock symbol (e.g., 'BBCA')
            date_str: Date in YYYY-MM-DD format (default: today)
            investor: 'LOCAL', 'FOREIGN', or 'ALL'
        
        Returns:
            Broker summary in Bandarmology format
        """
        if not date_str:
            # Try today first, then yesterday (market might be closed)
            date_str = date.today().strftime("%Y-%m-%d")
        
        symbol = symbol.replace(".JK", "").upper()
        
        params = {
            "date": date_str,
            "investor": investor
        }
        
        result = self._request_sync(f"/{symbol}/broker_summary", params)
        
        # Check if we got valid data
        if result.get("status") == "success" and result.get("data"):
            return self._parse_broker_summary(result, symbol)
        
        # Try yesterday if today failed (weekend/holiday)
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        params["date"] = yesterday
        result = self._request_sync(f"/{symbol}/broker_summary", params)
        
        if result.get("status") == "success" and result.get("data"):
            return self._parse_broker_summary(result, symbol)
        
        # Fallback to demo data
        print(f"GoAPI unavailable for {symbol}, using demo data")
        return {**DEMO_BROKER_SUMMARY, "symbol": symbol}
    
    def _parse_broker_summary(self, raw_data: Dict, symbol: str) -> Dict:
        """
        Enhanced Broker Summary Parser with Bandarmology Algorithm
        Based on: "Riset Broker Summary & Bandarmology Saham.txt"
        
        Features:
        - Broker type classification (INSTITUTION/RETAIL/MIXED)
        - 6-tier status detection (BIG_ACCUMULATION, CHURNING, etc.)
        - Wash trading (churning) detection
        - Foreign vs Local flow separation
        """
        results = raw_data.get("data", {}).get("results", [])
        
        if not results:
            return {**DEMO_BROKER_SUMMARY, "symbol": symbol, "is_demo": True}
        
        # ==================== SEPARATE BUYS AND SELLS ====================
        buys = [r for r in results if r.get("side") == "BUY"]
        sells = [r for r in results if r.get("side") == "SELL"]
        
        # Sort by value (highest first)
        buys.sort(key=lambda x: x.get("value", 0), reverse=True)
        sells.sort(key=lambda x: x.get("value", 0), reverse=True)
        
        # ==================== ENRICH WITH BROKER INFO ====================
        def enrich_broker(broker_data: Dict) -> Dict:
            """Add broker classification info"""
            code = broker_data.get("code", "")
            broker_info = BROKER_TYPES.get(code, {
                'name': broker_data.get("broker", {}).get("name", code),
                'type': 'UNKNOWN',
                'is_foreign': False,
                'weight': 0
            })
            return {
                "code": code,
                "name": broker_info.get("name", code),
                "type": broker_info.get("type", "UNKNOWN"),
                "value": broker_data.get("value", 0),
                "volume": broker_data.get("lot", 0) * 100,  # lot to shares
                "is_foreign": broker_info.get("is_foreign", False),
                "weight": broker_info.get("weight", 0)
            }
        
        top_buyers_enriched = [enrich_broker(b) for b in buys[:5]]
        top_sellers_enriched = [enrich_broker(s) for s in sells[:5]]
        
        # ==================== CALCULATE TOTALS ====================
        total_buy_value = sum(b.get("value", 0) for b in buys)
        total_sell_value = sum(s.get("value", 0) for s in sells)
        net_flow = total_buy_value - total_sell_value
        
        # Top 5 concentration
        top5_buy = sum(b.get("value", 0) for b in buys[:5])
        concentration_ratio = (top5_buy / total_buy_value * 100) if total_buy_value > 0 else 0
        
        # ==================== CALCULATE FLOW BY TYPE ====================
        institutional_buy = sum(b.get("value", 0) for b in buys if BROKER_TYPES.get(b.get("code", ""), {}).get("type") == "INSTITUTION")
        institutional_sell = sum(s.get("value", 0) for s in sells if BROKER_TYPES.get(s.get("code", ""), {}).get("type") == "INSTITUTION")
        institutional_net = institutional_buy - institutional_sell
        
        retail_buy = sum(b.get("value", 0) for b in buys if BROKER_TYPES.get(b.get("code", ""), {}).get("type") == "RETAIL")
        retail_sell = sum(s.get("value", 0) for s in sells if BROKER_TYPES.get(s.get("code", ""), {}).get("type") == "RETAIL")
        retail_net = retail_buy - retail_sell
        
        foreign_buy = sum(b.get("value", 0) for b in buys if BROKER_TYPES.get(b.get("code", ""), {}).get("is_foreign", False))
        foreign_sell = sum(s.get("value", 0) for s in sells if BROKER_TYPES.get(s.get("code", ""), {}).get("is_foreign", False))
        foreign_net = foreign_buy - foreign_sell
        
        # ==================== DETECT CHURNING (WASH TRADING) ====================
        churning_brokers = []
        all_broker_codes = set(b.get("code") for b in buys) | set(s.get("code") for s in sells)
        
        for code in all_broker_codes:
            broker_buys = sum(b.get("value", 0) for b in buys if b.get("code") == code)
            broker_sells = sum(s.get("value", 0) for s in sells if s.get("code") == code)
            total_broker = broker_buys + broker_sells
            
            if total_broker > 0:
                # Churn ratio: 1 - |buy - sell| / (buy + sell)
                churn_ratio = 1 - abs(broker_buys - broker_sells) / total_broker
                
                # High churn (>0.8) and significant volume (>5% of total)
                total_market = total_buy_value + total_sell_value
                volume_pct = total_broker / total_market * 100 if total_market > 0 else 0
                
                if churn_ratio > 0.8 and volume_pct > 5:
                    churning_brokers.append({
                        "code": code,
                        "churn_ratio": round(churn_ratio, 2),
                        "volume_pct": round(volume_pct, 2)
                    })
        
        churn_detected = len(churning_brokers) > 0
        
        # ==================== DETERMINE 6-TIER STATUS ====================
        # Check institutional dominance in top buyers
        top3_buyers_institutional = sum(1 for b in top_buyers_enriched[:3] if b.get("type") == "INSTITUTION")
        top3_sellers_institutional = sum(1 for s in top_sellers_enriched[:3] if s.get("type") == "INSTITUTION")
        
        # Determine status based on research algorithm
        if churn_detected and len(churning_brokers) >= 2:
            status = "CHURNING"
            signal_strength = 0
        elif total_buy_value > total_sell_value * 1.2:
            # Accumulation detected - check quality
            if top3_buyers_institutional >= 2 and institutional_net > 0:
                status = "BIG_ACCUMULATION"
                signal_strength = 2
            else:
                status = "ACCUMULATION"
                signal_strength = 1
        elif total_sell_value > total_buy_value * 1.2:
            # Distribution detected - check quality
            if top3_sellers_institutional >= 2 and institutional_net < 0:
                status = "BIG_DISTRIBUTION"
                signal_strength = -2
            else:
                status = "DISTRIBUTION"
                signal_strength = -1
        else:
            status = "NEUTRAL"
            signal_strength = 0
        
        # ==================== DETERMINE DOMINANT PLAYER ====================
        if institutional_net > abs(retail_net) and institutional_net > 0:
            dominant_player = "INSTITUTION"
        elif retail_net > abs(institutional_net) and retail_net > 0:
            dominant_player = "RETAIL"
        elif concentration_ratio > 50:
            dominant_player = "INSTITUTION"
        elif concentration_ratio > 30:
            dominant_player = "MIXED"
        else:
            dominant_player = "RETAIL"
        
        return {
            "status": status,
            "signal_strength": signal_strength,
            "top_buyers": top_buyers_enriched,
            "top_sellers": top_sellers_enriched,
            "concentration_ratio": round(concentration_ratio, 2),
            "dominant_player": dominant_player,
            "institutional_net_flow": institutional_net,
            "retail_net_flow": retail_net,
            "foreign_net_flow": foreign_net,
            "buy_value": total_buy_value,
            "sell_value": total_sell_value,
            "net_flow": net_flow,
            "churn_detected": churn_detected,
            "churning_brokers": churning_brokers,
            "symbol": symbol,
            "is_demo": False
        }
    
    # ==================== STOCK PRICES ====================
    
    def get_stock_price(self, symbol: str) -> Optional[Dict]:
        """Get current price for a stock"""
        symbol = symbol.replace(".JK", "").upper()
        params = {"symbols": symbol}
        result = self._request_sync("/prices", params)
        
        if result.get("status") == "success":
            results = result.get("data", {}).get("results", [])
            if results:
                return results[0]
        return None
    
    # ==================== HISTORICAL DATA ====================
    
    def get_historical(
        self, 
        symbol: str, 
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Dict]:
        """Get historical OHLCV data"""
        symbol = symbol.replace(".JK", "").upper()
        
        if not to_date:
            to_date = date.today().strftime("%Y-%m-%d")
        if not from_date:
            from_date = (date.today() - timedelta(days=180)).strftime("%Y-%m-%d")
        
        params = {"from": from_date, "to": to_date}
        result = self._request_sync(f"/{symbol}/historical", params)
        
        if result.get("status") == "success":
            return result.get("data", {}).get("results", [])
        return []

    # ==================== BROKER ACTIVITY HISTORY ====================
    
    def get_broker_history(
        self,
        broker_code: str,
        symbol: str,
        days: int = 30
    ) -> Dict:
        """
        Get broker activity history for a specific stock over N days.
        Calculates running position, trend, and daily activity.
        
        Args:
            broker_code: Broker code (e.g., 'YP', 'AK')
            symbol: Stock symbol (e.g., 'BBCA')
            days: Number of days to fetch (default: 30)
        
        Returns:
            Activity history with running position and trend analysis
        """
        symbol = symbol.replace(".JK", "").upper()
        broker_code = broker_code.upper()
        
        # Get broker info
        broker_info = BROKER_TYPES.get(broker_code, {
            'name': broker_code,
            'type': 'UNKNOWN',
            'is_foreign': False
        })
        
        daily_activity = []
        running_buy = 0
        running_sell = 0
        
        # Fetch data for each day
        today = date.today()
        
        for i in range(days):
            target_date = today - timedelta(days=i)
            # Skip weekends
            if target_date.weekday() >= 5:
                continue
                
            date_str = target_date.strftime("%Y-%m-%d")
            
            try:
                # Rate limiting: 300ms delay to avoid 429 errors
                import time
                time.sleep(0.3)
                
                result = self._request_sync(f"/{symbol}/broker_summary", {"date": date_str, "investor": "ALL"})
                
                if result.get("status") == "success":
                    results = result.get("data", {}).get("results", [])
                    
                    # Find this broker's activity
                    buy_value = 0
                    sell_value = 0
                    buy_volume = 0
                    sell_volume = 0
                    
                    for r in results:
                        if r.get("code") == broker_code:
                            if r.get("side") == "BUY":
                                buy_value = r.get("value", 0)
                                buy_volume = r.get("lot", 0) * 100
                            elif r.get("side") == "SELL":
                                sell_value = r.get("value", 0)
                                sell_volume = r.get("lot", 0) * 100
                    
                    net_value = buy_value - sell_value
                    running_buy += buy_value
                    running_sell += sell_value
                    
                    if buy_value > 0 or sell_value > 0:
                        daily_activity.append({
                            "date": date_str,
                            "buy_value": buy_value,
                            "sell_value": sell_value,
                            "net_value": net_value,
                            "buy_volume": buy_volume,
                            "sell_volume": sell_volume
                        })
                        
            except Exception as e:
                print(f"Error fetching broker history for {date_str}: {e}")
                continue
        
        # Calculate statistics
        total_net = running_buy - running_sell
        active_days = len(daily_activity)
        avg_daily_volume = sum(d["buy_volume"] + d["sell_volume"] for d in daily_activity) / max(active_days, 1)
        
        # Determine trend
        if active_days >= 5:
            recent_net = sum(d["net_value"] for d in daily_activity[:5])
            if recent_net > 0 and total_net > 0:
                trend = "AKUMULASI_AKTIF"
            elif recent_net < 0 and total_net < 0:
                trend = "DISTRIBUSI_AKTIF"
            elif recent_net > 0:
                trend = "MULAI_AKUMULASI"
            elif recent_net < 0:
                trend = "MULAI_DISTRIBUSI"
            else:
                trend = "NETRAL"
        else:
            trend = "DATA_TERBATAS"
        
        return {
            "broker_code": broker_code,
            "broker_name": broker_info.get("name", broker_code),
            "broker_type": broker_info.get("type", "UNKNOWN"),
            "is_foreign": broker_info.get("is_foreign", False),
            "symbol": symbol,
            "days_analyzed": days,
            "active_days": active_days,
            "running_buy": running_buy,
            "running_sell": running_sell,
            "running_position": total_net,
            "avg_daily_volume": round(avg_daily_volume, 0),
            "trend": trend,
            "daily_activity": daily_activity[:10],  # Return last 10 days only
            "is_demo": False if daily_activity else True
        }


# ==================== SINGLETON INSTANCE ====================

_goapi_client: Optional[GoAPIClient] = None

def get_goapi_client() -> GoAPIClient:
    """Get or create GoAPI client instance"""
    global _goapi_client
    if _goapi_client is None:
        _goapi_client = GoAPIClient()
    return _goapi_client


def test_goapi_connection() -> Dict:
    """Test GoAPI connection and return status"""
    client = get_goapi_client()
    
    if not client.api_key:
        return {
            "connected": False,
            "message": "GO_API_KEY not configured in .env",
            "using_demo": True
        }
    
    is_available = client.check_availability()
    
    if is_available:
        # Try to get broker summary for a common stock
        test_data = client.get_broker_summary("BBCA")
        return {
            "connected": True,
            "message": "GoAPI connected successfully",
            "using_demo": test_data.get("is_demo", False),
            "sample_data": test_data
        }
    else:
        return {
            "connected": False,
            "message": "GoAPI unreachable, using demo data",
            "using_demo": True
        }


# ==================== HYBRID IDX BROWSER + GOAPI ====================

async def get_broker_summary_hybrid(
    symbol: str,
    date_str: Optional[str] = None,
    use_browser: bool = True
) -> Dict:
    """
    Hybrid broker summary that tries IDX Browser first (no rate limits),
    then falls back to GoAPI if browser fails.
    
    This solves the GoAPI rate limiting issue (30/day, 500/month).
    
    Args:
        symbol: Stock symbol (e.g., 'BBCA')
        date_str: Date in YYYY-MM-DD format
        use_browser: Whether to try IDX Browser first (default: True)
    
    Returns:
        Broker summary in Bandarmology format
    """
    symbol = symbol.replace(".JK", "").upper()
    
    if not date_str:
        date_str = date.today().strftime("%Y-%m-%d")
    
    # Try IDX Broker Aggregator first (loops through brokers to find stock data)
    if use_browser:
        try:
            from app.services.idx_broker_aggregator import get_broker_aggregator
            
            # Format date for aggregator (YYYYMMDD)
            idx_date = date_str.replace("-", "")
            
            aggregator = get_broker_aggregator()
            result = await aggregator.get_broker_summary_for_stock(symbol, idx_date)
            
            if result and not result.get("is_demo", False) and result.get("brokers_active", 0) > 0:
                print(f"[HYBRID] Got broker data for {symbol} from IDX Aggregator")
                return result
            else:
                print(f"[HYBRID] IDX Aggregator found no data for {symbol}")
                
        except Exception as e:
            print(f"[HYBRID] IDX Aggregator failed for {symbol}: {e}")
    
    # Fallback to GoAPI
    try:
        from app.services.api_usage_tracker import can_make_api_call, record_api_call
        
        if can_make_api_call():
            goapi_client = get_goapi_client()
            goapi_data = goapi_client.get_broker_summary(symbol, date_str)
            
            if not goapi_data.get("is_demo", False):
                record_api_call(symbol)
                goapi_data["source"] = "goapi"
                print(f"[HYBRID] Got broker data for {symbol} from GoAPI")
                return goapi_data
        else:
            print(f"[HYBRID] GoAPI rate limit reached for {symbol}")
            
    except Exception as e:
        print(f"[HYBRID] GoAPI failed for {symbol}: {e}")
    
    # If all sources fail, return empty state (NO DEMO DATA)
    print(f"[HYBRID] No real data available for {symbol}")
    return {
        "symbol": symbol,
        "status": "DATA_UNAVAILABLE", 
        "top_buyers": [],
        "top_sellers": [],
        "net_flow": 0,
        "buy_value": 0,
        "sell_value": 0,
        "source": "none",
        "is_demo": False  # Explicitly False per user request
    }


async def get_stock_summary_hybrid(
    symbol: str = None,
    date_str: Optional[str] = None
) -> Optional[Dict]:
    """
    Get stock trading summary using IDX Browser.
    This is data that GoAPI doesn't provide directly.
    
    Args:
        symbol: Stock symbol to filter (e.g., 'BBCA')
        date_str: Date in YYYY-MM-DD format
    """
    try:
        from app.services.idx_browser_client import get_idx_browser_client
        
        browser_client = get_idx_browser_client()
        data = await browser_client.get_stock_summary(symbol, date_str)
        
        if data:
            print(f"[HYBRID] Got stock summary for {symbol or 'all'}")
            return data
            
    except Exception as e:
        print(f"[HYBRID] Stock summary failed: {e}")
    
    return None

