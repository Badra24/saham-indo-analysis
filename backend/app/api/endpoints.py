"""
API Endpoints for Remora-Quant System

Provides endpoints for:
1. Stock analysis with AI consensus
2. Order flow analysis (OBI, HAKA/HAKI, Iceberg)
3. Trading signals (Looping strategy)
4. Risk management (Kill switch, position sizing)
5. WebSocket real-time updates
6. File upload for broker summary and financial reports (NEW)
7. Alpha-V Hybrid Scoring System (NEW)
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from app.models.schemas import (
    ConsensusResult, MarketData, BandarmologyData, 
    OrderFlowData, TradingSignal, RiskStatus
)
# from app.services.ai_clients import TriAIOrchestrator # Removed: Redundant
from app.services.msci_calc import calculate_fif_2025
from app.services.indicators import calculate_all_indicators, get_latest_indicators, get_indicator_signals
from app.services.bandarmology import analyze_broker_summary
from app.services.tick_size import normalize_price
from app.services.order_flow import SmartMoneyAnalyzer, create_analyzer
from app.services.simulated_orderbook import get_simulated_order_book, simulate_trade_for_ticker
from app.services.strategy import get_strategy, LoopingStrategy
from app.services.risk_manager import get_risk_manager, RiskManager
from app.services.file_upload_service import (
    handle_file_upload, validate_file_type, parse_broker_summary_csv, 
    parse_broker_summary_pdf, parse_financial_report
)
from app.services.alpha_v_scoring import (
    calculate_alpha_v_score, get_grade_color, get_grade_label
)
from app.models.file_models import (
    FileType, BrokerSummaryData, FinancialReportData, 
    AlphaVScore, FileUploadResponse
)

import yfinance as yf
import pandas as pd
import json
import time
import asyncio
import math
from typing import List, Dict, Optional


def sanitize_floats(obj):
    """
    Recursively sanitize float values in a dict/list to be JSON compliant.
    Replaces NaN, inf, -inf with None.
    """
    if isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj


router = APIRouter()
# orchestrator = TriAIOrchestrator() # Removed: Redundant

# Global analyzers cache
_analyzers: Dict[str, SmartMoneyAnalyzer] = {}

# Simple cache for chart data (5 minute TTL)
_chart_cache: Dict[str, dict] = {}
_cache_ttl = 300  # 5 minutes


def get_analyzer(ticker: str) -> SmartMoneyAnalyzer:
    """Get or create analyzer for a ticker"""
    if ticker not in _analyzers:
        _analyzers[ticker] = create_analyzer(depth=5)
    return _analyzers[ticker]


def get_cached_chart_data(ticker: str) -> dict:
    """Get cached chart data if still valid"""
    if ticker in _chart_cache:
        cached = _chart_cache[ticker]
        if time.time() - cached.get('cached_at', 0) < _cache_ttl:
            return cached
    return None


def set_chart_cache(ticker: str, data: dict):
    """Cache chart data"""
    data['cached_at'] = time.time()
    _chart_cache[ticker] = data


# Indonesian Stock Database (Top 50 IDX stocks)
IDX_STOCKS = [
    {"ticker": "BBCA", "name": "Bank Central Asia Tbk", "sector": "Banking"},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia Tbk", "sector": "Banking"},
    {"ticker": "BMRI", "name": "Bank Mandiri Tbk", "sector": "Banking"},
    {"ticker": "BBNI", "name": "Bank Negara Indonesia Tbk", "sector": "Banking"},
    {"ticker": "TLKM", "name": "Telkom Indonesia Tbk", "sector": "Telecom"},
    {"ticker": "ASII", "name": "Astra International Tbk", "sector": "Automotive"},
    {"ticker": "UNVR", "name": "Unilever Indonesia Tbk", "sector": "Consumer"},
    {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur Tbk", "sector": "Consumer"},
    {"ticker": "INDF", "name": "Indofood Sukses Makmur Tbk", "sector": "Consumer"},
    {"ticker": "KLBF", "name": "Kalbe Farma Tbk", "sector": "Healthcare"},
    {"ticker": "HMSP", "name": "HM Sampoerna Tbk", "sector": "Consumer"},
    {"ticker": "GGRM", "name": "Gudang Garam Tbk", "sector": "Consumer"},
    {"ticker": "ADRO", "name": "Adaro Energy Indonesia Tbk", "sector": "Mining"},
    {"ticker": "PTBA", "name": "Bukit Asam Tbk", "sector": "Mining"},
    {"ticker": "ANTM", "name": "Aneka Tambang Tbk", "sector": "Mining"},
    {"ticker": "INCO", "name": "Vale Indonesia Tbk", "sector": "Mining"},
    {"ticker": "MEDC", "name": "Medco Energi Internasional Tbk", "sector": "Energy"},
    {"ticker": "PGAS", "name": "Perusahaan Gas Negara Tbk", "sector": "Energy"},
    {"ticker": "EXCL", "name": "XL Axiata Tbk", "sector": "Telecom"},
    {"ticker": "ISAT", "name": "Indosat Ooredoo Hutchison Tbk", "sector": "Telecom"},
    {"ticker": "TOWR", "name": "Sarana Menara Nusantara Tbk", "sector": "Infrastructure"},
    {"ticker": "TBIG", "name": "Tower Bersama Infrastructure Tbk", "sector": "Infrastructure"},
    {"ticker": "SMGR", "name": "Semen Indonesia Tbk", "sector": "Basic Industry"},
    {"ticker": "INTP", "name": "Indocement Tunggal Prakarsa Tbk", "sector": "Basic Industry"},
    {"ticker": "CPIN", "name": "Charoen Pokphand Indonesia Tbk", "sector": "Consumer"},
    {"ticker": "JPFA", "name": "Japfa Comfeed Indonesia Tbk", "sector": "Consumer"},
    {"ticker": "BSDE", "name": "Bumi Serpong Damai Tbk", "sector": "Property"},
    {"ticker": "CTRA", "name": "Ciputra Development Tbk", "sector": "Property"},
    {"ticker": "SMRA", "name": "Summarecon Agung Tbk", "sector": "Property"},
    {"ticker": "PWON", "name": "Pakuwon Jati Tbk", "sector": "Property"},
    {"ticker": "ACES", "name": "Ace Hardware Indonesia Tbk", "sector": "Retail"},
    {"ticker": "MAPI", "name": "Mitra Adiperkasa Tbk", "sector": "Retail"},
    {"ticker": "ERAA", "name": "Erajaya Swasembada Tbk", "sector": "Retail"},
    {"ticker": "LPPF", "name": "Matahari Department Store Tbk", "sector": "Retail"},
    {"ticker": "MDKA", "name": "Merdeka Copper Gold Tbk", "sector": "Mining"},
    {"ticker": "BRPT", "name": "Barito Pacific Tbk", "sector": "Petrochemical"},
    {"ticker": "TPIA", "name": "Chandra Asri Petrochemical Tbk", "sector": "Petrochemical"},
    {"ticker": "AKRA", "name": "AKR Corporindo Tbk", "sector": "Trading"},
    {"ticker": "UNTR", "name": "United Tractors Tbk", "sector": "Automotive"},
    {"ticker": "MYOR", "name": "Mayora Indah Tbk", "sector": "Consumer"},
    {"ticker": "SIDO", "name": "Sido Muncul Tbk", "sector": "Consumer"},
    {"ticker": "ESSA", "name": "Surya Esa Perkasa Tbk", "sector": "Energy"},
    {"ticker": "ARTO", "name": "Bank Jago Tbk", "sector": "Banking"},
    {"ticker": "BRIS", "name": "Bank Syariah Indonesia Tbk", "sector": "Banking"},
    {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia Tbk", "sector": "Technology"},
    {"ticker": "BUKA", "name": "Bukalapak Tbk", "sector": "Technology"},
    {"ticker": "EMTK", "name": "Elang Mahkota Teknologi Tbk", "sector": "Technology"},
    {"ticker": "SCMA", "name": "Surya Citra Media Tbk", "sector": "Media"},
    {"ticker": "MNCN", "name": "MNC Vision Networks Tbk", "sector": "Media"},
]


@router.get("/search")
async def search_stocks(q: str = "", limit: int = 20):
    """
    Search Indonesian stocks by ticker or company name.
    
    Uses IDX Static Data as PRIMARY source (all 956 emitens).
    This includes stocks like BUMI that are missing from Yahoo Finance.
    
    Data Source:
    1. IDX Static Data - 956 companies from idx.co.id (primary)
    2. Yahoo Finance - Only as fallback validation
    
    Args:
        q: Search query (ticker or name)
        limit: Maximum results (default 20)
    """
    from app.services.idx_static_data import search_emitens, get_company_by_code
    
    # If no query, return popular stocks
    if not q:
        # Return first N companies from IDX
        results = search_emitens("", limit=0)  # Empty query returns nothing
        # Fallback to static top stocks
        popular = ["BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "ICBP", "KLBF", "ADRO", "ANTM"]
        results = []
        for code in popular[:limit]:
            company = get_company_by_code(code)
            if company:
                results.append(company)
        return {"results": results, "source": "idx", "total_available": 956}
    
    query = q.strip()
    
    # Use IDX Static Data for search (956 emitens)
    results = search_emitens(query, limit=limit)
    
    # If IDX found results, return them
    if results:
        return {
            "results": results,
            "source": "idx",
            "total_available": 956
        }
    
    # Fallback: If not found in IDX AND query looks like a ticker, try Yahoo Finance
    query_upper = query.upper()
    if 2 <= len(query_upper) <= 5:
        try:
            ticker_test = f"{query_upper}.JK"
            stock = yf.Ticker(ticker_test)
            info = stock.info
            
            # Check if valid stock (has symbol and regularMarketPrice)
            if info.get("symbol") and info.get("regularMarketPrice"):
                results.append({
                    "symbol": query_upper,
                    "name": info.get("longName") or info.get("shortName") or query_upper,
                    "sector": info.get("sector") or "Unknown",
                    "source": "yahoo"
                })
        except Exception as e:
            print(f"YF lookup failed for {query}: {e}")
    
    return {
        "results": results,
        "source": "idx" if results else "none",
        "total_available": 956
    }


# ========================================
# EXISTING ENDPOINTS (Enhanced)
# ========================================




# ========================================
# NEW ORDER FLOW ENDPOINTS
# ========================================

async def get_order_flow_internal(ticker: str, price: float) -> Dict:
    """Internal helper for order flow analysis"""
    # Get simulated order book
    order_book = get_simulated_order_book(ticker, price, depth=10)
    
    # Simulate a trade
    trade = simulate_trade_for_ticker(ticker)
    
    # Analyze with SmartMoneyAnalyzer
    analyzer = get_analyzer(ticker)
    
    if trade:
        result = analyzer.analyze(
            order_book,
            trade_price=trade['price'],
            trade_volume=trade['volume']
        )
    else:
        result = analyzer.analyze(order_book)
    

    # Format order book for frontend (include cumulative totals)
    formatted_bids = []
    total_bid = 0
    for bid in order_book.bids:
        total_bid += bid.volume
        formatted_bids.append({
            "price": bid.price,
            "volume": bid.volume,
            "total": total_bid
        })
        
    formatted_asks = []
    total_ask = 0
    for ask in order_book.asks:
        total_ask += ask.volume
        formatted_asks.append({
            "price": ask.price,
            "volume": ask.volume,
            "total": total_ask
        })
    
    best_bid = order_book.bids[0].price if order_book.bids else 0
    best_ask = order_book.asks[0].price if order_book.asks else 0
    spread = best_ask - best_bid if best_ask and best_bid else 0
    spread_percent = (spread / best_ask * 100) if best_ask else 0
    
    result['order_book'] = {
        "bids": formatted_bids,
        "asks": formatted_asks,
        "lastPrice": order_book.last_price,
        "spread": spread,
        "spreadPercent": round(spread_percent, 2),
        "imbalance": result.get('obi', 0)
    }
    
    return result


@router.get("/orderflow/{ticker}", response_model=OrderFlowData)
async def get_order_flow(ticker: str):
    """
    Real-time Order Flow Analysis
    
    Returns:
    - OBI (Order Book Imbalance): -1.0 to 1.0
    - HAKA/HAKI volumes and net flow
    - Iceberg detection results
    - Institutional support/resistance levels
    - Trading signal (ACCUMULATION, DISTRIBUTION, etc.)
    """
    try:
        formatted_ticker = ticker.upper()
        if not formatted_ticker.endswith(".JK"):
            formatted_ticker += ".JK"
        
        # Get current price
        stock = yf.Ticker(formatted_ticker)
        price = stock.fast_info.last_price
        
        if not price:
            raise HTTPException(status_code=404, detail="Ticker not found")
        
        result = await get_order_flow_internal(formatted_ticker, price)
        
        return OrderFlowData(**result)
        
    except Exception as e:
        print(f"Error in order flow for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bandarmology/{ticker}")
async def get_bandarmology(ticker: str, date: str = None, force_refresh: bool = False, use_browser: bool = True):
    """
    Get Bandarmology (Broker Summary) Analysis
    
    Uses HYBRID approach:
    1. IDX Browser (Primary) - No rate limits, real-time from idx.co.id
    2. GoAPI (Fallback) - When browser fails (30/day, 500/month limits)
    
    Query params:
    - date: Optional date in YYYY-MM-DD format
    - force_refresh: Skip cache and fetch fresh data
    - use_browser: Try IDX Browser first (default: True, set False to force GoAPI)
    """
    from app.services.idx_broker_aggregator import get_broker_aggregator
    from app.services.mock_data_generator import mock_generator
    
    try:
        formatted_ticker = ticker.upper().replace(".JK", "")
        
        # ========================================
        # DIRECT STOCKBIT FETCH (No DuckDB Cache)
        # Reason: Real-time data, caching causes locks
        # ========================================
        # DIRECT STOCKBIT FETCH (No DuckDB Cache)
        # Reason: Real-time data, caching causes locks
        # Use stockbit_client DIRECTLY to preserve rich keys (name, type, is_foreign)
        # which aggregator was stripping out.
        # ========================================
        from app.services.stockbit_client import stockbit_client
        result = await stockbit_client.get_bandarmology(formatted_ticker)
        
        # Fallback to Mock Data only if Stockbit completely fails
        if result.get("source") in ["error", "stockbit_error"] or result.get("status") == "DATA_UNAVAILABLE":
            print(f"[FALLBACK] Stockbit failed for {ticker}. Using Mock Data.")
            mock_days = mock_generator.generate_mock_history(formatted_ticker, days=1)
            if mock_days:
                result = mock_days[-1]
                result["source"] = "mock_fallback"
        
        result["from_cache"] = False
        
        # Enrich with Advanced Metrics (Gap Analysis Phase 2)
        from app.services.bandarmology import bandarmology_engine
        from app.services.wyckoff_detector import get_wyckoff_detector
        
        try:
            hhi_data = bandarmology_engine.calculate_hhi(result)
            vwap_data = bandarmology_engine.calculate_bandar_vwap(result)
            
            result['hhi'] = hhi_data
            result['bandar_vwap'] = vwap_data.get('bandar_vwap', 0)
            
            # Wyckoff Detection (Requires Price History)
            # Fetch last 90 days for pattern recognition
            hist_summary = await stockbit_client.get_historical_summary(formatted_ticker, days=90)
            if hist_summary:
                detector = get_wyckoff_detector()
                wyckoff_res = detector.detect(hist_summary, result)
                if wyckoff_res and wyckoff_res.pattern.value != "None":
                     result['wyckoff'] = {
                         "pattern": wyckoff_res.pattern.value,
                         "action": wyckoff_res.action,
                         "confidence": wyckoff_res.confidence
                     }
        except Exception as calc_err:
            print(f"Error calculating advanced metrics: {calc_err}")
            
        return result
        
    except Exception as e:
        print(f"Error getting bandarmology for {ticker}: {e}")
        # Return default/empty data instead of 500 to keep UI working
        return {
            "status": "NEUTRAL",
            "signal_strength": 0,
            "top_buyers": [],
            "top_sellers": [],
            "concentration_ratio": 0.0,
            "dominant_player": "RETAIL",
            "institutional_net_flow": 0,
            "retail_net_flow": 0,
            "foreign_net_flow": 0,
            "buy_value": 0,
            "sell_value": 0,
            "net_flow": 0,
            "churn_detected": False,
            "churning_brokers": [],
            "is_demo": False,
            "source": "error"
        }


@router.get("/broker/{broker_code}/history/{ticker}")
async def get_broker_history(broker_code: str, ticker: str, days: int = 30):
    """
    Get broker activity history for a specific stock.
    
    Returns:
    - 30-day activity data with buy/sell values
    - Running position calculation
    - Trend analysis (AKUMULASI_AKTIF, DISTRIBUSI_AKTIF, etc.)
    - Daily activity breakdown
    
    Query params:
    - days: Number of days to analyze (default: 30, max: 60)
    """
    # from app.services.goapi_client import get_goapi_client # DELETED
    
    # Limit days to prevent API abuse
    days = min(days, 60)
    
    from app.services.idx_broker_aggregator import get_broker_aggregator
    agg = get_broker_aggregator()
    
    return await agg.get_broker_history(ticker, broker_code, days)
    
    # Old placeholder code removed below


# ========================================
# NEW: STOCKBIT REAL DATA ENDPOINTS
# ========================================

@router.get("/stockbit/orderbook/{ticker}")
async def get_stockbit_orderbook(ticker: str):
    """
    Get REAL orderbook (bid/ask) data from Stockbit.
    
    Returns:
    - bid/offer levels with price and volume
    - lastprice, high, low, open, close
    - foreign/domestic breakdown
    - ARA/ARB limits
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    result = await stockbit_client.get_orderbook(formatted_ticker)
    
    if not result:
        return {"error": "Data unavailable", "source": "stockbit_error"}
    
    return result


