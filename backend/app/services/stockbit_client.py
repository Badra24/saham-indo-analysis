
import httpx
import logging
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Try loading from backend if default fails
if not load_dotenv():
    load_dotenv("backend/.env")

logger = logging.getLogger(__name__)

# ==========================================
# BROKER DATA CONSTANTS
# Source: brokerSearch.json & Market Knowledge
# ==========================================
RETAIL_BROKERS = {
    'YP': 'Mirae', 'PD': 'IndoPremier', 'CC': 'Mandiri', 'NI': 'BNI', 
    'XL': 'Stockbit', 'XC': 'Ajaib', 'KK': 'Philip', 'SQ': 'BCA', 
    'AZ': 'Sucor', 'EP': 'MNC', 'GR': 'Panin', 'DR': 'RHB',
    'OD': 'Danareksa', 'MG': 'Semesta', 'YJ': 'Lotus', 'CP': 'Valbury',
    'HP': 'Henan', 'AG': 'Kiwoom', 'BQ': 'KoreaInv', 'XA': 'NH Korindo'
}

# Converted to Dict for consistency and Mapping
# Converted to Dict for consistency and Mapping
FOREIGN_BROKER_MAP = {
    'ZP': 'Maybank', 'AK': 'UBS', 'JU': 'UOB', 'BK': 'JP Morgan', 
    'KZ': 'CLSA', 'CS': 'Credit Suisse', 'RX': 'Macquarie', 
    'YU': 'CIMB', 'AI': 'UOB Kay Hian', 'FS': 'Yuanta', 'MS': 'Morgan Stanley'
}

INST_BROKERS = {
    'BB': 'Verdhana', 'DX': 'Bahana', 'LG': 'Trimegah', 'KI': 'Ciptadana',
    'IF': 'Samuel', 'DH': 'Sinarmas', 'RF': 'Buana', 'ID': 'Anugerah',
    'DP': 'DBS', 'SP': 'Sinarmas', 'YO': 'Amantara', 'SH': 'Artha'
}

def get_broker_category(code: str) -> str:
    """Get category (Foreign, Retail, Inst) from broker code."""
    if code in FOREIGN_BROKER_MAP: return "Foreign"
    elif code in RETAIL_BROKERS or code == 'XL': return "Retail"
    elif code in INST_BROKERS: return "Inst"
    return "Retail" # Default

