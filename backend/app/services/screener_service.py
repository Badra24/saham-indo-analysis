
import asyncio
import logging
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import yfinance as yf
from app.services.idx_static_data import get_all_tickers
from app.services.indicators import calculate_all_indicators

# Configure logger
logger = logging.getLogger(__name__)

class ScreenerService:
    """
    Massive AI Market Screener Engine.
    
    Features:
    - Scans 800+ stocks in parallel using ThreadPoolExecutor.
    - Implements "Analisis Scanning saham.txt" criteria (RVOL, VWAP, Bandarmology).
    - High performance (seconds vs minutes).
    """
    
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=50) # Optimum for I/O bound tasks
        
    def _fetch_analyze_single(self, ticker: str) -> Optional[Dict]:
        """
        Worker function to fetch and analyze a single stock.
        Running in a separate thread.
        """
        try:
            # 1. Fetch Data (1 year for MA200)
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo") # 6 months is enough for most indicators
            
            if hist.empty or len(hist) < 50:
                return None
                
            # 2. Calculate Technicals
            df = calculate_all_indicators(hist)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 3. Extract Core Metrics
            price = latest['Close']
            volume = latest['Volume']
            avg_vol_20 = latest.get('Volume_SMA', volume)
            if avg_vol_20 == 0: avg_vol_20 = 1
            
            rvol = volume / avg_vol_20
            value_idr = price * volume
            
            # 4. Status Classification (The "AI" Logic)
            signals = []
            
            # --- RESEARCH CRITERIA ---
            
            # A. Anomaly Volume (Bandar Activity)
            if rvol > 3.0:
                signals.append("RVOL_SPIKE_EXTREME")
            elif rvol > 2.0:
                signals.append("RVOL_SPIKE")
                
            # B. Trend & Momentum
            rsi = latest.get('RSI', 50)
            if rsi > 70:
                signals.append("OVERBOUGHT")
            elif rsi < 30:
                signals.append("OVERSOLD")
                
            # C. VWAP Logic (Bullish Control)
            vwap = latest.get('VWAP', price)
            if price > vwap:
                signals.append("ABOVE_VWAP")
            
            # D. Reversal Detection (Oversold + Trend Naik logic from viral image)
            # Logic: RSI Oversold but Price > MA5 or Price making higher low (simplified)
            ma20 = latest.get('SMA_20', 0) or latest.get('EMA_21', 0)
            if rsi < 35 and price > prev['Close']:
                signals.append("POTENTIAL_REVERSAL")
                
            # E. Golden Cross
            ma50 = latest.get('SMA_50', 0)
            ma200 = latest.get('SMA_200', 0)
            if ma50 > ma200 and prev.get('SMA_50', 0) <= prev.get('SMA_200', 0):
                signals.append("GOLDEN_CROSS")

            # 5. Bandarmology (Approximation without Broker Sum)
            # If Volume Up + Price Up = Accumulation
            # If Volume Up + Price Down = Distribution
            price_change_pct = (price - prev['Close']) / prev['Close'] * 100
            
            bandar_status = "NEUTRAL"
            if rvol > 1.5:
                if price_change_pct > 1:
                    bandar_status = "AKUMULASI"
                elif price_change_pct < -1:
                    bandar_status = "DISTRIBUSI"
            
            return {
                "ticker": ticker.replace(".JK", ""),
                "price": float(price),
                "change_pct": round(float(price_change_pct), 2),
                "volume": int(volume),
                "value_idr": float(value_idr),
                "rvol": round(float(rvol), 2),
                "rsi": round(float(rsi), 2),
                "ma20": round(float(ma20), 0),
                "ma50": round(float(ma50), 0),
                "stoch_k": round(float(latest.get('Stoch_K', 50)), 2),
                "signals": signals,
                "bandar_status": bandar_status,
                "vwap": round(float(vwap), 0)
            }
            
        except Exception as e:
            # logger.error(f"Error screening {ticker}: {e}")
            return None

    async def _enrich_with_bandarmology(self, result: Dict) -> Dict:
        """
        Fetch Bandarmology data from Stockbit for a filtered result.
        """
        try:
            from app.services.stockbit_client import stockbit_client
            
            # Only fetch if we have a valid token (handled inside client)
            bandar_data = await stockbit_client.get_bandarmology(result['ticker'])
            
            if bandar_data:
                result['bandar_status'] = bandar_data.get('top1_status', 'NEUTRAL')
                result['bandar_volume'] = bandar_data.get('top1_amount', 0)
                result['top_buyers'] = bandar_data.get('top_buyers', [])
                result['top_sellers'] = bandar_data.get('top_sellers', [])
                
                # Enhanced Logic: Override technical status if Bandar Logic conflicts
                # Example: If Stock Down but Big Accumulation -> "MARKDOWN ACCUM"
                price_chg = result['change_pct']
                status = bandar_data.get('avg5_status', '')
                
                if "Acc" in status:
                    if price_chg < -1:
                        result['signals'].append("MARKDOWN_ACCUMULATION")
                    elif price_chg > 0:
                        result['signals'].append("MARKUP_ACCUMULATION")
                elif "Dist" in status:
                     if price_chg > 1:
                        result['signals'].append("MARKUP_DISTRIBUTION")
                        
        except Exception as e:
            logger.error(f"Enrichment failed for {result['ticker']}: {e}")
            
        return result

    async def screen_stocks(self, limit: int = 100, min_rvol: float = 1.0) -> List[Dict]:
        """
        Run Massive Scan on ALL Stocks.
        """
        # 1. Get Universe
        all_tickers = get_all_tickers() # 800+ stocks
        # Optional: Filter universe for testing? No, user wants MASSIVE.
        
        logger.info(f"Starting scan for {len(all_tickers)} stocks...")
        
        # 2. Run Parallel (Technical Analysis - Level 1)
        loop = asyncio.get_running_loop()
        futures = [
            loop.run_in_executor(self._executor, self._fetch_analyze_single, ticker)
            for ticker in all_tickers
        ]
        
        results = await asyncio.gather(*futures)
        
        # 3. Filter Results (Level 1)
        valid_results = [r for r in results if r is not None]
        filtered = [r for r in valid_results if r['value_idr'] > 1_000_000_000] # > 1 Miliar Liquidity
        
        if min_rvol > 0:
            filtered = [r for r in filtered if r['rvol'] >= min_rvol]
            
        # Sort by RVOL (Most active)
        filtered.sort(key=lambda x: x['rvol'], reverse=True)
        top_candidates = filtered[:limit]
        
        # 4. Enrich with Stockbit Bandarmology (Level 2 - Deep Dive)
        # RATE LIMITED: Only 5 concurrent requests to avoid overwhelming Stockbit
        logger.info(f"Enriching top {len(top_candidates)} stocks with Bandarmology (rate limited)...")
        
        # Use semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def rate_limited_enrich(res):
            async with semaphore:
                await asyncio.sleep(0.1)  # Small delay to be polite to API
                return await self._enrich_with_bandarmology(res)
        
        enriched_results = await asyncio.gather(*[rate_limited_enrich(res) for res in top_candidates])
        
        return enriched_results

# Singleton
screener_service = ScreenerService()