@router.get("/stockbit/foreignflow/{ticker}")
async def get_stockbit_foreignflow(ticker: str, period: str = "PERIOD_RANGE_1D"):
    """
    Get foreign vs domestic flow data from Stockbit.
    
    Query params:
    - period: PERIOD_RANGE_1D, PERIOD_RANGE_1W, etc.
    
    Returns:
    - summary: net foreign/domestic totals
    - value: time series of flows
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    # Use the comprehensive get_bandarmology method which returns summaries and flows
    result = await stockbit_client.get_bandarmology(formatted_ticker)
    
    if not result:
        return {"error": "Data unavailable", "source": "stockbit_error"}
    
    return result


@router.get("/stockbit/emiten/{ticker}")
async def get_stockbit_emiten(ticker: str):
    """
    Get company/emiten information from Stockbit.
    
    Returns:
    - name, sector, sub_sector
    - sentiment, indexes
    - price info
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    result = await stockbit_client.get_emiten_info(formatted_ticker)
    
    if not result:
        return {"error": "Data unavailable", "source": "stockbit_error"}
    
    return result


@router.get("/stockbit/runningtrade/{ticker}")
async def get_stockbit_running_trade(ticker: str, limit: int = 50):
    """
    Get real-time running trade data from Stockbit.
    
    Returns:
    - List of recent trades with price, volume, time
    - is_open_market status
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    result = await stockbit_client.get_running_trade(formatted_ticker, limit)
    
    if not result:
        return {"error": "Data unavailable", "source": "stockbit_error"}
    
    return result


# ========================================
# STOCKBIT FINANCIAL DATA ENDPOINTS
# ========================================

@router.get("/stockbit/financial/{ticker}")
async def get_stockbit_financial(ticker: str):
    """
    Get financial data from Stockbit.
    Returns key financial metrics (market_cap, dividend_yield, price, etc.)
    This endpoint can replace manual financial report uploads!
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    result = await stockbit_client.get_financial_data(formatted_ticker)
    
    if not result:
        db_result = db_service.get_financial_report(formatted_ticker)
        if db_result:
            return {"source": "duckdb_upload", "symbol": formatted_ticker, "metrics": db_result}
        return {"error": "Financial data unavailable", "source": "none"}
    
    return result