class StockbitClient:
    """
    Client for interacting with the Stockbit API (Exodus).
    Authentication requires STOCKBIT_AUTH_TOKEN in env.
    
    Supports runtime token update for Docker deployment:
        stockbit_client.update_token("new_token_here")
    """
    
    BASE_URL = "https://exodus.stockbit.com"
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv("STOCKBIT_AUTH_TOKEN")
        self._token_valid = True
        self._last_error = None
        self._last_error_time = None
        self._request_count = 0
        
        if not self.token:
            logger.warning("STOCKBIT_AUTH_TOKEN not set. Client will fail explicitly.")
            self._token_valid = False
        
        self._setup_headers()
    
    def _setup_headers(self):
        """Setup HTTP headers with current token."""
        # Ensure Bearer prefix
        if self.token and not self.token.startswith("Bearer "):
            self.token = f"Bearer {self.token}"

        self.headers = {
            "Authorization": self.token,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Origin": "https://stockbit.com",
            "Referer": "https://stockbit.com/",
            "sec-ch-ua": '"Opera GX";v="125", "Not?A_Brand";v="8", "Chromium";v="141"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"'
        }
    
    def update_token(self, new_token: str) -> bool:
        """
        Update token at runtime (for Docker hot-reload).
        
        Args:
            new_token: New Stockbit auth token (with or without 'Bearer ' prefix)
            
        Returns:
            True if token was updated successfully
        """
        if not new_token:
            return False
            
        self.token = new_token
        self._token_valid = True
        self._last_error = None
        self._last_error_time = None
        self._setup_headers()
        
        logger.info("Stockbit token updated successfully")
        return True
    
    def get_status(self) -> dict:
        """
        Get current client status (for monitoring/API).
        
        Returns:
            Dict with token validity, last error, request count
        """
        from datetime import datetime
        
        return {
            "token_valid": self._token_valid,
            "token_set": bool(self.token),
            "last_error": self._last_error,
            "last_error_time": self._last_error_time.isoformat() if self._last_error_time else None,
            "request_count": self._request_count,
            "needs_refresh": not self._token_valid
        }
    
    def _mark_token_invalid(self, error_message: str):
        """Mark token as invalid (called on 401 error)."""
        from datetime import datetime
        
        self._token_valid = False
        self._last_error = error_message
        self._last_error_time = datetime.now()
        logger.warning(f"Token marked invalid: {error_message}")
    async def _fetch(self, url: str, params: Dict[str, Any], retries: int = 2) -> Optional[Dict[str, Any]]:
        """Fetch with retry logic and exponential backoff."""
        if not self.token:
            logger.error("Cannot fetch: Token missing.")
            return None
        
        import asyncio
        self._request_count += 1
        
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        self._token_valid = True  # Token is working
                        return response.json()
                    elif response.status_code == 401:
                        # Token expired - mark invalid and return None
                        error_msg = response.text[:200]
                        self._mark_token_invalid(f"401 Unauthorized: {error_msg}")
                        return None
                    elif response.status_code == 429:  # Rate limited
                        wait_time = (attempt + 1) * 1.0  # 1s, 2s, 3s
                        logger.warning(f"Stockbit rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Stockbit Error {response.status_code}: {response.text[:100]}")
                        return None
            except Exception as e:
                if attempt < retries:
                    wait_time = (attempt + 1) * 0.5  # 0.5s, 1s
                    logger.warning(f"Stockbit connection retry {attempt+1}/{retries}: {str(e)[:50]}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Stockbit Connection Error after {retries} retries: {e}")
                    return None
        return None
    async def get_running_trade(self, symbol: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """
        Get running trade data. 
        Note: Broker codes are typically hidden (empty string) in real-time response.
        """
        url = f"{self.BASE_URL}/order-trade/running-trade"
        params = {
            "sort": "DESC",
            "limit": limit,
            "order_by": "RUNNING_TRADE_ORDER_BY_TIME",
            "symbols[]": symbol
        }
        
        return await self._fetch(url, params)

    async def get_brokers(self) -> List[str]:
        """Fetch list of all available broker codes."""
        url = f"{self.BASE_URL}/findata-view/marketdetectors/brokers"
        params = {"page": 1, "limit": 150, "group": "GROUP_UNSPECIFIED"}
        
        data = await self._fetch(url, params)
        if data and 'data' in data:
            return [b['code'] for b in data['data']]
        return []

    # ========================================
    # NEW: REAL DATA ENDPOINTS (2026-01-13)
    # ========================================

    async def get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get REAL orderbook data (bid/ask levels).
        
        Returns:
            - bid: list of {price, volume} 
            - offer: list of {price, volume}
            - lastprice, high, low, open, close
            - foreign/domestic breakdown
            - ara/arb (auto reject limits)
        """
        url = f"{self.BASE_URL}/company-price-feed/v2/orderbook/companies/{symbol}"
        params = {"with_full_price_tick": "false"}
        
        data = await self._fetch(url, params)
        if not data or 'data' not in data:
            return None
            
        d = data['data']
        return {
            "symbol": symbol,
            "lastprice": d.get('lastprice', 0),
            "open": d.get('open', 0),
            "high": d.get('high', 0),
            "low": d.get('low', 0),
            "close": d.get('close', 0),
            "previous": d.get('previous', 0),
            "change": d.get('change', 0),
            "percentage_change": d.get('percentage_change', 0),
            "volume": d.get('volume', 0),
            "value": d.get('value', 0),
            "frequency": d.get('frequency', 0),
            "foreign_buy": d.get('fbuy', 0),
            "foreign_sell": d.get('fsell', 0),
            "foreign_net": d.get('fnet', 0),
            "ara": d.get('ara', 0),
            "arb": d.get('arb', 0),
            "bid": d.get('bid', []),  # List of {price, volume}
            "offer": d.get('offer', []),  # List of {price, volume}
            "total_bid_offer": d.get('total_bid_offer', {}),
            "status": d.get('status', 'unknown'),
            "source": "stockbit"
        }

    async def get_running_trade_chart(self, symbol: str, period: str = "RT_PERIOD_LAST_1_DAY") -> Optional[Dict[str, Any]]:
        """
        Get running trade chart data (broker activity over time).
        
        Args:
            period: RT_PERIOD_LAST_1_DAY, RT_PERIOD_LAST_7_DAYS, RT_PERIOD_LAST_1_MONTH, RT_PERIOD_LAST_1_YEAR
        
        Returns:
            - price_chart_data: price movement
            - broker_chart_data: broker buy/sell activity
        """
        url = f"{self.BASE_URL}/order-trade/running-trade/chart/{symbol}"
        params = {"period": period}
        
        data = await self._fetch(url, params)
        if not data or 'data' not in data:
            return None
            
        d = data['data']
        return {
            "symbol": symbol,
            "from": d.get('from'),
            "to": d.get('to'),
            "price_chart": d.get('price_chart_data', []),
            "broker_chart": d.get('broker_chart_data', []),
            "source": "stockbit"
        }

    async def get_foreign_domestic_flow(self, symbol: str, period: str = "PERIOD_RANGE_1D") -> Optional[Dict[str, Any]]:
        """
        Get foreign vs domestic flow data.
        
        Args:
            period: PERIOD_RANGE_1D, PERIOD_RANGE_1W, etc.
        
        Returns:
            - summary: net foreign/domestic
            - value: time series of flows
        """
        url = f"{self.BASE_URL}/findata-view/foreign-domestic/v1/chart-data/{symbol}"
        params = {"market_type": "MARKET_TYPE_REGULAR", "period": period}
        
        data = await self._fetch(url, params)
        if not data or 'data' not in data:
            return None
            
        d = data['data']
        return {
            "symbol": symbol,
            "summary": d.get('summary', {}),
            "value": d.get('value', []),
            "volume": d.get('volume', []),
            "frequency": d.get('frequency', []),
            "from": d.get('from'),
            "to": d.get('to'),
            "source": "stockbit"
        }

    async def get_historical_summary(self, symbol: str, days: int = 30) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical OHLCV summary (faster than yfinance for IDX).
        
        Returns:
            List of daily data with open, high, low, close, volume, value
        """
        from datetime import datetime, timedelta
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        url = f"{self.BASE_URL}/company-price-feed/historical/summary/{symbol}"
        params = {
            "period": "HS_PERIOD_DAILY",
            "start_date": start_date,
            "end_date": end_date,
            "limit": days,
            "page": 1
        }
        
        data = await self._fetch(url, params)
        if not data or 'data' not in data:
            return None
            
        result = data['data'].get('result', [])
        return [{
            "date": r.get('date'),
            "open": r.get('open', 0),
            "high": r.get('high', 0),
            "low": r.get('low', 0),
            "close": r.get('close', 0),
            "volume": r.get('volume', 0),
            "value": r.get('value', 0),
            # FIXED: Correct keys from Stockbit API
            "foreign_buy": r.get('foreign_buy', 0),
            "foreign_sell": r.get('foreign_sell', 0),
            "net_foreign": r.get('net_foreign', 0)
        } for r in result]

    async def get_emiten_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get company/emiten information.
        
        Returns:
            - name, sector, sub_sector
            - sentiment, indexes
            - price info
        """
        url = f"{self.BASE_URL}/emitten/{symbol}/info"
        params = {}
        
        data = await self._fetch(url, params)
        if not data or 'data' not in data:
            return None
            
        d = data['data']
        return {
            "symbol": symbol,
            "name": d.get('name', symbol),
            "sector": d.get('sector', 'Unknown'),
            "sub_sector": d.get('sub_sector', ''),
            "sentiment": d.get('sentiment', {}),
            "indexes": d.get('indexes', []),
            "price": d.get('price', 0),
            "volume": d.get('volume', 0),
            "value": d.get('value', 0),
            "source": "stockbit"
        }

    async def get_bandarmology(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[Dict[str, Any]]:
        """
        Get complete Bandarmology data (Detector + Broker Summary).
        Uses 'marketdetectors' endpoint (The "Holy Grail").
        
        Args:
            symbol: Ticker symbol (e.g. BBCA)
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
        """
        url = f"{self.BASE_URL}/marketdetectors/{symbol}"
        params = {
            "transaction_type": "TRANSACTION_TYPE_NET",
            "market_board": "MARKET_BOARD_REGULER",
            "investor_type": "INVESTOR_TYPE_ALL",
            "limit": 25 # Top 25 brokers is enough
        }
        
        if start_date:
            params["from"] = start_date
        
        if end_date:
            params["to"] = end_date
            
        # Default to today only if no date provided? 
        # Actually Stockbit defaults to today if omitted, which is fine.
        
        try:
            data = await self._fetch(url, params)
            if not data or 'data' not in data:
                return None
                
            bd = data['data'].get('bandar_detector', {})
            bs = data['data'].get('broker_summary', {})
            
            # Calculate Totals from the list (since Stockbit doesn't provide raw totals in summary)
            brokers_buy = bs.get('brokers_buy', [])
            brokers_sell = bs.get('brokers_sell', [])
            
            total_buy_val = sum(float(b.get('bval', 0)) for b in brokers_buy)
            total_sell_val = sum(abs(float(b.get('sval', 0))) for b in brokers_sell)
            
            # Helper using Module Level Constants
            def get_broker_info(code):
                name = code
                if code in RETAIL_BROKERS: name = RETAIL_BROKERS[code]
                elif code in FOREIGN_BROKER_MAP: name = FOREIGN_BROKER_MAP[code]
                elif code in INST_BROKERS: name = INST_BROKERS[code]
                
                category = get_broker_category(code)
                return {"code": code, "name": name, "category": category}

            # ----------------------------------------------------
            # AGGREGATE FLOWS (Institutional, Retail, Foreign)
            # ----------------------------------------------------
            flows = {
                "Foreign": {"buy": 0.0, "sell": 0.0},
                "Retail": {"buy": 0.0, "sell": 0.0},
                "Inst": {"buy": 0.0, "sell": 0.0}
            }
            
            # Process Buyers
            for b in brokers_buy:
                 info = get_broker_info(b['netbs_broker_code'])
                 cat = info['category']
                 flows[cat]["buy"] += float(b['bval'])

            # Process Sellers
            for s in brokers_sell:
                 info = get_broker_info(s['netbs_broker_code'])
                 cat = info['category']
                 flows[cat]["sell"] += abs(float(s['sval']))

            # Calculate Net Flows
            inst_net = flows["Inst"]["buy"] - flows["Inst"]["sell"]
            retail_net = flows["Retail"]["buy"] - flows["Retail"]["sell"]
            foreign_net = flows["Foreign"]["buy"] - flows["Foreign"]["sell"]

            # Calculate Concentration Ratio (Top 5 Value / Total Value)
            # Using Top 5 buyers + Top 5 sellers
            top5_buy_val = sum(float(b.get('bval', 0)) for b in brokers_buy[:5])
            top5_sell_val = sum(abs(float(b.get('sval', 0))) for b in brokers_sell[:5])
            
            total_txn_value = total_buy_val + total_sell_val
            concentration_ratio = 0
            if total_txn_value > 0:
                concentration_ratio = ((top5_buy_val + top5_sell_val) / total_txn_value) * 100

            # Normalize response to match our internal metrics
            return {
                "top1_status": bd.get('top1', {}).get('accdist', 'NEUTRAL'),
                "top3_status": bd.get('top3', {}).get('accdist', 'NEUTRAL'),
                "top5_status": bd.get('top5', {}).get('accdist', 'NEUTRAL'),
                "avg5_status": bd.get('avg5', {}).get('accdist', 'NEUTRAL'),
                "top1_amount": bd.get('top1', {}).get('amount', 0),
                "total_buyer": bd.get('total_buyer', 0),
                "total_seller": bd.get('total_seller', 0),
                "buy_value": total_buy_val,
                "sell_value": total_sell_val,
                "net_value": total_buy_val - total_sell_val, 
                
                # New Aggregated Metrics for Frontend
                "institutional_net_flow": inst_net,
                "retail_net_flow": retail_net,
                "foreign_net_flow": foreign_net,
                "concentration_ratio": concentration_ratio,
                
                "top_buyers": [
                    {
                        **get_broker_info(b['netbs_broker_code']), 
                        "val": float(b['bval']), # Backward Compatibility for Aggregator
                        "value": float(b['bval']), # Frontend needs 'value'
                        "volume": float(b.get('bvolume', 0)),
                        "type": "INSTITUTION" if get_broker_category(b['netbs_broker_code']) == "Inst" else get_broker_category(b['netbs_broker_code']).upper(),
                        "is_foreign": get_broker_category(b['netbs_broker_code']) == "Foreign"
                    } 
                    for b in brokers_buy
                ],
                "top_sellers": [
                    {
                        **get_broker_info(b['netbs_broker_code']), 
                        "val": abs(float(b['sval'])), # Backward Compatibility for Aggregator
                        "value": abs(float(b['sval'])), # Frontend needs 'value' (positive)
                        "volume": float(b.get('svolume', 0)),
                        "type": "INSTITUTION" if get_broker_category(b['netbs_broker_code']) == "Inst" else get_broker_category(b['netbs_broker_code']).upper(),
                        "is_foreign": get_broker_category(b['netbs_broker_code']) == "Foreign"
                    } 
                    for b in brokers_sell
                ]
            }
            
        except Exception as e:
            logger.error(f"Bandarmology fetch error for {symbol}: {e}")
            return None

    # ========================================
    # FINANCIAL DATA METHODS
    # ========================================
    
    # Fundachart Item IDs for key financial metrics
    # Found via Stockbit fundachart exploration
    FUNDACHART_ITEMS = {
        # Size
        'market_cap': 2892,
        'enterprise_value': 2895,
        'shares_outstanding': 2899,
        # Valuation
        'price': 2661,
        # Valuation Ratios (Quarterly) - from Stockbit Key Ratio section
        'pe_ratio': 2904,  # PE Ratio (Quarter)
        'pb_ratio': 2903,  # PB Ratio (Quarter) 
        'ps_ratio': 2902,  # Price to Sales (Quarter)
        'eps': 2901,       # EPS (Quarter)
        # Dividend
        'dividend': 2913,
        'dividend_yield': 2915,
        'payout_ratio': 2916,
        # Income Statement
        'revenue': 31,
        'cogs': 32,
        'gross_profit': 33,
        'operating_expense': 34,
        'operating_income': 35,
        'net_income': 54,  # Net Income (TTM)
        'ebitda': 2917,    # EBITDA (Quarter)
        # Profitability
        'gross_margin': 12,
        'operating_margin': 13,
        'net_margin': 14,
        'roe': 15,         # Return on Equity
        'roa': 16,         # Return on Assets
        # Balance Sheet
        'cash': 3068,
        'receivables': 3069,
        'inventory': 3071,
        'book_value': 3080,  # Book Value per Share
        # Solvency (Quarterly)
        'current_ratio': 1498,
        'quick_ratio': 1500,
        'debt_to_equity': 1508,
        # Cash Flow
        'operating_cashflow': 2525,
        'fcf': 2545,
    }

    async def get_fundachart(self, symbol: str, item_id: int, timeframe: str = "5y") -> Optional[Dict[str, Any]]:
        """
        Fetch fundachart data for a specific metric.
        
        Args:
            symbol: Stock ticker (e.g., 'BBCA')
            item_id: Fundachart item ID (use FUNDACHART_ITEMS constants)
            timeframe: '1y', '3y', '5y', 'max'
            
        Returns:
            Dict with chart_data containing historical values
        """
        url = f"{self.BASE_URL}/fundachart"
        params = {
            'item': item_id,
            'companies': symbol,
            'timeframe': timeframe
        }
        
        data = await self._fetch(url, params)
        if data and 'data' in data and len(data['data']) > 0:
            company_data = data['data'][0]
            if company_data.get('ratios'):
                return company_data['ratios'][0]
        return None

    async def get_financial_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive financial data for Alpha-V Score calculation.
        This replaces manual financial report uploads!
        
        Returns:
            Dict containing all metrics needed for Alpha-V:
            - Valuation: market_cap, enterprise_value, price
            - Solvency: current_ratio, quick_ratio, debt_to_equity
            - Cash Flow: operating_cashflow, fcf
            - Profitability: net_margin, operating_margin, gross_margin
        """
        import asyncio
        
        try:
            result = {
                'symbol': symbol,
                'source': 'stockbit',
                'metrics': {}
            }
            
            # All metrics to fetch for Alpha-V Score
            alpha_v_metrics = [
                # Valuation Ratios (NEW!)
                'pe_ratio', 'pb_ratio', 'ps_ratio', 'eps',
                # Size
                'market_cap', 'enterprise_value', 'price', 'shares_outstanding',
                # Solvency
                'current_ratio', 'quick_ratio', 'debt_to_equity',
                # Cash Flow
                'operating_cashflow', 'fcf',
                # Profitability
                'net_margin', 'operating_margin', 'gross_margin', 'roe', 'roa',
                # Income Statement
                'revenue', 'gross_profit', 'operating_income', 'net_income', 'ebitda',
                # Dividend
                'dividend_yield', 'payout_ratio',
            ]
            
            async def fetch_metric(metric_name):
                item_id = self.FUNDACHART_ITEMS.get(metric_name)
                if not item_id:
                    return None
                chart = await self.get_fundachart(symbol, item_id, '1y')
                if chart and chart.get('chart_data'):
                    latest = chart['chart_data'][-1]
                    return (metric_name, {
                        'value': latest.get('value'),
                        'date': latest.get('formated_date'),
                        'item_name': chart.get('item_name')
                    })
                return None
            
            # Execute all requests in parallel (batch of 5 to avoid rate limits)
            all_results = []
            batch_size = 5
            for i in range(0, len(alpha_v_metrics), batch_size):
                batch = alpha_v_metrics[i:i+batch_size]
                batch_results = await asyncio.gather(
                    *[fetch_metric(m) for m in batch], 
                    return_exceptions=True
                )
                all_results.extend(batch_results)
                # Small delay between batches
                if i + batch_size < len(alpha_v_metrics):
                    await asyncio.sleep(0.2)
            
            for r in all_results:
                if r and not isinstance(r, Exception):
                    result['metrics'][r[0]] = r[1]
            
            # Calculate derived metrics if base data available
            metrics = result['metrics']
            
            # Calculate OCF/Net Income ratio if we have OCF
            if metrics.get('operating_cashflow') and metrics.get('net_margin'):
                ocf = metrics['operating_cashflow'].get('value')
                if ocf and metrics.get('revenue'):
                    rev = metrics['revenue'].get('value')
                    net_m = metrics['net_margin'].get('value')
                    if rev and net_m:
                        net_income = rev * (net_m / 100)
                        if net_income != 0:
                            result['metrics']['ocf_to_net_income'] = {
                                'value': ocf / net_income,
                                'calculated': True
                            }
            
            return result if result['metrics'] else None
            
        except Exception as e:
            logger.error(f"Financial data fetch error for {symbol}: {e}")
            return None
    
    async def get_financial_data_with_fallback(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get financial data formatted for FinancialReportData model.
        Ready to be used directly in Alpha-V Score calculation.
        Uses cached fundachart data if possible + on-demand key ratios
        """
        from datetime import datetime
        
        raw_data = await self.get_financial_data(symbol)
        if not raw_data or not raw_data.get('metrics'):
            return None
        
        m = raw_data['metrics']
        
        def get_val(key):
            if key in m and m[key]:
                return m[key].get('value')
            return None
        
        # Get current price for valuation ratios
        current_price = get_val('price') or 0
        market_cap = get_val('market_cap')
        enterprise_value = get_val('enterprise_value')
        
        # Get valuation ratios directly from fundachart (NEW!)
        per = get_val('pe_ratio')
        pbv = get_val('pb_ratio')
        roe = get_val('roe')
        roa = get_val('roa')
        ebitda = get_val('ebitda')
        net_income_direct = get_val('net_income')
        
        # Fallback to Key Ratios from HTML if fundachart doesn't have valuation ratios
        if not per or not pbv:
            try:
                key_ratios = await self.get_key_ratios(symbol)
                if key_ratios:
                    if not per and key_ratios.get('per'): 
                        per = key_ratios.get('per')
                    
                    if not pbv and key_ratios.get('pbv'):
                        pbv = key_ratios.get('pbv')
                        
                    if not roe and key_ratios.get('roe'):
                        roe = key_ratios.get('roe')
                    
                    if not roa and key_ratios.get('roa'):
                        roa = key_ratios.get('roa')
                        
                    if not ebitda and key_ratios.get('ebitda'):
                        ebitda = key_ratios.get('ebitda')
                        
                    logger.info(f"Retrieved Key Ratios fallback for {symbol}: PER={per}, PBV={pbv}, ROE={roe}")
            except Exception as e:
                logger.warning(f"Key Ratios fallback failed for {symbol}: {e}")
        
        # Calculate EV/EBITDA if we have both
        ev_ebitda = None
        if enterprise_value and ebitda and ebitda != 0:
            ev_ebitda = enterprise_value / ebitda
        
        # Build FinancialReportData compatible dict
        result = {
            'ticker': symbol,
            'period': f"Q4 {datetime.now().year}",  # Assume latest
            'report_type': 'quarterly',
            'source': 'stockbit-auto',
            
            # Valuation (now from fundachart!)
            'per': per,
            'pbv': pbv,
            'ev_ebitda': ev_ebitda,
            'pcf': None,  # Will calculate below
            
            # Profitability
            'roe': roe,
            'roa': roa,
            'npm': get_val('net_margin'),
            'opm': get_val('operating_margin'),
            
            # Cash Flow
            'ocf': get_val('operating_cashflow'),
            
            # Solvency
            'der': get_val('debt_to_equity'),
            'current_ratio': get_val('current_ratio'),
            'quick_ratio': get_val('quick_ratio'),
            
            # Raw values for calculations
            'market_cap': market_cap,
            'enterprise_value': enterprise_value,
            'ebitda': ebitda,
            'revenue': get_val('revenue'),
            'gross_profit': get_val('gross_profit'),
            'operating_income': get_val('operating_income'),
            'fcf': get_val('fcf'),
            'dividend_yield': get_val('dividend_yield'),
        }
        
        # Calculate PCF if we have market_cap and OCF
        if market_cap and result['ocf'] and result['ocf'] != 0:
            result['pcf'] = market_cap / result['ocf']
        
        # Get net income - prefer direct, else calculate from margin
        if net_income_direct:
            result['net_income'] = net_income_direct
        elif result['npm'] and result['revenue']:
            result['net_income'] = result['revenue'] * (result['npm'] / 100)
        
        # Calculate PER if not available from fundachart
        # PER = Market Cap / Annual Net Income
        if not per and market_cap and result.get('net_income') and result['net_income'] > 0:
            # Quarterly net income * 4 for annual estimate
            annual_net_income = result['net_income'] * 4
            result['per'] = market_cap / annual_net_income
            logger.info(f"Calculated PER for {symbol}: {result['per']:.2f}")
        
        # OCF to Net Income ratio
        if result.get('net_income') and result['net_income'] != 0 and result['ocf']:
            result['ocf_to_net_income'] = result['ocf'] / result['net_income']
        
        return result

    async def get_financial_report_data(self, symbol: str, report_type: int = 1, data_type: int = 1) -> Optional[Dict[str, Any]]:
        """
        Fetch financial statement data (Income Statement, Balance Sheet, Cash Flow).
        
        Args:
            symbol: Stock ticker
            report_type: 1=Income Statement, 2=Balance Sheet, 3=Cash Flow
            data_type: 1=Quarterly, 2=Yearly
            
        Returns:
            Dict with periods, accounts, and values
        """
        url = f"{self.BASE_URL}/findata-view/company/financial"
        params = {
            'symbol': symbol,
            'data_type': data_type,
            'report_type': report_type,
            'statement_type': 1
        }
        
        data = await self._fetch(url, params)
        if data and 'data' in data:
            return data['data']
        return None

    async def get_key_ratios(self, symbol: str, data_type: int = 1) -> Optional[Dict[str, Any]]:
        """
        Fetch Key Ratios (PER, PBV, ROE, EPS, etc.) from financial HTML report.
        
        Key Ratio table has id="data_table_keyratio_1" in the HTML response.
        
        Args:
            symbol: Stock ticker
            data_type: 1=Quarterly, 2=Yearly
            
        Returns:
            Dict with latest key ratios: per, pbv, roe, roa, eps, etc.
        """
        from bs4 import BeautifulSoup
        
        # Get Income Statement which contains Key Ratio table
        report = await self.get_financial_report_data(symbol, report_type=1, data_type=data_type)
        if not report or 'html_report' not in report:
            return None
        
        try:
            soup = BeautifulSoup(report['html_report'], 'html.parser')
            
            # Find Key Ratio table - it has id containing 'keyratio'
            keyratio_table = soup.find('table', id=lambda x: x and 'keyratio' in x.lower())
            if not keyratio_table:
                # Try finding div with keyratio id
                keyratio_div = soup.find('div', id='keyratio')
                if keyratio_div:
                    keyratio_table = keyratio_div.find('table')
            
            if not keyratio_table:
                logger.warning(f"Key Ratio table not found for {symbol}")
                return None
            
            ratios = {}
            ratio_mapping = {
                'pe ratio': 'per',
                'pb ratio': 'pbv',
                'price to book': 'pbv',
                'eps': 'eps',
                'roe': 'roe',
                'return on equity': 'roe',
                'roa': 'roa',
                'return on assets': 'roa',
                'price to sales': 'ps_ratio',
                'ebitda': 'ebitda',
                'net profit margin': 'npm',
                'operating profit margin': 'opm',
                'gross profit margin': 'gpm',
            }
            
            # Parse rows - Key Ratio table rows may not have 'dtr' class
            for row in keyratio_table.find_all('tr'):
                acc = row.find('span', class_='acc-name')
                if not acc:
                    continue
                    
                acc_name = (acc.get('data-lang-1', '') or acc.get_text(strip=True)).lower()
                
                # Find matching ratio
                matched_key = None
                for pattern, key in ratio_mapping.items():
                    if pattern in acc_name:
                        matched_key = key
                        break
                
                if not matched_key:
                    continue
                
                # Get latest value (last column) - Key Ratio uses 'row-ratio-val' class
                vals = row.find_all('td', class_='row-ratio-val')
                if not vals:
                    vals = row.find_all('td', class_='rowval')  # fallback
                if vals:
                    latest = vals[-1]
                    raw_val = latest.get('data-raw', latest.get('data-value-idr', ''))
                    try:
                        if raw_val and raw_val != '-':
                            ratios[matched_key] = float(raw_val)
                    except (ValueError, TypeError):
                        pass
            
            logger.info(f"Extracted Key Ratios for {symbol}: {list(ratios.keys())}")
            return ratios if ratios else None
            
        except Exception as e:
            logger.error(f"Error parsing Key Ratios for {symbol}: {e}")
            return None

    async def get_emiten_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get company information including sector, name, description."""
        url = f"{self.BASE_URL}/emitten/{symbol}/info"
        data = await self._fetch(url, {})
        if data and 'data' in data:
            return data['data']
        return None


# Global instance
stockbit_client = StockbitClient()

