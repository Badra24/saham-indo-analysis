"""
Volume Scanner Service - Remora-Quant

Scans IDX stocks for abnormal volume activity to detect potential "Inang" (Smart Money).

Criteria from Riset:
- RVOL (Relative Volume) > 2x MA(20)
- Value Transaction > IDR 20 Billion
- Beta between 1.5 - 3.5
- Price > VWAP (Buyers in Control)
"""

import yfinance as yf
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result from volume scan."""
    ticker: str
    name: str
    sector: str
    current_price: float
    change_percent: float
    volume: int
    avg_volume_20: int
    rvol: float  # Relative Volume
    value_traded: float  # In IDR
    signal: str  # "HOT", "WARM", "NORMAL"
    signal_reason: str


# Universe of stocks to scan (top liquid stocks + Barito/Bakrie groups)
SCAN_UNIVERSE = [
    # Blue Chips
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK",
    "TLKM.JK", "ASII.JK", "UNVR.JK", "HMSP.JK", "ICBP.JK",
    
    # Barito Group (High Priority from Riset)
    "BREN.JK", "BRPT.JK", "TPIA.JK", "CUAN.JK", "PTRO.JK",
    
    # Bakrie Group
    "BUMI.JK", "BRMS.JK", "DEWA.JK", "ENRG.JK", "BNBR.JK",
    
    # Second Liners & Tech
    "GOTO.JK", "BBYB.JK", "ARTO.JK", "BUKA.JK", "EMTK.JK",
    
    # Mining & Energy
    "ADRO.JK", "ITMG.JK", "PTBA.JK", "MEDC.JK", "PGAS.JK",
    
    # Property
    "BSDE.JK", "CTRA.JK", "SMRA.JK", "PWON.JK",
    
    # Consumer
    "INDF.JK", "MYOR.JK", "KLBF.JK", "SIDO.JK",
    
    # Others volatile
    "ANTM.JK", "INCO.JK", "MDKA.JK", "AMMN.JK",
]


async def get_stock_data(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch stock data for volume analysis.
    
    Returns volume, price, and historical data for RVOL calculation.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Get historical data for MA(20) volume
        hist = stock.history(period="1mo")
        if hist.empty:
            return None
        
        # Get current data
        info = stock.fast_info
        current_price = info.last_price if hasattr(info, 'last_price') else hist['Close'].iloc[-1]
        current_volume = info.last_volume if hasattr(info, 'last_volume') else hist['Volume'].iloc[-1]
        
        # Calculate 20-day average volume
        avg_volume_20 = hist['Volume'].tail(20).mean()
        
        # Calculate RVOL
        rvol = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
        
        # Calculate value traded
        value_traded = current_price * current_volume
        
        # Price change
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
        
        # Get stock info
        try:
            full_info = stock.info
            name = full_info.get('shortName', ticker.replace('.JK', ''))
            sector = full_info.get('sector', 'Unknown')
        except:
            name = ticker.replace('.JK', '')
            sector = 'Unknown'
        
        return {
            'ticker': ticker.replace('.JK', ''),
            'name': name,
            'sector': sector,
            'current_price': current_price,
            'change_percent': change_percent,
            'volume': int(current_volume),
            'avg_volume_20': int(avg_volume_20),
            'rvol': round(rvol, 2),
            'value_traded': value_traded,
        }
        
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None


def classify_signal(data: Dict[str, Any]) -> tuple:
    """
    Classify stock signal based on Remora-Quant criteria.
    
    Returns (signal, reason)
    """
    reasons = []
    score = 0
    
    # RVOL criteria (most important)
    if data['rvol'] >= 3.0:
        score += 3
        reasons.append(f"RVOL sangat tinggi ({data['rvol']}x)")
    elif data['rvol'] >= 2.0:
        score += 2
        reasons.append(f"RVOL tinggi ({data['rvol']}x)")
    elif data['rvol'] >= 1.5:
        score += 1
        reasons.append(f"RVOL di atas rata-rata ({data['rvol']}x)")
    
    # Value traded criteria (> 20 Miliar)
    value_miliar = data['value_traded'] / 1_000_000_000
    if value_miliar >= 50:
        score += 2
        reasons.append(f"Value > Rp 50M ({value_miliar:.1f}M)")
    elif value_miliar >= 20:
        score += 1
        reasons.append(f"Value > Rp 20M ({value_miliar:.1f}M)")
    
    # Price movement
    if data['change_percent'] >= 3:
        score += 1
        reasons.append(f"Naik {data['change_percent']:.1f}%")
    elif data['change_percent'] <= -3:
        score += 1
        reasons.append(f"Turun {data['change_percent']:.1f}%")
    
    # Classify
    if score >= 4:
        return "HOT", " | ".join(reasons)
    elif score >= 2:
        return "WARM", " | ".join(reasons)
    else:
        return "NORMAL", "Aktivitas normal"


async def scan_volume_async(
    min_rvol: float = 1.5,
    min_value: float = 10_000_000_000,  # 10 Miliar default
    limit: int = 20
) -> List[ScanResult]:
    """
    Scan stocks for volume anomalies.
    
    Args:
        min_rvol: Minimum RVOL threshold (default 1.5x)
        min_value: Minimum value traded in IDR
        limit: Max results to return
    
    Returns:
        List of ScanResult sorted by RVOL descending
    """
    results = []
    
    # Fetch all stocks in parallel
    tasks = [get_stock_data(ticker) for ticker in SCAN_UNIVERSE]
    stock_data_list = await asyncio.gather(*tasks)
    
    for data in stock_data_list:
        if data is None:
            continue
        
        # Apply filters
        if data['rvol'] < min_rvol:
            continue
        if data['value_traded'] < min_value:
            continue
        
        # Classify signal
        signal, reason = classify_signal(data)
        
        results.append(ScanResult(
            ticker=data['ticker'],
            name=data['name'],
            sector=data['sector'],
            current_price=data['current_price'],
            change_percent=data['change_percent'],
            volume=data['volume'],
            avg_volume_20=data['avg_volume_20'],
            rvol=data['rvol'],
            value_traded=data['value_traded'],
            signal=signal,
            signal_reason=reason
        ))
    
    # Sort by RVOL descending
    results.sort(key=lambda x: x.rvol, reverse=True)
    
    return results[:limit]


def scan_volume_sync(
    min_rvol: float = 1.5,
    min_value: float = 10_000_000_000,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for volume scan.
    """
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(
            scan_volume_async(min_rvol, min_value, limit)
        )
        return [
            {
                'ticker': r.ticker,
                'name': r.name,
                'sector': r.sector,
                'price': r.current_price,
                'change_percent': round(r.change_percent, 2),
                'volume': r.volume,
                'avg_volume': r.avg_volume_20,
                'rvol': r.rvol,
                'value_traded': r.value_traded,
                'signal': r.signal,
                'signal_reason': r.signal_reason
            }
            for r in results
        ]
    finally:
        loop.close()


async def get_hot_stocks() -> List[Dict[str, Any]]:
    """
    Quick scan for HOT stocks only (RVOL >= 2x, Value >= 20M).
    
    This is the primary scanner function for real-time alerts.
    """
    results = await scan_volume_async(min_rvol=2.0, min_value=20_000_000_000, limit=10)
    
    return [
        {
            'ticker': r.ticker,
            'name': r.name,
            'price': r.current_price,
            'change_percent': round(r.change_percent, 2),
            'rvol': r.rvol,
            'value_miliar': round(r.value_traded / 1_000_000_000, 1),
            'signal': r.signal,
            'reason': r.signal_reason
        }
        for r in results if r.signal in ['HOT', 'WARM']
    ]