@router.get("/stockbit/fundachart/{ticker}/{metric}")
async def get_stockbit_fundachart(ticker: str, metric: str, timeframe: str = "5y"):
    """
    Get specific fundachart metric data.
    Metrics: market_cap, dividend_yield, revenue, current_ratio, debt_to_equity, etc.
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    item_id = stockbit_client.FUNDACHART_ITEMS.get(metric)
    if not item_id:
        return {"error": f"Unknown metric: {metric}", "available": list(stockbit_client.FUNDACHART_ITEMS.keys())}
    
    result = await stockbit_client.get_fundachart(formatted_ticker, item_id, timeframe)
    if not result:
        return {"error": "Data unavailable"}
    
    return {"symbol": formatted_ticker, "metric": metric, "timeframe": timeframe, "data": result}


@router.get("/stockbit/company/{ticker}")
async def get_stockbit_company(ticker: str):
    """Get company info from Stockbit (name, sector, description)."""
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    result = await stockbit_client.get_emiten_info(formatted_ticker)
    
    if not result:
        return {"error": "Company info unavailable"}
    
    return {"symbol": formatted_ticker, "source": "stockbit", "data": result}


# ========================================
# ANALYTICS ENDPOINTS (Trend & Heatmap)
# ========================================

@router.get("/analytics/trend/{ticker}")
async def get_analytics_trend(ticker: str, days: int = 30):
    """
    Get trend data for broker flow visualization.
    Uses Stockbit historical summary to generate foreign flow trend.
    
    Returns list of daily data with:
    - date, net_foreign (foreign_buy - foreign_sell), cumulative_flow
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    
    try:
        history = await stockbit_client.get_historical_summary(formatted_ticker, days=days)
        
        if not history:
            return []
        
        # Calculate trend data
        cumulative = 0
        trend_data = []
        
        for day in sorted(history, key=lambda x: x.get('date', '')):
            net_foreign = (day.get('foreign_buy', 0) or 0) - (day.get('foreign_sell', 0) or 0)
            cumulative += net_foreign
            
            trend_data.append({
                "date": day.get('date', ''),
                "net_foreign": net_foreign,
                "cumulative_flow": cumulative,
                "volume": day.get('volume', 0),
                "close": day.get('close', 0),
                "foreign_buy": day.get('foreign_buy', 0),
                "foreign_sell": day.get('foreign_sell', 0)
            })
        
        return trend_data
        
    except Exception as e:
        print(f"Error getting trend: {e}")
        return []

@router.get("/analytics/intraday-flow/{ticker}")
async def get_analytics_intraday_flow(ticker: str, days: int = 7):
    """
    Get Intraday Broker Flow (Retail vs Foreign vs Inst).
    Uses Stockbit Running Trade Chart data.
    """
    from app.services.stockbit_client import stockbit_client, get_broker_category
    from datetime import datetime
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    
    # Determine Period
    period = "RT_PERIOD_LAST_1_DAY"
    if days > 1: period = "RT_PERIOD_LAST_7_DAYS"
    if days > 7: period = "RT_PERIOD_LAST_1_MONTH"
    
    try:
        data = await stockbit_client.get_running_trade_chart(formatted_ticker, period=period)
        if not data or 'broker_chart' not in data:
            return []
            
        broker_chart = data['broker_chart']
        
        # We need to aggregate flows by timestamp
        # Structure: Map<Timestamp, {retail: 0, foreign: 0, inst: 0, price: 0}>
        time_map = {}
        
        # Process Broker Charts
        for bc in broker_chart:
            if bc.get('type') != 'TYPE_CHART_VALUE':
                continue
                
            charts = bc.get('charts', [])
            for c in charts:
                broker_code = c.get('broker_code')
                category = get_broker_category(broker_code)
                
                points = c.get('chart', [])
                for p in points:
                    # Key: date + time (e.g., "2026-01-07 09:00")
                    dt_key = f"{p.get('date')} {p.get('time')}"
                    
                    if dt_key not in time_map:
                        time_map[dt_key] = {
                            "date": dt_key, 
                            "retail_flow": 0.0, 
                            "foreign_flow": 0.0, 
                            "inst_flow": 0.0,
                            "price": 0.0 # Will fill later
                        }
                    
                    raw_val = float(p.get('value', {}).get('raw', 0))
                    
                    if category == "Retail":
                        time_map[dt_key]["retail_flow"] += raw_val
                    elif category == "Foreign":
                        time_map[dt_key]["foreign_flow"] += raw_val
                    elif category == "Inst":
                        time_map[dt_key]["inst_flow"] += raw_val

        # Fill Price Data (Optional, if we want price overlay)
        price_chart = data.get('price_chart', [])
        for p in price_chart:
             dt_key = f"{p.get('date')} {p.get('time')}"
             if dt_key in time_map:
                 time_map[dt_key]["price"] = float(p.get('value', {}).get('raw', 0))
        
        # Convert to List and Sort
        result = list(time_map.values())
        result.sort(key=lambda x: x['date'])
        
        return result
        
    except Exception as e:
        print(f"Error getting intraday flow: {e}")
        return []


@router.get("/analytics/heatmap/{ticker}")
async def get_analytics_heatmap(ticker: str, days: int = 30):
    """
    Get heatmap data for broker activity visualization.
    
    Returns list of daily data with activity intensity.
    """
    from app.services.stockbit_client import stockbit_client
    
    formatted_ticker = ticker.upper().replace(".JK", "")
    
    try:
        history = await stockbit_client.get_historical_summary(formatted_ticker, days=days)
        
        if not history:
            return []
        
        # Calculate average volume for normalization
        volumes = [d.get('volume', 0) or 0 for d in history]
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        
        heatmap_data = []
        for day in sorted(history, key=lambda x: x.get('date', '')):
            volume = day.get('volume', 0) or 0
            value = day.get('value', 0) or 0
            
            # Intensity: how much above/below average
            intensity = (volume / avg_volume) if avg_volume > 0 else 0
            
            # Determine activity type based on foreign flow
            net_foreign = (day.get('foreign_buy', 0) or 0) - (day.get('foreign_sell', 0) or 0)
            activity_type = "accumulation" if net_foreign > 0 else "distribution" if net_foreign < 0 else "neutral"
            
            heatmap_data.append({
                "date": day.get('date', ''),
                "intensity": round(intensity, 2),
                "volume": volume,
                "value": value,
                "activity_type": activity_type,
                "net_foreign": net_foreign
            })
        
        return heatmap_data
        
    except Exception as e:
        print(f"Heatmap fetch error: {e}")
        return []

