"""
ADK Orchestrator Tool

Super-tool that fetches ALL analysis data in one call.
This reduces tool calls and provides complete data for AI analysis.
"""

import asyncio
from typing import Dict, Any
from google.adk.tools import FunctionTool

import yfinance as yf


def _get_full_analysis_data_sync(symbol: str) -> Dict[str, Any]:
    """
    Synchronous implementation of full analysis data fetcher.
    
    Gathers all data from existing services:
    - Order Flow (OBI, HAKA/HAKI, Iceberg)
    - Bandarmology (Broker patterns, Smart Money)
    - Technical Indicators (RSI, MACD, VWAP, EMA, BB)
    - Looping Strategy signals
    - Risk status
    
    Args:
        symbol: Stock ticker (e.g., "BBCA" or "BBCA.JK")
    
    Returns:
        Dict containing all analysis phases
    """
    try:
        # Normalize symbol for IDX
        formatted_symbol = symbol.upper()
        if not formatted_symbol.endswith(".JK"):
            formatted_symbol += ".JK"
        
        # Import existing services
        from app.services.order_flow import create_analyzer
        from app.services.simulated_orderbook import get_simulated_order_book, simulate_trade_for_ticker
        # Note: bandarmology now uses goapi_client (imported in Phase 2)
        from app.services.indicators import calculate_all_indicators, get_latest_indicators
        from app.services.strategy import get_strategy
        from app.services.risk_manager import get_risk_manager
        
        # Get current price from yfinance
        stock = yf.Ticker(formatted_symbol)
        info = stock.fast_info
        current_price = info.last_price
        
        if not current_price:
            return {
                "success": False,
                "error": f"Could not fetch price for {formatted_symbol}",
                "symbol": formatted_symbol
            }
        
        # ========================================
        # PHASE 1: ORDER FLOW ANALYSIS
        # ========================================
        order_book = get_simulated_order_book(formatted_symbol, current_price, depth=10)
        trade = simulate_trade_for_ticker(formatted_symbol)
        
        analyzer = create_analyzer(depth=5)
        if trade:
            order_flow_result = analyzer.analyze(
                order_book,
                trade_price=trade['price'],
                trade_volume=trade['volume']
            )
        else:
            order_flow_result = analyzer.analyze(order_book)
        
        phase_1_orderflow = {
            "obi": order_flow_result.get('obi', 0),
            "haka_volume": order_flow_result.get('haka_volume', 0),
            "haki_volume": order_flow_result.get('haki_volume', 0),
            "net_flow": order_flow_result.get('net_flow', 0),
            "iceberg_detected": order_flow_result.get('iceberg_detected', False),
            "iceberg_side": order_flow_result.get('iceberg_side', None),
            "institutional_support": order_flow_result.get('institutional_support', []),
            "institutional_resistance": order_flow_result.get('institutional_resistance', []),
            "signal": order_flow_result.get('signal', 'NEUTRAL'),
            "signal_strength": order_flow_result.get('signal_strength', 0),
            "recommendation": order_flow_result.get('recommendation', '')
        }
        
        # ========================================
        # PHASE 2: BANDARMOLOGY ANALYSIS (REAL DATA FROM GoAPI)
        # ========================================
        try:
            from app.services.goapi_client import get_goapi_client
            
            goapi_client = get_goapi_client()
            # Remove .JK suffix for GoAPI (it expects raw symbol)
            raw_symbol = formatted_symbol.replace(".JK", "")
            bandar_result = goapi_client.get_broker_summary(raw_symbol)
            
            # Extract smart money detection from analysis
            smart_money_detected = (
                bandar_result.get('status') in ['BIG_ACCUMULATION', 'ACCUMULATION'] and
                bandar_result.get('dominant_player') == 'INSTITUTION'
            )
            
            # Map status to broker pattern
            status_to_pattern = {
                'BIG_ACCUMULATION': 'AKUMULASI_KUAT',
                'ACCUMULATION': 'AKUMULASI',
                'BIG_DISTRIBUTION': 'DISTRIBUSI_KUAT',
                'DISTRIBUTION': 'DISTRIBUSI',
                'CHURNING': 'CUCI_PIRING',
                'NEUTRAL': 'NETRAL'
            }
            
            # Build recommendation based on status
            if bandar_result.get('status') == 'BIG_ACCUMULATION':
                recommendation = "BULLISH - Institusi agresif membeli, ikuti arah Smart Money"
            elif bandar_result.get('status') == 'ACCUMULATION':
                recommendation = "BULLISH MODERAT - Akumulasi terdeteksi"
            elif bandar_result.get('status') == 'BIG_DISTRIBUTION':
                recommendation = "BEARISH - Institusi agresif menjual, WASPADA"
            elif bandar_result.get('status') == 'DISTRIBUTION':
                recommendation = "BEARISH MODERAT - Distribusi terdeteksi"
            elif bandar_result.get('status') == 'CHURNING':
                recommendation = "NETRAL - Wash trading terdeteksi, HINDARI"
            else:
                recommendation = "NETRAL - Tidak ada arah jelas"
            
            phase_2_bandarmology = {
                "smart_money_detected": smart_money_detected,
                "broker_pattern": status_to_pattern.get(bandar_result.get('status', 'NEUTRAL'), 'NETRAL'),
                "status_raw": bandar_result.get('status', 'NEUTRAL'),
                "top_buyers": bandar_result.get('top_buyers', []),
                "top_sellers": bandar_result.get('top_sellers', []),
                "net_foreign_flow": bandar_result.get('foreign_net_flow', 0),
                "institutional_net_flow": bandar_result.get('institutional_net_flow', 0),
                "retail_net_flow": bandar_result.get('retail_net_flow', 0),
                "concentration_ratio": bandar_result.get('concentration_ratio', 0),
                "dominant_player": bandar_result.get('dominant_player', 'UNKNOWN'),
                "churn_detected": bandar_result.get('churn_detected', False),
                "signal_strength": bandar_result.get('signal_strength', 0),
                "recommendation": recommendation,
                "data_source": "DEMO" if bandar_result.get('is_demo', True) else "GOAPI_REAL"
            }
            
        except Exception as bandar_error:
            print(f"Error getting GoAPI bandarmology: {bandar_error}")
            # Fallback to minimal data
            phase_2_bandarmology = {
                "smart_money_detected": False,
                "broker_pattern": "DATA_ERROR",
                "top_buyers": [],
                "top_sellers": [],
                "net_foreign_flow": 0,
                "recommendation": f"Error: {str(bandar_error)}",
                "data_source": "ERROR"
            }
        
        # ========================================
        # PHASE 3: TECHNICAL INDICATORS
        # ========================================
        hist = stock.history(period="6mo")
        
        if not hist.empty:
            hist = calculate_all_indicators(hist)
            indicators = get_latest_indicators(hist)
        else:
            indicators = {}
        
        phase_3_technical = {
            "rsi": indicators.get('rsi', 50),
            "macd_v": indicators.get('macd_v', 0),
            "macd_signal": indicators.get('macd_signal', 0),
            "macd_histogram": indicators.get('macd_histogram', 0),
            "vwap": indicators.get('vwap', current_price),
            "ema_21": indicators.get('ema_21', current_price),
            "ema_55": indicators.get('ema_55', current_price),
            "ema_200": indicators.get('ema_200', current_price),
            "sma_50": indicators.get('sma_50', current_price),
            "sma_200": indicators.get('sma_200', current_price),
            "bb_upper": indicators.get('bb_upper', current_price * 1.02),
            "bb_middle": indicators.get('bb_middle', current_price),
            "bb_lower": indicators.get('bb_lower', current_price * 0.98),
            "atr_14": indicators.get('atr_14', current_price * 0.02),
            "atr_26": indicators.get('atr_26', current_price * 0.02),
            "volume_sma": indicators.get('volume_sma', 0),
            "relative_volume": indicators.get('relative_volume', 1.0),
            # VPVR (Real Engine)
            "vpvr_poc": indicators.get('vpvr_poc', 0),
            "vpvr_vah": indicators.get('vpvr_vah', 0),
            "vpvr_val": indicators.get('vpvr_val', 0)
        }
        
        # ========================================
        # PHASE 4: LOOPING STRATEGY SIGNALS
        # ========================================
        strategy = get_strategy()
        strategy_result = strategy.analyze(
            ticker=formatted_symbol,
            current_price=current_price,
            order_flow_data=order_flow_result,
            indicators=indicators
        )
        
        phase_4_strategy = {
            "action": strategy_result.get('action', 'HOLD'),
            "position_phase": strategy_result.get('phase', 'NONE'),
            "entry_price": strategy_result.get('entry_price', current_price),
            "stop_loss": strategy_result.get('stop_loss', current_price * 0.95),
            "take_profit_1": strategy_result.get('take_profit_1', current_price * 1.03),
            "take_profit_2": strategy_result.get('take_profit_2', current_price * 1.05),
            "take_profit_3": strategy_result.get('take_profit_3', current_price * 1.08),
            "confidence": strategy_result.get('confidence', 50),
            "reasoning": strategy_result.get('reasoning', '')
        }
        
        # ========================================
        # PHASE 5: RISK STATUS
        # ========================================
        risk_manager = get_risk_manager()
        risk_status = risk_manager.get_status()
        
        phase_5_risk = {
            "kill_switch_active": risk_status.get('kill_switch_active', False),
            "daily_pnl": risk_status.get('daily_pnl', 0),
            "daily_pnl_pct": risk_status.get('daily_pnl_pct', 0),
            "remaining_risk": risk_status.get('remaining_risk', 100),
            "max_drawdown": risk_status.get('max_drawdown', 0),
            "current_exposure": risk_status.get('current_exposure', 0)
        }

        # ========================================
        # PHASE 6: ALPHA-V SCORING (NEW!)
        # ========================================
        try:
            from app.services.alpha_v_scoring import calculate_alpha_v_score
            from app.api.endpoints import _uploaded_broker_data, _uploaded_financial_data
            
            # Use uploaded data if available (cache in endpoints)
            uploaded_broker = _uploaded_broker_data.get(formatted_symbol)
            uploaded_financial = _uploaded_financial_data.get(formatted_symbol)
            
            alpha_v_score = calculate_alpha_v_score(
                ticker=formatted_symbol,
                financial_data=uploaded_financial,
                broker_data=uploaded_broker,
                current_price=current_price
            )
            
            phase_6_alphav = {
                "total_score": alpha_v_score.total_score,
                "grade": alpha_v_score.grade.value,
                "fundamental_score": alpha_v_score.fundamental_score,
                "quality_score": alpha_v_score.quality_score,
                "smart_money_score": alpha_v_score.smart_money_score,
                "strategy": alpha_v_score.strategy,
                "confidence_notes": alpha_v_score.confidence_notes
            }
        except Exception as av_err:
            print(f"Error calculating Alpha-V: {av_err}")
            phase_6_alphav = {
                "total_score": 0,
                "grade": "N/A",
                "error": str(av_err)
            }
            
        # ========================================
        # PHASE 7: ML ENGINE ANALYSIS (REAL ENGINE)
        # ========================================
        try:
            from app.services.ml_engine import ml_engine
            
            ml_result = ml_engine.analyze_latest_anomaly(hist)
            
            phase_7_ml = {
                "anomaly_detected": ml_result.get('is_anomaly', False),
                "anomaly_score": ml_result.get('score', 0),
                "description": ml_result.get('description', 'Normal'),
                "engine": "Isolation Forest (Scikit-Learn)"
            }
        except Exception as ml_err:
            print(f"Error in ML Engine: {ml_err}")
            phase_7_ml = {
                "anomaly_detected": False,
                "description": f"Error: {str(ml_err)}",
                "engine": "Failed"
            }
        
        # ========================================
        # COMPILE RESULT
        # ========================================
        return {
            "success": True,
            "symbol": formatted_symbol,
            "current_price": current_price,
            "market_cap": getattr(info, 'market_cap', None),
            
            "phase_1_orderflow": phase_1_orderflow,
            "phase_2_bandarmology": phase_2_bandarmology,
            "phase_3_technical": phase_3_technical,
            "phase_4_strategy": phase_4_strategy,
            "phase_5_risk": phase_5_risk,
            "phase_6_alphav": phase_6_alphav,
            "phase_7_ml": phase_7_ml,
            
            "summary": {
                "trend_bias": "BULLISH" if phase_1_orderflow['obi'] > 0.2 else ("BEARISH" if phase_1_orderflow['obi'] < -0.2 else "NEUTRAL"),
                "order_flow_signal": phase_1_orderflow['signal'],
                "strategy_action": phase_4_strategy['action'],
                "confidence": phase_4_strategy['confidence'],
                "kill_switch": phase_5_risk['kill_switch_active'],
                "alpha_v_score": phase_6_alphav['total_score'],
                "alpha_v_grade": phase_6_alphav['grade'],
                "ml_anomaly": phase_7_ml['anomaly_detected']
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "error_type": type(e).__name__
        }


def get_full_analysis_data(symbol: str) -> Dict[str, Any]:
    """
    Fetch complete analysis data for a stock symbol.
    
    This is the main super-tool that gathers all data needed for
    comprehensive stock analysis using the Remora-Quant methodology.
    
    Data includes:
    - Order Flow Analysis (OBI, HAKA/HAKI, Iceberg detection)
    - Bandarmology (Smart Money, Broker patterns)
    - Technical Indicators (RSI, MACD, VWAP, EMA, Bollinger)
    - Looping Strategy signals
    - Risk management status
    - Alpha-V Score (Hybrid Fundamental + Quant + Bandarmology)
    
    Args:
        symbol: Stock ticker symbol (e.g., "BBCA" for Bank Central Asia)
               Will automatically append ".JK" suffix if not present.
    
    Returns:
        Dict containing all analysis phases including Alpha-V
    """
    return _get_full_analysis_data_sync(symbol)


# Register as FunctionTool for Google ADK
get_full_analysis_data_tool = FunctionTool(func=get_full_analysis_data)
