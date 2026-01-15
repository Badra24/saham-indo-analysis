"""
ADK Orchestrator Tool

Super-tool that fetches ALL analysis data in one call.
This reduces tool calls and provides complete data for AI analysis.
"""

import asyncio
from typing import Dict, Any
from google.adk.tools import FunctionTool

import yfinance as yf


def _get_ml_interpretation(prediction: Dict, features: Dict) -> str:
    """
    Generate human-readable interpretation of ML prediction for LLM context.
    This helps the LLM agent understand and communicate ML results.
    """
    pattern = prediction.get('pattern', 'NEUTRAL')
    prob = prediction.get('accumulation_probability', 0.5)
    conf = prediction.get('confidence', 0.5)
    direction = prediction.get('price_direction', 'FLAT')
    hhi = features.get('hhi', 0)
    foreign = features.get('foreign_flow_ratio', 0)
    
    parts = []
    
    # Pattern interpretation
    if pattern == 'ACCUMULATION':
        parts.append(f"ML Model detects ACCUMULATION pattern ({prob:.0%} probability)")
        parts.append(f"Price direction prediction: {direction}")
    elif pattern == 'DISTRIBUTION':
        parts.append(f"ML Model detects DISTRIBUTION pattern ({1-prob:.0%} probability)")
        parts.append(f"Price direction prediction: {direction}")
    else:
        parts.append("ML Model shows NEUTRAL - no clear accumulation/distribution")
    
    # Confidence level
    if conf >= 0.8:
        parts.append(f"Confidence: HIGH ({conf:.0%})")
    elif conf >= 0.6:
        parts.append(f"Confidence: MODERATE ({conf:.0%})")
    else:
        parts.append(f"Confidence: LOW ({conf:.0%})")
    
    # Key feature insights
    insights = []
    if hhi > 2500:
        insights.append("HHI indicates highly concentrated trading (Bandar dominant)")
    elif hhi > 1500:
        insights.append("HHI shows moderate concentration")
    
    if foreign > 0.3:
        insights.append(f"High foreign participation ({foreign:.0%})")
    
    if insights:
        parts.append("Key Insights: " + "; ".join(insights))
    
    return " | ".join(parts)

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
        # PHASE 2: BANDARMOLOGY ANALYSIS (HYBRID DB + GoAPI)
        # ========================================
        try:
            from app.services.idx_broker_aggregator import get_broker_aggregator
            
            # Direct fetch from Stockbit (no DuckDB)
            raw_symbol = formatted_symbol.replace(".JK", "")
            aggregator = get_broker_aggregator()
            
            # Using sync wrapper for async call in non-async context
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            
            if loop and loop.is_running():
                # If event loop is running, create task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    bandar_result = pool.submit(
                        asyncio.run, 
                        aggregator.get_broker_summary_for_stock(raw_symbol)
                    ).result()
            else:
                bandar_result = asyncio.run(aggregator.get_broker_summary_for_stock(raw_symbol))
            
            data_source = "STOCKBIT_REALTIME" if bandar_result and bandar_result.get('source') == 'stockbit' else "FALLBACK"
            
            if not bandar_result:
                bandar_result = {'status': 'NEUTRAL', 'is_demo': False}
            
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
            status = bandar_result.get('status', 'NEUTRAL')
            if status == 'BIG_ACCUMULATION':
                recommendation = "BULLISH - Institusi agresif membeli, ikuti arah Smart Money"
            elif status == 'ACCUMULATION':
                recommendation = "BULLISH MODERAT - Akumulasi terdeteksi"
            elif status == 'BIG_DISTRIBUTION':
                recommendation = "BEARISH - Institusi agresif menjual, WASPADA"
            elif status == 'DISTRIBUTION':
                recommendation = "BEARISH MODERAT - Distribusi terdeteksi"
            elif status == 'CHURNING':
                recommendation = "NETRAL - Wash trading terdeteksi, HINDARI"
            else:
                recommendation = "NETRAL - Tidak ada arah jelas"
            
            phase_2_bandarmology = {
                "smart_money_detected": smart_money_detected,
                "broker_pattern": status_to_pattern.get(status, 'NETRAL'),
                "status_raw": status,
                "top_buyers": bandar_result.get('top_buyers', []),
                "top_sellers": bandar_result.get('top_sellers', []),
                "net_foreign_flow": bandar_result.get('foreign_net_flow', 0) or bandar_result.get('net_foreign_flow', 0),
                "institutional_net_flow": bandar_result.get('institutional_net_flow', 0),
                "retail_net_flow": bandar_result.get('retail_net_flow', 0),
                "concentration_ratio": bandar_result.get('concentration_ratio', 0),
                "dominant_player": bandar_result.get('dominant_player', 'UNKNOWN'),
                "churn_detected": bandar_result.get('churn_detected', False),
                "signal_strength": bandar_result.get('signal_strength', 0),
                "recommendation": recommendation,
                "data_source": data_source
            }
            
        except Exception as bandar_error:
            print(f"Error getting bandarmology: {bandar_error}")
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
            
            # Hybrid Fallback: Use Stockbit for broker, DuckDB only for financial (user uploads)
            from app.services.database_service import db_service
            from app.models.file_models import BrokerSummaryData, FinancialReportData, BrokerType, BrokerEntry
            from datetime import date
            
            non_jk_symbol = formatted_symbol.replace(".JK", "")
            
            if not uploaded_broker:
                try:
                    # Use Stockbit directly instead of DuckDB
                    from app.services.idx_broker_aggregator import get_broker_aggregator
                    aggregator = get_broker_aggregator()
                    
                    import asyncio
                    stockbit_result = asyncio.run(aggregator.get_broker_summary_for_stock(non_jk_symbol))
                    
                    if stockbit_result and stockbit_result.get("source") == "stockbit":
                        print(f"[Orchestrator] Got real-time Stockbit data for {formatted_symbol}")
                        top_buyers = [
                            BrokerEntry(broker_code=b['code'], buy_value=b['value'], buy_volume=b.get('volume', 0), broker_type=BrokerType.UNKNOWN, is_foreign=b['code'] in ["CC", "ML", "YP", "CS", "DB", "GS", "JP", "MS", "UB"]) 
                            for b in stockbit_result.get("top_buyers", [])
                        ]
                        top_sellers = [
                            BrokerEntry(broker_code=s['code'], sell_value=s['value'], sell_volume=s.get('volume', 0), broker_type=BrokerType.UNKNOWN, is_foreign=s['code'] in ["CC", "ML", "YP", "CS", "DB", "GS", "JP", "MS", "UB"]) 
                            for s in stockbit_result.get("top_sellers", [])
                        ]
                        
                        uploaded_broker = BrokerSummaryData(
                            ticker=formatted_symbol,
                            date=date.today().isoformat(),
                            source="stockbit_realtime",
                            top_buyers=top_buyers,
                            top_sellers=top_sellers,
                            bcr=0.0,
                            net_foreign_flow=float(stockbit_result.get("net_flow", 0) or 0),
                            foreign_flow_pct=0,
                            total_buy=float(stockbit_result.get("buy_value", 0) or 0),
                            total_sell=float(stockbit_result.get("sell_value", 0) or 0),
                            total_transaction_value=float(stockbit_result.get("buy_value", 0) or 0) + float(stockbit_result.get("sell_value", 0) or 0),
                            phase=stockbit_result.get("status", "NEUTRAL")
                        )
                except Exception as e:
                    print(f"[Orchestrator] Stockbit fallback failed: {e}")
            
            if not uploaded_financial:
                # TRY STOCKBIT FIRST for financial data
                try:
                    from app.services.stockbit_client import stockbit_client
                    # Use sync wrapper for async call
                    fin_data = asyncio.run(stockbit_client.get_financial_data(non_jk_symbol))
                    if fin_data and fin_data.get('metrics'):
                        print(f"[Orchestrator] Found financial data from Stockbit for {formatted_symbol}")
                        metrics = fin_data['metrics']
                        # Map Stockbit metrics to FinancialReportData format
                        uploaded_financial = FinancialReportData(
                            ticker=non_jk_symbol,
                            revenue=metrics.get('revenue', {}).get('value', 0) or 0,
                            net_income=0,  # Not directly available
                            total_equity=0,  # Calculate from debt_to_equity if needed
                            total_assets=0,
                            total_liabilities=0,
                            current_assets=0,
                            current_liabilities=0,
                            operating_cash_flow=0,
                            eps=0,
                            dividend_yield=metrics.get('dividend_yield', {}).get('value', 0) or 0,
                            roe=0,
                            debt_to_equity=metrics.get('debt_to_equity', {}).get('value', 0) or 0,
                        )
                except Exception as e:
                    print(f"[Orchestrator] Stockbit financial fetch failed: {e}")
                
                # FALLBACK to DuckDB only if Stockbit failed
                if not uploaded_financial:
                    try:
                        db_fin = db_service.get_financial_report(non_jk_symbol)
                        if db_fin:
                            print(f"[Orchestrator] Found persistent financial data in DuckDB for {formatted_symbol}")
                            uploaded_financial = FinancialReportData(**db_fin)
                    except Exception as e:
                        print(f"[Orchestrator] Financial DB Fallback failed: {e}")
            
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
        # PHASE 7: ML PREDICTION (Trained Model)
        # ========================================
        try:
            from app.ml.inference.predictor import get_predictor
            from app.ml.features.broker_features import BrokerFeatureExtractor
            
            # Prepare broker data for ML
            ml_broker_data = {
                'top_buyers': phase_2_bandarmology.get('top_buyers', []),
                'top_sellers': phase_2_bandarmology.get('top_sellers', [])
            }
            
            # Convert to expected format if needed (list of dicts with code/value)
            if isinstance(ml_broker_data['top_buyers'], list) and len(ml_broker_data['top_buyers']) > 0:
                if isinstance(ml_broker_data['top_buyers'][0], str):
                    # Just broker codes, no values - use bandarmology result directly
                    ml_broker_data = bandar_result if 'bandar_result' in locals() else ml_broker_data
            
            predictor = get_predictor()
            ml_prediction = predictor.predict(ml_broker_data)
            
            # Extract feature analysis for LLM interpretation
            extractor = BrokerFeatureExtractor()
            ml_features = extractor.extract(ml_broker_data)
            
            phase_7_ml_prediction = {
                "accumulation_probability": ml_prediction.get('accumulation_probability', 0.5),
                "pattern": ml_prediction.get('pattern', 'NEUTRAL'),
                "price_direction": ml_prediction.get('price_direction', 'FLAT'),
                "confidence": ml_prediction.get('confidence', 0.5),
                "model_version": ml_prediction.get('model_version', 'unknown'),
                "features": {
                    "hhi": ml_features.get('hhi', 0),
                    "bcr": ml_features.get('bcr', 1.0),
                    "retail_flow_ratio": ml_features.get('retail_flow_ratio', 0.5),
                    "foreign_flow_ratio": ml_features.get('foreign_flow_ratio', 0),
                    "top3_dominance": ml_features.get('top3_dominance', 0.33),
                    "buy_sell_imbalance": ml_features.get('buy_sell_imbalance', 0)
                },
                "interpretation": _get_ml_interpretation(ml_prediction, ml_features)
            }
        except Exception as ml_err:
            print(f"ML Prediction failed: {ml_err}")
            phase_7_ml_prediction = {
                "accumulation_probability": 0.5,
                "pattern": "UNKNOWN",
                "error": str(ml_err),
                "note": "ML prediction unavailable, using qualitative analysis only"
            }
        
        # ========================================
        # PHASE 8: ADVANCED GAP ANALYSIS (WYCKOFF & ALERTS)
        # ========================================
        try:
            from app.services.wyckoff_detector import get_wyckoff_detector, WyckoffPattern
            from app.services.alert_engine import get_alert_engine, AlertEngine
            from app.services.bandarmology import bandarmology_engine
            
            # 1. Wyckoff Pattern Detection
            detector = get_wyckoff_detector()
            price_history = hist.to_dict('records') if not hist.empty else []
            wyckoff_result = detector.detect(price_history, bandar_result)
            
            # 2. AQS & Churn Analysis
            aqs_data = bandarmology_engine.calculate_aqs(
                broker_history=[],  # TODO: Need history from DB
                price_history=hist['Close'].tolist() if not hist.empty else [],
                current_broker_data=bandar_result
            )
            
            churn_data = bandarmology_engine.calculate_churn_ratio(
                total_volume=phase_1_orderflow.get('obi', 0), # Using OBI as proxy if total volume not available
                net_ownership_change=phase_2_bandarmology.get('institutional_net_flow', 0)
            )

            # 3. HHI & Bandar VWAP
            hhi_data = bandarmology_engine.calculate_hhi(bandar_result)
            bandar_vwap_data = bandarmology_engine.calculate_bandar_vwap(bandar_result)
            
            phase_8_gap_analysis = {
                "wyckoff": {
                    "pattern": wyckoff_result.pattern.value if wyckoff_result.pattern else None,
                    "confidence": wyckoff_result.confidence,
                    "action": wyckoff_result.action,
                    "details": wyckoff_result.details
                },
                "aqs": aqs_data,
                "churn": churn_data,
                "hhi": hhi_data,
                "bandar_vwap": bandar_vwap_data
            }
            
            # 4. Alert Triggering (Fire & Forget)
            alert_engine = get_alert_engine()
            
            # Spring Alert
            if wyckoff_result.pattern == WyckoffPattern.SPRING and wyckoff_result.confidence == "HIGH":
                alert = AlertEngine.create_spring_alert(
                    symbol=formatted_symbol,
                    support_level=wyckoff_result.level,
                    current_price=current_price,
                    top_buyer=wyckoff_result.details.get('top_buyer', 'Unknown'),
                    buy_value=wyckoff_result.details.get('buy_value', 0)
                )
                alert_engine.send_alert_sync(alert)
                print(f"[Orchestrator] 🚨 SENT SPRING ALERT: {formatted_symbol}")
                
            # UTAD Alert
            elif wyckoff_result.pattern == WyckoffPattern.UTAD and wyckoff_result.confidence == "HIGH":
                alert = AlertEngine.create_utad_alert(
                    symbol=formatted_symbol,
                    resistance_level=wyckoff_result.level,
                    current_price=current_price,
                    top_seller=wyckoff_result.details.get('top_seller', 'Unknown'),
                    sell_value=wyckoff_result.details.get('sell_value', 0)
                )
                alert_engine.send_alert_sync(alert)
                print(f"[Orchestrator] 🚨 SENT UTAD ALERT: {formatted_symbol}")
                
        except Exception as gap_err:
            print(f"Gap Analysis failed: {gap_err}")
            phase_8_gap_analysis = {
                "error": str(gap_err),
                "wyckoff": {"pattern": "ERROR"},
                "aqs": {"grade": "N/A"},
                "churn": {"level": "UNKNOWN"}
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
            "phase_7_ml_prediction": phase_7_ml_prediction,
            "phase_8_gap_analysis": phase_8_gap_analysis,

            
            "summary": {
                "trend_bias": "BULLISH" if phase_1_orderflow['obi'] > 0.2 else ("BEARISH" if phase_1_orderflow['obi'] < -0.2 else "NEUTRAL"),
                "order_flow_signal": phase_1_orderflow['signal'],
                "strategy_action": phase_4_strategy['action'],
                "confidence": phase_4_strategy['confidence'],
                "kill_switch": phase_5_risk['kill_switch_active'],
                "alpha_v_score": phase_6_alphav['total_score'],
                "alpha_v_grade": phase_6_alphav['grade'],
                # ML Enhancement
                "ml_pattern": phase_7_ml_prediction.get('pattern', 'UNKNOWN'),
                "ml_confidence": phase_7_ml_prediction.get('confidence', 0),
                "ml_direction": phase_7_ml_prediction.get('price_direction', 'FLAT'),
                # Gap Analysis
                "wyckoff_pattern": phase_8_gap_analysis['wyckoff']['pattern'],
                "aqs_grade": phase_8_gap_analysis['aqs']['grade'],
                "churn_warning": phase_8_gap_analysis['churn'].get('warning', 'NONE')
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