@router.get("/indicators/{ticker}")
async def get_indicators(ticker: str, period: str = "1y"):
    """
    Get all technical indicators for a stock
    
    Returns RSI, VWAP, MACD-V, Bollinger Bands, ATR, volume analysis, historical prices,
    and indicator line data for chart overlay.
    
    Args:
        ticker: Stock symbol (e.g., BBCA)
        period: History period (1mo, 3mo, 6mo, 1y, 2y, 5y, max)
    
    Uses 5-minute cache for faster subsequent loads.
    """
    try:
        formatted_ticker = ticker.upper()
        if not formatted_ticker.endswith(".JK"):
            formatted_ticker += ".JK"
        
        # Validate period (to prevent injection)
        valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
        if period not in valid_periods:
            period = "1y"
        
        # Determine interval based on period
        interval = "1d"
        if period == "1d":
            interval = "5m"
        elif period == "5d":
            interval = "15m"
        elif period == "1mo":
            interval = "1h"
        
        # Check cache (include period in cache key)
        cache_key = f"{formatted_ticker}_{period}"
        cached = get_cached_chart_data(cache_key)
        if cached:
            print(f"Using cached data for {cache_key}")
            return cached
        
        print(f"Fetching fresh data for {formatted_ticker} (period={period}, interval={interval})...")
        stock = yf.Ticker(formatted_ticker)
        hist = stock.history(period=period, interval=interval)
        
        if hist.empty:
            raise HTTPException(status_code=404, detail="No data available")
        
        hist = calculate_all_indicators(hist)
        indicator_signals = get_indicator_signals(hist)
        
        # Format candles for chart
        candles = []
        # Format indicator lines for chart overlay
        indicator_lines = {
            # Moving Averages
            "ema9": [],
            "ema21": [],
            "ema55": [],
            "ema200": [],
            "sma50": [],
            "sma100": [],
            "sma200": [],
            # VWAP
            "vwap": [],
            # Bollinger Bands
            "bb_upper": [],
            "bb_middle": [],
            "bb_lower": [],
            # Stochastic (for separate pane)
            "stoch_k": [],
            "stoch_d": [],
            # CCI (for separate pane)
            "cci": [],
            # OBV (for separate pane)
            "obv": [],
            # RSI (for separate pane)
            "rsi": [],
            # Ichimoku
            "ichimoku_tenkan": [],
            "ichimoku_kijun": [],
            "ichimoku_span_a": [],
            "ichimoku_span_b": [],
            # Pivot Points
            "pivot": [],
            "pivot_r1": [],
            "pivot_r2": [],
            "pivot_s1": [],
            "pivot_s2": [],
            # MACD (Added)
            "macd": [],
            "macd_signal": [],
            "macd_hist": [],
            "macd_v": [],
            # Volume Anomaly (Added)
            "volume_anomaly": [],
            # VPVR (New!)
            "vpvr_poc": [],
            "vpvr_vah": [],
            "vpvr_val": [],
            # Fibonacci (static levels based on latest calculation)
            "fib_levels": {},
        }
        
        for index, row in hist.iterrows():
            ts = int(index.timestamp())
            candles.append({
                "time": ts,
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close'])
            })
            
            # Moving Averages
            if pd.notna(row.get('EMA_9')):
                indicator_lines["ema9"].append({"time": ts, "value": float(row['EMA_9'])})
            if pd.notna(row.get('EMA_21')):
                indicator_lines["ema21"].append({"time": ts, "value": float(row['EMA_21'])})
            if pd.notna(row.get('EMA_55')):
                indicator_lines["ema55"].append({"time": ts, "value": float(row['EMA_55'])})
            if pd.notna(row.get('EMA_200')):
                indicator_lines["ema200"].append({"time": ts, "value": float(row['EMA_200'])})
            if pd.notna(row.get('SMA_50')):
                indicator_lines["sma50"].append({"time": ts, "value": float(row['SMA_50'])})
            if pd.notna(row.get('SMA_100')):
                indicator_lines["sma100"].append({"time": ts, "value": float(row['SMA_100'])})
            if pd.notna(row.get('SMA_200')):
                indicator_lines["sma200"].append({"time": ts, "value": float(row['SMA_200'])})
            
            # MACD
            if pd.notna(row.get('MACD')):
                indicator_lines["macd"].append({"time": ts, "value": float(row['MACD'])})
            if pd.notna(row.get('MACD_Signal')):
                indicator_lines["macd_signal"].append({"time": ts, "value": float(row['MACD_Signal'])})
            if pd.notna(row.get('MACD_Histogram')):
                indicator_lines["macd_hist"].append({"time": ts, "value": float(row['MACD_Histogram'])})
            if pd.notna(row.get('MACD_V')):
                indicator_lines["macd_v"].append({"time": ts, "value": float(row['MACD_V'])})

            if pd.notna(row.get('Volume_Anomaly')):
                indicator_lines["volume_anomaly"].append({"time": ts, "value": 1 if row['Volume_Anomaly'] else 0})

            # VPVR
            if pd.notna(row.get('VPVR_POC')):
                indicator_lines["vpvr_poc"].append({"time": ts, "value": float(row['VPVR_POC'])})
            if pd.notna(row.get('VPVR_VAH')):
                indicator_lines["vpvr_vah"].append({"time": ts, "value": float(row['VPVR_VAH'])})
            if pd.notna(row.get('VPVR_VAL')):
                indicator_lines["vpvr_val"].append({"time": ts, "value": float(row['VPVR_VAL'])})

            # VWAP
            if pd.notna(row.get('VWAP')):
                indicator_lines["vwap"].append({"time": ts, "value": float(row['VWAP'])})
            
            # Bollinger Bands
            if pd.notna(row.get('BB_Upper')):
                indicator_lines["bb_upper"].append({"time": ts, "value": float(row['BB_Upper'])})
            if pd.notna(row.get('BB_Middle')):
                indicator_lines["bb_middle"].append({"time": ts, "value": float(row['BB_Middle'])})
            if pd.notna(row.get('BB_Lower')):
                indicator_lines["bb_lower"].append({"time": ts, "value": float(row['BB_Lower'])})
            
            # Stochastic
            if pd.notna(row.get('Stoch_K')):
                indicator_lines["stoch_k"].append({"time": ts, "value": float(row['Stoch_K'])})
            if pd.notna(row.get('Stoch_D')):
                indicator_lines["stoch_d"].append({"time": ts, "value": float(row['Stoch_D'])})
            
            # CCI
            if pd.notna(row.get('CCI')):
                indicator_lines["cci"].append({"time": ts, "value": float(row['CCI'])})
            
            # OBV (normalize for display)
            if pd.notna(row.get('OBV')):
                indicator_lines["obv"].append({"time": ts, "value": float(row['OBV'])})
            
            # RSI
            if pd.notna(row.get('RSI')):
                indicator_lines["rsi"].append({"time": ts, "value": float(row['RSI'])})
            
            # Ichimoku
            if pd.notna(row.get('Ichimoku_Tenkan')):
                indicator_lines["ichimoku_tenkan"].append({"time": ts, "value": float(row['Ichimoku_Tenkan'])})
            if pd.notna(row.get('Ichimoku_Kijun')):
                indicator_lines["ichimoku_kijun"].append({"time": ts, "value": float(row['Ichimoku_Kijun'])})
            if pd.notna(row.get('Ichimoku_SpanA')):
                indicator_lines["ichimoku_span_a"].append({"time": ts, "value": float(row['Ichimoku_SpanA'])})
            if pd.notna(row.get('Ichimoku_SpanB')):
                indicator_lines["ichimoku_span_b"].append({"time": ts, "value": float(row['Ichimoku_SpanB'])})
            
            # Pivot Points
            if pd.notna(row.get('Pivot')):
                indicator_lines["pivot"].append({"time": ts, "value": float(row['Pivot'])})
            if pd.notna(row.get('Pivot_R1')):
                indicator_lines["pivot_r1"].append({"time": ts, "value": float(row['Pivot_R1'])})
            if pd.notna(row.get('Pivot_R2')):
                indicator_lines["pivot_r2"].append({"time": ts, "value": float(row['Pivot_R2'])})
            if pd.notna(row.get('Pivot_S1')):
                indicator_lines["pivot_s1"].append({"time": ts, "value": float(row['Pivot_S1'])})
            if pd.notna(row.get('Pivot_S2')):
                indicator_lines["pivot_s2"].append({"time": ts, "value": float(row['Pivot_S2'])})
        
        # Add Fibonacci levels (static, based on last row)
        if not hist.empty:
            last_row = hist.iloc[-1]
            indicator_lines["fib_levels"] = {
                "fib_0": float(last_row.get('Fib_0', 0)),
                "fib_236": float(last_row.get('Fib_236', 0)),
                "fib_382": float(last_row.get('Fib_382', 0)),
                "fib_500": float(last_row.get('Fib_500', 0)),
                "fib_618": float(last_row.get('Fib_618', 0)),
                "fib_786": float(last_row.get('Fib_786', 0)),
                "fib_100": float(last_row.get('Fib_100', 0)),
            }
        

        
        result = {
            "ticker": formatted_ticker,
            "timestamp": int(time.time()),
            "historical_prices": candles,
            "indicator_lines": indicator_lines,

            **indicator_signals
        }
        
        # Sanitize NaN/inf values before caching and returning
        result = sanitize_floats(result)
        
        # Cache the result (use cache_key which includes period)
        set_chart_cache(cache_key, result.copy())
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# NEW STRATEGY ENDPOINTS
# ========================================

@router.get("/strategy/signal/{ticker}", response_model=TradingSignal)
async def get_trading_signal(ticker: str):
    """
    Get Looping Strategy Trading Signal
    
    Analyzes order flow and indicators to generate:
    - Action (BUY, SELL, HOLD, RE_ENTRY)
    - Position sizing (30-30-40 pyramiding)
    - Stop loss and take profit levels
    - Confidence score
    """
    try:
        formatted_ticker = ticker.upper()
        if not formatted_ticker.endswith(".JK"):
            formatted_ticker += ".JK"
        
        # Get price and indicators
        stock = yf.Ticker(formatted_ticker)
        price = stock.fast_info.last_price
        
        if not price:
            raise HTTPException(status_code=404, detail="Ticker not found")
        
        hist = stock.history(period="6mo")
        hist = calculate_all_indicators(hist)
        indicators = get_latest_indicators(hist) if not hist.empty else {}
        
        # Get order flow
        order_flow = await get_order_flow_internal(formatted_ticker, price)
        
        # Generate signal
        strategy = get_strategy()
        signal = strategy.analyze(
            ticker=formatted_ticker,
            current_price=price,
            order_flow_data=order_flow,
            indicators=indicators
        )
        
        return TradingSignal(**signal)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# NEW RISK MANAGEMENT ENDPOINTS
# ========================================

@router.get("/risk/status", response_model=RiskStatus)
async def get_risk_status():
    """
    Get current risk management status
    
    Returns:
    - Daily P&L and percentage
    - Kill switch status
    - Remaining risk budget
    - Current exposure
    - Max drawdown
    """
    try:
        risk_manager = get_risk_manager()
        status = risk_manager.get_status()
        return RiskStatus(**status)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/position-size")
async def calculate_position_size(ticker: str, price: float = None):
    """
    Calculate optimal position size based on volatility
    
    Uses ATR-based sizing for risk management.
    """
    try:
        formatted_ticker = ticker.upper()
        if not formatted_ticker.endswith(".JK"):
            formatted_ticker += ".JK"
        
        stock = yf.Ticker(formatted_ticker)
        
        if not price:
            price = stock.fast_info.last_price
            
        if not price:
            raise HTTPException(status_code=404, detail="Ticker not found")
        
        # Get ATR for volatility
        hist = stock.history(period="3mo")
        if hist.empty:
            raise HTTPException(status_code=404, detail="No historical data")
            
        hist = calculate_all_indicators(hist)
        atr = hist['ATR_14'].iloc[-1] if 'ATR_14' in hist.columns else price * 0.02
        
        # Calculate position size
        risk_manager = get_risk_manager()
        sizing = risk_manager.calculate_position_size(price, atr)
        
        return {
            "ticker": formatted_ticker,
            "price": price,
            "atr": float(atr),
            **sizing
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/kill-switch/reset")
async def reset_kill_switch():
    """
    Manually reset the kill switch
    
    ⚠️ Use with caution! Only reset after reviewing portfolio.
    """
    risk_manager = get_risk_manager()
    risk_manager.reset_kill_switch()
    
    return {
        "status": "success",
        "message": "Kill switch has been reset. Trade carefully.",
        "new_status": risk_manager.get_status()
    }


# ========================================
# MASSIVE SCREENER ENDPOINTS (Unified)
# ========================================

@router.get("/scanner/volume")
async def scan_volume_stocks(
    min_rvol: float = 1.5,
    min_value: float = 10,  # In billions (Miliar)
    limit: int = 20
):
    """
    Scan stocks using the new Massive Screener Engine.
    
    Adapts the new engine output to match the old frontend contract.
    """
    from app.services.screener_service import screener_service
    
    try:
        # Run the Massive Screener
        # min_value logic is handled in service (default > 1B), filter further here if needed
        results = await screener_service.screen_stocks(limit=limit * 2, min_rvol=min_rvol)
        
        # Filter by value (convert min_value from Miliar to full IDR)
        min_value_idx = min_value * 1_000_000_000
        filtered_results = [r for r in results if r['value_idr'] >= min_value_idx]
        
        # Map to Frontend Format
        mapped_results = []
        for r in filtered_results[:limit]:
            # Determine Signal Label from signals list
            signal_label = "NORMAL"
            reason = ""
            
            if "RVOL_SPIKE_EXTREME" in r['signals']:
                signal_label = "HOT"
                reason = "Extreme Volume Spike"
            elif "RVOL_SPIKE" in r['signals']:
                signal_label = "WARM"
                reason = "Volume Spike"
            elif "GOLDEN_CROSS" in r['signals']:
                signal_label = "WARM"
                reason = "Golden Cross"
            
            # Append other signals to reason
            other_signals = [s for s in r['signals'] if s not in ["RVOL_SPIKE_EXTREME", "RVOL_SPIKE", "GOLDEN_CROSS"]]
            if other_signals:
                reason += f" | {', '.join(other_signals)}"
            
            # Add Bandar Status to reason if significant
            if r['bandar_status'] != "NEUTRAL":
                reason += f" | {r['bandar_status']}"


            # Calculate Recommendation based on technicals and bandarmology
            recommendation = "HOLD"
            if r['rsi'] < 35 and r['bandar_status'] in ['AKUMULASI', 'Big Acc']:
                recommendation = "STRONG BUY"
            elif r['rsi'] < 45 and r['bandar_status'] in ['AKUMULASI', 'Big Acc', 'Small Acc']:
                recommendation = "BUY / ACCUMULATE"
            elif r['rsi'] > 70 or r['bandar_status'] in ['DISTRIBUSI', 'Big Dist']:
                recommendation = "SELL"
            elif r['rsi'] > 60 and r['bandar_status'] in ['Small Dist']:
                recommendation = "REDUCE"
            elif len(r['signals']) > 0 and 'ABOVE_VWAP' in r['signals']:
                recommendation = "BUY / ACCUMULATE"
            
            # Calculate Price Targets (simplified based on technicals)
            current_price = r['price']
            conservative_target = round(current_price * 1.05, 0)  # +5%
            moderate_target = round(current_price * 1.10, 0)  # +10%
            aggressive_target = round(current_price * 1.20, 0)  # +20%
            
            # Calculate momentum label
            momentum = "neutral"
            if r['rsi'] > 60:
                momentum = "bullish"
            elif r['rsi'] < 40:
                momentum = "bearish"
            elif 'ABOVE_VWAP' in r['signals']:
                momentum = "bullish"

            mapped_results.append({
                'ticker': r['ticker'],
                'name': r['ticker'],
                'sector': "Unknown",
                'price': r['price'],
                'change_percent': r['change_pct'],
                'volume': r['volume'],
                'volume_formatted': f"{r['volume'] / 1_000_000:.1f}M" if r['volume'] >= 1_000_000 else f"{r['volume'] / 1_000:.1f}K",
                'avg_volume': r['volume'],
                'rvol': r['rvol'],
                'value_miliar': round(r['value_idr'] / 1_000_000_000, 1),
                'signal': signal_label,
                'signal_reason': reason.strip(" | "),
                # Enhanced fields
                'recommendation': recommendation,
                'momentum': momentum,
                'signals_list': r['signals'],
                'bandar_status': r['bandar_status'],
                'bandar_volume': r.get('bandar_volume', 0),
                'price_targets': {
                    'conservative': conservative_target,
                    'moderate': moderate_target,
                    'aggressive': aggressive_target
                },
                'key_indicators': {
                    'rsi': r['rsi'],
                    'macd': r.get('macd', 0),
                    'stoch_k': r.get('stoch_k', 50),
                    'vol_ratio': r['rvol']
                },
                'technicals': {
                    'ma20': r.get('ma20', 0),
                    'ma50': r.get('ma50', 0),
                    'vwap': r.get('vwap', 0),
                    'rsi': r['rsi'],
                    'stoch_k': r.get('stoch_k', 50)
                },
                'top_buyers': r.get('top_buyers', [])[:3],
                'top_sellers': r.get('top_sellers', [])[:3]
            })
            
        return {
            "count": len(mapped_results),
            "filters": {
                "min_rvol": min_rvol,
                "min_value_miliar": min_value,
            },
            "timestamp": int(time.time()),
            "results": mapped_results
        }
    except Exception as e:
        print(f"Screener Error: {e}")
        return {"count": 0, "results": []}


@router.get("/scanner/hot")
async def get_hot_stocks():
    """
    Quick scan for HOT stocks only (Wrapper for Massive Screener).
    """
    # Reuse the logic above with strict filters
    return await scan_volume_stocks(min_rvol=2.0, min_value=20, limit=10)


# ========================================
# WEBSOCKET ENDPOINT (Enhanced)
# ========================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_json(self, websocket: WebSocket, data: dict):
        try:
            if websocket in self.active_connections:
                await websocket.send_json(data)
        except Exception as e:
            self.disconnect(websocket)

manager = ConnectionManager()


@router.websocket("/ws/{ticker}")
async def websocket_endpoint(websocket: WebSocket, ticker: str):
    """
    Real-time WebSocket endpoint.
    
    Streams:
    - Price updates (every 5 seconds)
    - Order flow analysis
    - Trading signals
    """
    await manager.connect(websocket)
    
    formatted_ticker = ticker.upper()
    if not formatted_ticker.endswith(".JK"):
        formatted_ticker += ".JK"
    
    try:
        await manager.send_json(websocket, {
            "type": "connected",
            "ticker": formatted_ticker,
            "message": f"Connected to Remora-Quant feed for {formatted_ticker}"
        })
        
        while True:
            try:
                stock = yf.Ticker(formatted_ticker)
                info = stock.fast_info
                current_price = info.last_price
                
                if current_price:
                    # Get order flow
                    order_flow = await get_order_flow_internal(formatted_ticker, current_price)
                    
                    # Create comprehensive update
                    update = {
                        "type": "update",
                        "ticker": formatted_ticker,
                        "price": float(current_price),
                        "timestamp": int(time.time()),
                        "order_flow": {
                            "obi": order_flow.get('obi', 0),
                            "signal": order_flow.get('signal', 'NEUTRAL'),
                            "signal_strength": order_flow.get('signal_strength', 0),
                            "net_flow": order_flow.get('net_flow', 0),
                            "iceberg_detected": order_flow.get('iceberg_detected', False)
                        },
                        "recommendation": order_flow.get('recommendation', '')
                    }
                    await manager.send_json(websocket, update)
                    
            except Exception as e:
                await manager.send_json(websocket, {
                    "type": "error",
                    "message": f"Failed to fetch data: {str(e)}"
                })
            
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ========================================
# GOAPI USAGE STATUS ENDPOINT
# ========================================

@router.get("/goapi/status")
async def get_goapi_status():
    """
    Get current GoAPI usage status.
    
    Returns:
    - Daily/monthly usage counts
    - Remaining quota
    - Warning status if approaching limits
    """
    from app.services.api_usage_tracker import get_usage_status
    return get_usage_status()


# ========================================
# FILE UPLOAD ENDPOINTS (NEW)
# ========================================

# In-memory cache for uploaded data (per ticker)
_uploaded_broker_data: Dict[str, BrokerSummaryData] = {}
_uploaded_financial_data: Dict[str, FinancialReportData] = {}


@router.post("/upload/broker-summary")
async def upload_broker_summary(
    file: UploadFile = File(...),
    ticker: str = Form(...)
):
    """
    Upload broker summary file (PDF/CSV/Excel).
    
    Use this when API fails or hits rate limits.
    
    Supported formats:
    - CSV: Stockbit/Ajaib style broker summary
    - Excel: Same format as CSV
    - PDF: Stockbit broker summary PDF
    
    Returns parsed broker data including:
    - BCR (Broker Concentration Ratio)
    - Top buyers/sellers with classification
    - Retail disguise detection
    - Smart Money Flow score
    """
    try:
        content = await file.read()
        result = await handle_file_upload(
            file_content=content,
            filename=file.filename,
            ticker=ticker,
            upload_type="broker_summary"
        )
        
        if result.success and result.parsed_data:
            # Cache the parsed data
            broker_data = BrokerSummaryData(**result.parsed_data)
            _uploaded_broker_data[ticker.upper()] = broker_data
        
        return result.model_dump()
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Upload failed: {str(e)}",
            "file_type": "unknown",
            "file_name": file.filename if file else "unknown",
            "errors": [str(e)]
        }


@router.post("/upload/broker-summary-image")
async def upload_broker_summary_image(
    file: UploadFile = File(...),
    ticker: str = Form(...)
):
    """
    Upload broker summary screenshot (PNG/JPG) for OCR parsing.
    
    Uses Tesseract OCR to extract broker data from Stockbit/Ajaib screenshots.
    
    Supported formats: PNG, JPG, JPEG
    """
    from app.services.file_upload_service import parse_broker_summary_image, FileType
    
    try:
        # Validate file type
        ext = file.filename.lower().split('.')[-1] if file.filename else ''
        if ext not in ['png', 'jpg', 'jpeg']:
            return {
                "success": False,
                "message": "Unsupported image format. Use PNG or JPG.",
                "file_type": "unknown",
                "file_name": file.filename,
                "errors": ["Only PNG and JPG images are supported"]
            }
        
        content = await file.read()
        broker_data = parse_broker_summary_image(content, ticker, file.filename)
        
        # Cache the parsed data
        _uploaded_broker_data[ticker.upper()] = broker_data
        
        return {
            "success": True,
            "message": f"Successfully parsed broker summary from image (OCR)",
            "file_type": "image",
            "file_name": file.filename,
            "parsed_data": broker_data.model_dump(),
            "warnings": ["OCR accuracy may vary. Please verify the extracted data."]
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"OCR parsing failed: {str(e)}",
            "file_type": "image",
            "file_name": file.filename if file else "unknown",
            "errors": [str(e)]
        }


@router.post("/upload/financial-report")
async def upload_financial_report(
    file: UploadFile = File(...),
    ticker: str = Form(...)
):
    """
    Upload financial report file (CSV/Excel).
    
    Used for Alpha-V Fundamental and Quality scoring.
    
    Expected format (CSV/Excel):
    - Metric | Value format
    - Or wide format with columns as metrics
    
    Key metrics extracted:
    - PER, PBV, PCF, EV/EBITDA
    - ROE, ROA, NPM
    - OCF, Net Income (for quality score)
    - DER (for solvency check)
    """
    try:
        content = await file.read()
        result = await handle_file_upload(
            file_content=content,
            filename=file.filename,
            ticker=ticker,
            upload_type="financial_report"
        )
        
        if result.success and result.parsed_data:
            # Cache the parsed data (In-Memory)
            financial_data = FinancialReportData(**result.parsed_data)
            _uploaded_financial_data[ticker.upper()] = financial_data
            
            # Persist to DuckDB (Persistent Storage)
            try:
                from app.services.database_service import db_service
                db_service.insert_financial_report(ticker.upper(), result.parsed_data)
            except Exception as db_err:
                print(f"Failed to persist financial report to DB: {db_err}")
        
        return result.model_dump()
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Upload failed: {str(e)}",
            "file_type": "unknown",
            "file_name": file.filename if file else "unknown",
            "errors": [str(e)]
        }


@router.get("/upload/status/{ticker}")
async def get_upload_status(ticker: str):
    """
    Check what uploaded data is available for a ticker.
    """
    ticker_upper = ticker.upper()
    
    broker_available = ticker_upper in _uploaded_broker_data
    financial_available = ticker_upper in _uploaded_financial_data
    
    result = {
        "ticker": ticker_upper,
        "broker_summary_uploaded": broker_available,
        "financial_report_uploaded": financial_available,
        "has_any_upload": broker_available or financial_available
    }
    
    if broker_available:
        bd = _uploaded_broker_data[ticker_upper]
        result["broker_summary_info"] = {
            "date": bd.date,
            "bcr": bd.bcr,
            "phase": bd.phase,
            "file_name": bd.file_name
        }
    
    if financial_available:
        fd = _uploaded_financial_data[ticker_upper]
        result["financial_report_info"] = {
            "period": fd.period,
            "per": fd.per,
            "pbv": fd.pbv,
            "file_name": fd.file_name
        }
    
    return result


# ========================================
# ALPHA-V SCORING ENDPOINTS (NEW)
# ========================================

@router.get("/alpha-v/{ticker}")
async def get_alpha_v_score_endpoint(
    ticker: str,
    use_uploaded_data: bool = True
):
    """
    Get Alpha-V Hybrid Score for a stock.
    
    Alpha-V Score = (0.3 × F) + (0.2 × Q) + (0.5 × S)
    
    Where:
    - F = Fundamental Score (PER, PBV, sectoral position)
    - Q = Quality Score (OCF/Net Income, DER)
    - S = Smart Money Flow (BCR, Foreign Flow, Divergence)
    
    Grade interpretation:
    - A (80-100): High Conviction - Aggressive Buy
    - B (60-79): Momentum Play - Buy on Dip
    - C (40-59): Watchlist - Wait & See
    - D (20-39): Value Trap - Avoid
    - E (0-19): Toxic - Sell/Short
    
    Query params:
    - use_uploaded_data: Include data from user uploads (default: True)
    """
    ticker_upper = ticker.upper()
    cache_key = ticker_upper.replace(".JK", "") # Normalize for cache lookup
    
    # Get uploaded data if available (Priority 1)
    broker_data = _uploaded_broker_data.get(cache_key) if use_uploaded_data else None
    financial_data = _uploaded_financial_data.get(cache_key) if use_uploaded_data else None

    # Fallback: Fetch from Stockbit API (Priority 2 - Real-time)
    if not broker_data:
        try:
            from app.services.idx_broker_aggregator import get_broker_aggregator
            from app.models.file_models import BrokerType, BrokerEntry
            
            # Fetch directly from Stockbit (no DuckDB caching)
            aggregator = get_broker_aggregator()
            stockbit_result = await aggregator.get_broker_summary_for_stock(ticker_upper.replace(".JK",""))
            
            if stockbit_result and stockbit_result.get("source") == "stockbit":
                print(f"[Alpha-V] Got real-time data from Stockbit for {ticker_upper}")
                
                # Map Buyers
                top_buyers = []
                for b in stockbit_result.get("top_buyers", []):
                    top_buyers.append(BrokerEntry(
                        broker_code=b['code'],
                        broker_name=b['code'],
                        broker_type=BrokerType.UNKNOWN,
                        buy_value=b['value'],
                        buy_volume=b.get('volume', 0),
                        is_foreign=b['code'] in ["CC", "ML", "YP", "CS", "DB", "GS", "JP", "MS", "UB"]
                    ))
                    
                # Map Sellers
                top_sellers = []
                for s in stockbit_result.get("top_sellers", []):
                    top_sellers.append(BrokerEntry(
                        broker_code=s['code'],
                        broker_name=s['code'],
                        broker_type=BrokerType.UNKNOWN,
                        sell_value=s['value'],
                        sell_volume=s.get('volume', 0),
                        is_foreign=s['code'] in ["CC", "ML", "YP", "CS", "DB", "GS", "JP", "MS", "UB"]
                    ))

                from datetime import date
                broker_data = BrokerSummaryData(
                    ticker=ticker_upper,
                    date=date.today().isoformat(),
                    source="stockbit_realtime",
                    top_buyers=top_buyers,
                    top_sellers=top_sellers,
                    bcr=0.0,  # Not available from summary
                    net_foreign_flow=float(stockbit_result.get("net_flow", 0) or 0),
                    foreign_flow_pct=0,
                    total_buy=float(stockbit_result.get("buy_value", 0) or 0),
                    total_sell=float(stockbit_result.get("sell_value", 0) or 0),
                    total_transaction_value=float(stockbit_result.get("buy_value", 0) or 0) + float(stockbit_result.get("sell_value", 0) or 0),
                    phase=stockbit_result.get("status", "NEUTRAL")
                )
        except Exception as e:
            print(f"[Alpha-V] Stockbit fallback failed: {e}")
    
    # Fallback: Fetch from Stockbit API (Priority 2 - Live Data)
    if not financial_data:
        try:
            from app.services.stockbit_client import stockbit_client
            print(f"[Alpha-V] Fetching financial data from Stockbit for {ticker_upper}...")
            stockbit_fin = await stockbit_client.get_financial_data_with_fallback(cache_key)
            
            if stockbit_fin:
                print(f"[Alpha-V] Got financial data from Stockbit: {list(stockbit_fin.keys())}")
                # Convert to FinancialReportData
                financial_data = FinancialReportData(
                    ticker=stockbit_fin.get('ticker', cache_key),
                    period=stockbit_fin.get('period', 'Auto'),
                    report_type=stockbit_fin.get('report_type', 'quarterly'),
                    source='stockbit-auto',
                    per=stockbit_fin.get('per'),
                    pbv=stockbit_fin.get('pbv'),
                    pcf=stockbit_fin.get('pcf'),
                    ev_ebitda=stockbit_fin.get('ev_ebitda'),
                    roe=stockbit_fin.get('roe'),
                    roa=stockbit_fin.get('roa'),
                    npm=stockbit_fin.get('npm'),
                    opm=stockbit_fin.get('opm'),
                    ocf=stockbit_fin.get('ocf'),
                    net_income=stockbit_fin.get('net_income'),
                    der=stockbit_fin.get('der'),
                    current_ratio=stockbit_fin.get('current_ratio'),
                    quick_ratio=stockbit_fin.get('quick_ratio'),
                )
                print(f"[Alpha-V] Created FinancialReportData from Stockbit: PER={financial_data.per}, PBV={financial_data.pbv}, EV/EBITDA={financial_data.ev_ebitda}, PCF={financial_data.pcf}")
        except Exception as e:
            print(f"[Alpha-V] Stockbit Financial Data fallback failed: {e}")
            import traceback
            traceback.print_exc()

    # Fallback: Check DuckDB for Financial Data (Priority 3 - Persistent Cache)
    if not financial_data:
        try:
            from app.services.database_service import db_service
            db_fin = db_service.get_financial_report(ticker_upper)
            
            if db_fin:
                print(f"[Alpha-V] Found persistent financial data in DuckDB for {ticker_upper}")
                financial_data = FinancialReportData(**db_fin)
        except Exception as e:
            print(f"[Alpha-V] DB Fallback for Financial Data failed: {e}")

    # Defensive check: Ensure financial data actually has metrics
    if financial_data:
        # Check if it's just an empty shell or has real data
        has_metrics = any([
            financial_data.per is not None,
            financial_data.pbv is not None,
            financial_data.ev_ebitda is not None,
            financial_data.pcf is not None,
            financial_data.net_income is not None # Allow raw data
        ])
        
        if not has_metrics:
            financial_data = None
        else:
            # Fallback: If PER/PBV missing but we have raw data, try to fetch current price info to calc
            if (financial_data.per is None or financial_data.per == 0) or (financial_data.pbv is None or financial_data.pbv == 0):
                try:
                    # Direct YFinance injection
                    import yfinance as yf
                    yf_ticker = ticker_upper
                    if not yf_ticker.endswith(".JK"):
                        yf_ticker += ".JK"
                        
                    stock = yf.Ticker(yf_ticker)
                    info = stock.info
                    
                    print(f"[Alpha-V] Fetching live ratios from YFinance for {yf_ticker}...")
                    
                    if financial_data.per is None or financial_data.per == 0:
                        financial_data.per = info.get("trailingPE", info.get("forwardPE", 0))
                        print(f"[Alpha-V] Injected live PER: {financial_data.per}")
                        
                    if financial_data.pbv is None or financial_data.pbv == 0:
                        financial_data.pbv = info.get("priceToBook", 0)
                        print(f"[Alpha-V] Injected live PBV: {financial_data.pbv}")

                    if financial_data.ev_ebitda is None or financial_data.ev_ebitda == 0:
                         financial_data.ev_ebitda = info.get("enterpriseToEbitda", 0)
                         print(f"[Alpha-V] Injected live EV/EBITDA: {financial_data.ev_ebitda}")

                    # PCF from yfinance if missing
                    if financial_data.pcf is None or financial_data.pcf == 0:
                         financial_data.pcf = info.get("priceToCashflow")
                         # Manual calc fallback: MarketCap / OCF
                         if (not financial_data.pcf) and info.get("operatingCashflow") and info.get("marketCap"):
                             try:
                                financial_data.pcf = info.get("marketCap") / info.get("operatingCashflow")
                             except:
                                 pass
                         print(f"[Alpha-V] Injected live PCF: {financial_data.pcf}")
                         
                    # PEG Ratio for sectoral score
                    if not hasattr(financial_data, 'peg') or financial_data.peg is None:
                        financial_data.peg = info.get("pegRatio", None)
                        
                    # --- QUALITY METRICS INJECTION ---
                    
                    # DER (Debt to Equity)
                    if financial_data.der is None or financial_data.der == 0:
                        financial_data.der = info.get("debtToEquity", 0)
                        if financial_data.der and financial_data.der > 100: 
                             
                             financial_data.der = financial_data.der / 100.0
                        print(f"[Alpha-V] Injected live DER: {financial_data.der}")

                    # ROE (Return on Equity)
                    if financial_data.roe is None or financial_data.roe == 0:
                        financial_data.roe = info.get("returnOnEquity", 0)
                        if financial_data.roe:
                             financial_data.roe = financial_data.roe * 100 # YF is decimal (0.15), we want 15
                        print(f"[Alpha-V] Injected live ROE: {financial_data.roe}")

                    # OCF & Net Income (for Quality Score: OCF/NI ratio)
                    if financial_data.ocf is None or financial_data.ocf == 0:
                        financial_data.ocf = info.get("operatingCashflow", 0)
                        print(f"[Alpha-V] Injected live OCF: {financial_data.ocf}")
                        
                    if financial_data.net_income is None or financial_data.net_income == 0:
                        financial_data.net_income = info.get("netIncomeToCommon", 0)
                        print(f"[Alpha-V] Injected live Net Income: {financial_data.net_income}")
                        
                    # Recalculate derived OCF/NI if we injected new data
                    if (financial_data.ocf_to_net_income is None) and financial_data.ocf and financial_data.net_income:
                        financial_data.ocf_to_net_income = financial_data.ocf / financial_data.net_income
                             
                except Exception as e:
                    print(f"[Alpha-V] Failed to inject live ratios: {e}")

    print(f"[Alpha-V] Cache lookup for {cache_key}: Broker={'YES' if broker_data else 'NO'}, Financial={'YES' if financial_data else 'NO'}")
    
    # Determine price trend (simplified)
    price_trend = "neutral"
    volume_trend = "neutral"
    has_price_data = False
    
    try:
        formatted_ticker = f"{ticker_upper}.JK" if not ticker_upper.endswith(".JK") else ticker_upper
        stock = yf.Ticker(formatted_ticker)
        hist = stock.history(period="1mo")
        
        if not hist.empty and len(hist) > 5:
            has_price_data = True
            recent_close = hist['Close'].iloc[-1]
            week_ago_close = hist['Close'].iloc[-5] if len(hist) >= 5 else hist['Close'].iloc[0]
            
            pct_change = (recent_close - week_ago_close) / week_ago_close * 100
            if pct_change > 5:
                price_trend = "up"
            elif pct_change < -5:
                price_trend = "down"
            
            # Volume trend
            recent_vol = hist['Volume'].iloc[-5:].mean()
            older_vol = hist['Volume'].iloc[-10:-5].mean() if len(hist) >= 10 else recent_vol
            
            if recent_vol > older_vol * 1.2:
                volume_trend = "increasing"
            elif recent_vol < older_vol * 0.8:
                volume_trend = "decreasing"
    except:
        pass
    
    # Determine sector
    sector = "Default"
    if financial_data and financial_data.sector:
        sector = financial_data.sector
    
    # Calculate Alpha-V score
    alpha_v = calculate_alpha_v_score(
        ticker=ticker_upper,
        financial_data=financial_data,
        broker_data=broker_data,
        sector=sector,
        price_trend=price_trend,
        volume_trend=volume_trend
    )
    
    # Add display helpers
    return {
        **alpha_v.model_dump(),
        "grade_color": get_grade_color(alpha_v.grade),
        "grade_label": get_grade_label(alpha_v.grade),
        "data_availability": {
            "broker_data": broker_data is not None,
            "financial_data": financial_data is not None,
            "price_data": has_price_data
        }
    }


@router.get("/conviction-analysis/{ticker}")
async def get_conviction_analysis(ticker: str):
    """
    Get comprehensive conviction analysis combining:
    - Alpha-V Score
    - Broker Summary (API or uploaded)
    - Technical Indicators
    - Order Flow Analysis
    
    This is the master endpoint for complete stock analysis.
    """
    ticker_upper = ticker.upper()
    formatted_ticker = f"{ticker_upper}.JK" if not ticker_upper.endswith(".JK") else ticker_upper
    
    result = {
        "ticker": ticker_upper,
        "timestamp": int(time.time()),
        "alpha_v": None,
        "broker_summary": None,
        "technical": None,
        "order_flow": None,
        "data_completeness": 0,
        "missing_data": [],
        "conviction_level": "LOW",
        "action": "HOLD",
        "rationale": []
    }
    
    completeness = 0
    
    # 1. Get Alpha-V Score
    try:
        alpha_v_result = await get_alpha_v_score_endpoint(ticker)
        result["alpha_v"] = alpha_v_result
        completeness += 40
    except Exception as e:
        result["missing_data"].append(f"Alpha-V: {str(e)}")
    
    # 2. Get Broker Summary
    try:
        # Check uploaded first
        if ticker_upper in _uploaded_broker_data:
            result["broker_summary"] = _uploaded_broker_data[ticker_upper].model_dump()
            result["broker_summary"]["source"] = "upload"
            completeness += 25
        else:
            # Try API
            bandar_result = await get_bandarmology(ticker)
            result["broker_summary"] = bandar_result
            if bandar_result.get("source") != "error":
                completeness += 25
            else:
                result["missing_data"].append("Broker Summary: API failed - please upload file")
    except Exception as e:
        result["missing_data"].append(f"Broker Summary: {str(e)}")
    
    # 3. Get Technical Indicators
    try:
        indicators = await get_indicators(ticker, period="3mo")
        result["technical"] = {
            "rsi": indicators.get("rsi"),
            "macd_signal": indicators.get("macd_signal"),
            "trend": indicators.get("trend"),
            "bb_position": indicators.get("bb_position")
        }
        completeness += 20
    except Exception as e:
        result["missing_data"].append(f"Technical: {str(e)}")
    
    # 4. Get Order Flow
    try:
        stock = yf.Ticker(formatted_ticker)
        price = stock.fast_info.last_price
        if price:
            order_flow = await get_order_flow_internal(formatted_ticker, price)
            result["order_flow"] = {
                "obi": order_flow.get("obi"),
                "signal": order_flow.get("signal"),
                "net_flow": order_flow.get("net_flow")
            }
            completeness += 15
    except Exception as e:
        result["missing_data"].append(f"Order Flow: {str(e)}")
    
    result["data_completeness"] = completeness
    
    # Determine conviction and action
    if result["alpha_v"]:
        score = result["alpha_v"].get("total_score", 50)
        grade = result["alpha_v"].get("grade", "C")
        
        if score >= 80:
            result["conviction_level"] = "VERY_HIGH"
            result["action"] = "BUY"
            result["rationale"].append(f"Grade {grade}: High conviction opportunity")
        elif score >= 60:
            result["conviction_level"] = "HIGH"
            result["action"] = "BUY"
            result["rationale"].append(f"Grade {grade}: Momentum play with institutional support")
        elif score >= 40:
            result["conviction_level"] = "MEDIUM"
            result["action"] = "HOLD"
            result["rationale"].append(f"Grade {grade}: Wait for clearer signals")
        elif score >= 20:
            result["conviction_level"] = "LOW"
            result["action"] = "AVOID"
            result["rationale"].append(f"Grade {grade}: Value trap characteristics")
        else:
            result["conviction_level"] = "VERY_LOW"
            result["action"] = "SELL"
            result["rationale"].append(f"Grade {grade}: Toxic or distribution phase")
    
    # Add data quality warning
    if completeness < 50:
        result["rationale"].append(f"⚠️ Low data completeness ({completeness}%) - analysis may be incomplete")
    
    return result

@router.post("/adk/swarm-analysis/{ticker}")
async def run_swarm_analysis(ticker: str):
    """
    Triggers the Multi-Agent Swarm (Phase 18) to analyze the ticker.
    Agents: Supervisor, Quant, Risk, Bandar.
    """
    from app.adk.agent_swarm import agent_swarm
    
    # 1. Gather Context (Reuse Conviction Logic)
    # in a real implementation, we would call orchestrator.get_full_context(ticker)
    # Here we emulate it by calling the existing conviction endpoint logic internally
    # or just fetching what we have.
    
    # For now, let's just fetch the data directly to ensure fresh state
    context_data = await get_conviction_analysis(ticker)
    
   
    risk_profile = {
        "atr_percentage": 0.02, # Default safe
        "max_drawdown": 0.05
    }
    
    # If we have technical data, try to extract ATR
    if context_data.get("technical"):
        # simple mock mapping for now
        pass
        
    full_context = {
        "alpha_v": context_data.get("alpha_v", {}),
        "bandarmology": context_data.get("broker_summary", {}), # Mapping broker summary to bandarmology
        "risk_profile": risk_profile
    }
    
    # 2. Run Mission
    mission_report = await agent_swarm.run_mission(ticker, full_context)
    
    return mission_report




