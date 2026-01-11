"""
Alpha-V Hybrid Scoring System

Implementation of the Alpha-V Model from research:
"Konvergensi Valuasi Fundamental dan Arus Institusional"

Total Score (TS) = (0.3 × F) + (0.2 × Q) + (0.5 × S)

Where:
- F = Fundamental Score (0-100): PER Z-Score, Sectoral Rank
- Q = Quality Score (0-100): OCF/Net Income, DER
- S = Smart Money Flow Score (0-100): BCR, Foreign Flow, Divergence

Grade Classification:
- A (80-100): High Conviction - Aggressive Buy
- B (60-79): Momentum Play - Buy on Dip
- C (40-59): Watchlist - Wait & See
- D (20-39): Value Trap - Avoid
- E (0-19): Toxic/Distribution - Sell/Short
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.models.file_models import (
    AlphaVScore, AlphaVGrade, BrokerSummaryData, FinancialReportData
)

logger = logging.getLogger(__name__)

# ============================================================================
# SECTOR BENCHMARKS (From IDX Research Data)
# ============================================================================

SECTOR_BENCHMARKS = {
    "Financials": {"avg_per": 14.0, "avg_pbv": 2.5, "avg_roe": 15.0},
    "Energy": {"avg_per": 8.0, "avg_pbv": 1.2, "avg_roe": 12.0},
    "Basic Materials": {"avg_per": 10.0, "avg_pbv": 1.5, "avg_roe": 10.0},
    "Consumer Cyclical": {"avg_per": 18.0, "avg_pbv": 3.0, "avg_roe": 12.0},
    "Consumer Defensive": {"avg_per": 20.0, "avg_pbv": 4.0, "avg_roe": 15.0},
    "Technology": {"avg_per": 30.0, "avg_pbv": 4.0, "avg_roe": 8.0},
    "Healthcare": {"avg_per": 25.0, "avg_pbv": 3.5, "avg_roe": 12.0},
    "Infrastructure": {"avg_per": 15.0, "avg_pbv": 1.5, "avg_roe": 8.0},
    "Transportation": {"avg_per": 12.0, "avg_pbv": 1.8, "avg_roe": 10.0},
    "Property": {"avg_per": 15.0, "avg_pbv": 1.0, "avg_roe": 6.0},
    "Default": {"avg_per": 15.0, "avg_pbv": 2.0, "avg_roe": 10.0}
}


# ============================================================================
# FUNDAMENTAL SCORE (F) - 0-100
# ============================================================================

def calculate_fundamental_score(
    financial_data: Optional[FinancialReportData],
    current_price: float = None,
    sector: str = "Default"
) -> Dict[str, Any]:
    """
    Calculate Fundamental Score (F) based on:
    1. PER Z-Score vs historical
    2. Sectoral Rank (percentile)
    3. PEG Ratio for growth stocks
    
    From research:
    - Z_per < -1.0 (Cheap historically): Score 100
    - Z_per > +2.0 (Expensive extreme): Score 0
    - Bottom 25% of sector: Score 80-100
    - Top 25% of sector: Score 0-20
    """
    display_breakdown = {
        "per_component": 0,
        "pbv_component": 0,
        "ev_ebitda_component": 0,
        "pcf_component": 0,
        "sectoral_component": 0,
        "notes": []
    }
    
    benchmark = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["Default"])
    
    if not financial_data:
        return {
            "score": 50,  # Neutral when no data
            "breakdown": display_breakdown,
            "confidence": 0.3,
            "notes": ["No financial data available - using neutral score"]
        }
    
    score_components = []
    
    # 1. PER Component (0-30 points)
    per_score = 0
    if financial_data.per:
        per = financial_data.per
        sector_avg = benchmark["avg_per"]
        per_ratio = per / sector_avg
        
        if per_ratio < 0.5: per_score = 30
        elif per_ratio < 0.8: per_score = 25
        elif per_ratio < 1.2: per_score = 15
        elif per_ratio < 1.5: per_score = 10
        else: per_score = 5
        
        # Check for cyclical trap
        if sector in ["Energy", "Basic Materials"] and per < 5:
            per_score = max(0, per_score - 10)
            display_breakdown["notes"].append("⚠️ Low PER in cyclical sector")
            
        display_breakdown["per_component"] = per_score
    score_components.append(per_score)
    
    # 2. PBV Component (0-20 points)
    pbv_score = 0
    if financial_data.pbv:
        pbv = financial_data.pbv
        sector_avg = benchmark["avg_pbv"]
        pbv_ratio = pbv / sector_avg
        
        if pbv_ratio < 0.5: pbv_score = 20
        elif pbv_ratio < 0.8: pbv_score = 15
        elif pbv_ratio < 1.2: pbv_score = 10
        elif pbv_ratio < 2.0: pbv_score = 5
        else: pbv_score = 0
        
        if financial_data.roe and financial_data.roe > 15:
            pbv_score = min(20, pbv_score + 5)
            
        display_breakdown["pbv_component"] = pbv_score
    score_components.append(pbv_score)

    # 3. EV/EBITDA Component (0-20 points) - NEW
    ev_score = 0
    if financial_data.ev_ebitda:
        ev = financial_data.ev_ebitda
        
        # Sector specific thresholds
        if sector in ["Infrastructure", "Technology", "Telecommunication"]: # Toleransi tinggi
             if ev < 6: ev_score = 20 # Cheap
             elif ev < 8: ev_score = 15
             elif ev < 10: ev_score = 10
             else: ev_score = 5
        elif sector == "Basic Materials": # Mining (AMMN case)
             if ev < 10: ev_score = 20
             elif ev < 15: ev_score = 15 # Toleransi mining
             else: ev_score = 5
        else: # Default
             if ev < 8: ev_score = 20
             elif ev < 10: ev_score = 15
             elif ev < 12: ev_score = 10
             else: ev_score = 5
             
        display_breakdown["ev_ebitda_component"] = ev_score
    score_components.append(ev_score)

    # 4. PCF Component (0-15 points) - NEW
    pcf_score = 0
    if financial_data.pcf:
        pcf = financial_data.pcf
        
        if pcf < 0: # Negative cash flow
            pcf_score = 0 
            display_breakdown["notes"].append("🚨 Negative Price/CashFlow")
        elif pcf < 5: # Deep Value
            pcf_score = 15
            display_breakdown["notes"].append("✓ Deep Value (PCF < 5)")
        elif pcf < 10: # Attractive
            pcf_score = 10
        elif pcf < 15: # Fair
            pcf_score = 5
        else:
            pcf_score = 0
            
        display_breakdown["pcf_component"] = pcf_score
    score_components.append(pcf_score)
    
    # 5. Sectoral Context (0-15 points)
    sectoral_score = 10  # Default neutral
    
    if sector == "Technology" and financial_data.peg and financial_data.peg < 1:
        sectoral_score = 15
        display_breakdown["notes"].append(f"PEG < 1 ({financial_data.peg:.2f})")
    
    if financial_data.earnings_growth and financial_data.earnings_growth > 20:
        sectoral_score = min(15, sectoral_score + 5)
    
    display_breakdown["sectoral_component"] = sectoral_score
    score_components.append(sectoral_score)
    
    # Calculate total
    total_score = sum(score_components)
    confidence = min(len([x for x in score_components if x > 0]) / 5, 1.0)
    
    return {
        "score": min(100, total_score),
        "breakdown": display_breakdown,
        "confidence": confidence,
        "notes": display_breakdown["notes"]
    }


# ============================================================================
# QUALITY SCORE (Q) - 0-100
# ============================================================================

def calculate_quality_score(
    financial_data: Optional[FinancialReportData]
) -> Dict[str, Any]:
    """
    Calculate Quality Score (Q) based on:
    1. OCF/Net Income ratio (Cash Conversion Quality)
    2. DER (Debt Ratio)
    
    From research:
    - R_ocf > 1.0: Score 100 (High quality earnings)
    - 0.5 < R_ocf < 1.0: Score 50
    - R_ocf < 0.5 or OCF negative: Score 0 (Manipulation risk)
    - DER < 1.0: Bonus +10
    - DER > 2.5: Penalty -20
    """
    breakdown = {
        "ocf_component": 0,
        "der_component": 0,
        "quality_flags": []
    }
    
    if not financial_data:
        return {
            "score": 50,
            "breakdown": breakdown,
            "confidence": 0.3,
            "notes": ["No financial data available - using neutral score"]
        }
    
    score = 50  # Start neutral
    
    # 1. OCF/Net Income Ratio (primary quality metric)
    if financial_data.ocf is not None and financial_data.net_income is not None:
        if financial_data.net_income != 0:
            ocf_ratio = financial_data.ocf / financial_data.net_income
            
            if ocf_ratio > 1.2:
                ocf_score = 60
                breakdown["quality_flags"].append("✓ Excellent cash conversion")
            elif ocf_ratio > 1.0:
                ocf_score = 50
                breakdown["quality_flags"].append("✓ Good cash conversion")
            elif ocf_ratio > 0.7:
                ocf_score = 35
            elif ocf_ratio > 0.5:
                ocf_score = 25
            elif ocf_ratio > 0:
                ocf_score = 15
                breakdown["quality_flags"].append("⚠️ Weak cash conversion")
            else:
                ocf_score = 0
                breakdown["quality_flags"].append("🚨 Negative OCF - possible manipulation")
            
            breakdown["ocf_component"] = ocf_score
            score = ocf_score
        elif financial_data.ocf and financial_data.ocf < 0:
            score = 0
            breakdown["ocf_component"] = 0
            breakdown["quality_flags"].append("🚨 Negative OCF with zero/negative income")
    
    # 2. DER Adjustment
    if financial_data.der is not None:
        der = financial_data.der
        
        if der < 0.5:
            der_adj = 20
            breakdown["quality_flags"].append("✓ Very low leverage - safe")
        elif der < 1.0:
            der_adj = 10
            breakdown["quality_flags"].append("✓ Low leverage")
        elif der < 2.0:
            der_adj = 0
        elif der < 2.5:
            der_adj = -10
            breakdown["quality_flags"].append("⚠️ High leverage")
        else:
            der_adj = -20
            breakdown["quality_flags"].append("🚨 Very high leverage - risky")
        
        breakdown["der_component"] = der_adj
        score += der_adj
    
    # Bonus for strong profitability
    if financial_data.roe and financial_data.roe > 15:
        score += 10
        breakdown["quality_flags"].append(f"✓ Strong ROE: {financial_data.roe:.1f}%")
    
    score = max(0, min(100, score))
    
    return {
        "score": score,
        "breakdown": breakdown,
        "confidence": 0.7 if financial_data.ocf is not None else 0.4,
        "notes": breakdown["quality_flags"]
    }


# ============================================================================
# SMART MONEY FLOW SCORE (S) - 0-100
# ============================================================================

def calculate_smart_money_score(
    broker_data: Optional[BrokerSummaryData],
    price_trend: str = "neutral",  # "up", "down", "neutral"
    volume_trend: str = "neutral"  # "increasing", "decreasing", "neutral"
) -> Dict[str, Any]:
    """
    Calculate Smart Money Flow Score (S) based on:
    1. BCR (Broker Concentration Ratio)
    2. Foreign Flow
    3. Price-Volume Divergence
    
    From research:
    - BCR > 1.5 (Top 3 Buyer dominant): Score 100
    - BCR < 0.8 (Top 3 Seller dominant): Score 0
    - Net Buy Asing > 20% consecutive: Score 100
    - Hidden Accumulation (Price flat/down + Positive BCR): Score 100 (Golden signal)
    """
    breakdown = {
        "bcr_component": 0,
        "foreign_flow_component": 0,
        "divergence_component": 0,
        "signals": []
    }
    
    if not broker_data:
        return {
            "score": 50,
            "breakdown": breakdown,
            "confidence": 0.3,
            "notes": ["No broker data available - using neutral score"]
        }
    
    score = 50  # Start neutral
    
    # 1. BCR Component (0-50 points)
    bcr = broker_data.bcr
    
    if bcr > 2.0:
        bcr_score = 50
        breakdown["signals"].append("🔥 Strong accumulation (BCR > 2.0)")
    elif bcr > 1.5:
        bcr_score = 40
        breakdown["signals"].append("✓ Accumulation signal (BCR > 1.5)")
    elif bcr > 1.2:
        bcr_score = 30
    elif bcr > 0.8:
        bcr_score = 20  # Neutral
    elif bcr > 0.5:
        bcr_score = 10
        breakdown["signals"].append("⚠️ Distribution pressure (BCR < 0.8)")
    else:
        bcr_score = 0
        breakdown["signals"].append("🚨 Strong distribution (BCR < 0.5)")
    
    breakdown["bcr_component"] = bcr_score
    score = bcr_score
    
    # 2. Foreign Flow Component (0-30 points)
    if broker_data.foreign_flow_pct:
        ff_pct = broker_data.net_foreign_flow / broker_data.total_transaction_value * 100 if broker_data.total_transaction_value > 0 else 0
        
        if ff_pct > 20:
            ff_score = 30
            breakdown["signals"].append("🔥 Strong foreign buying")
        elif ff_pct > 10:
            ff_score = 25
        elif ff_pct > 5:
            ff_score = 20
        elif ff_pct > 0:
            ff_score = 15
        elif ff_pct > -10:
            ff_score = 10
        elif ff_pct > -20:
            ff_score = 5
        else:
            ff_score = 0
            breakdown["signals"].append("🚨 Heavy foreign selling")
        
        breakdown["foreign_flow_component"] = ff_score
        score += ff_score
    
    # 3. Price-Volume Divergence (Golden Signal from research)
    divergence_score = 10  # Neutral
    
    # Hidden Accumulation: Price flat/down + Strong buying = Premium signal
    if price_trend in ["down", "neutral"] and bcr > 1.2:
        divergence_score = 20
        breakdown["signals"].append("🌟 HIDDEN ACCUMULATION detected - Price weak but buying strong")
    
    # Distribution Warning: Price up + Selling = Danger
    elif price_trend == "up" and bcr < 0.8:
        divergence_score = 0
        breakdown["signals"].append("⚠️ Distribution into strength - Markup distribution phase")
    
    breakdown["divergence_component"] = divergence_score
    score += divergence_score
    
    # 4. Retail Disguise Detection (from research)
    if broker_data.retail_disguise_detected:
        if bcr > 1.2:
            score += 10  # Bonus - disguised accumulation
            breakdown["signals"].append("🕵️ Retail disguise + accumulation = Strong institutional interest")
        else:
            breakdown["signals"].append("⚠️ Retail disguise detected - monitor closely")
    
    score = max(0, min(100, score))
    
    return {
        "score": score,
        "breakdown": breakdown,
        "confidence": 0.8 if broker_data.source == "api" else 0.6,
        "notes": breakdown["signals"]
    }


# ============================================================================
# ALPHA-V TOTAL SCORE CALCULATION
# ============================================================================

def calculate_alpha_v_score(
    ticker: str,
    financial_data: Optional[FinancialReportData] = None,
    broker_data: Optional[BrokerSummaryData] = None,
    current_price: float = None,
    sector: str = "Default",
    price_trend: str = "neutral",
    volume_trend: str = "neutral"
) -> AlphaVScore:
    """
    Calculate comprehensive Alpha-V Score.
    
    Formula: TS = (0.3 × F) + (0.2 × Q) + (0.5 × S)
    
    Returns AlphaVScore with grade and strategy recommendation.
    """
    # Calculate component scores
    f_result = calculate_fundamental_score(financial_data, current_price, sector)
    q_result = calculate_quality_score(financial_data)
    s_result = calculate_smart_money_score(broker_data, price_trend, volume_trend)
    
    f_score = f_result["score"]
    q_score = q_result["score"]
    s_score = s_result["score"]
    
    # Weights from research
    w_f = 0.30
    w_q = 0.20
    w_s = 0.50
    
    # Calculate total
    total_score = (w_f * f_score) + (w_q * q_score) + (w_s * s_score)
    
    # Determine grade
    if total_score >= 80:
        grade = AlphaVGrade.A
        strategy = "Aggressive Buy - High Conviction opportunity"
    elif total_score >= 60:
        grade = AlphaVGrade.B
        strategy = "Buy on Dip - Momentum play with institutional support"
    elif total_score >= 40:
        grade = AlphaVGrade.C
        strategy = "Watchlist - Wait for clearer signals"
    elif total_score >= 20:
        grade = AlphaVGrade.D
        strategy = "Avoid - Value trap characteristics detected"
    else:
        grade = AlphaVGrade.E
        strategy = "Sell/Short - Toxic or distribution phase"
    
    # Calculate confidence
    confidence = (f_result["confidence"] + q_result["confidence"] + s_result["confidence"]) / 3
    
    # Compile data sources
    data_sources = []
    if financial_data:
        data_sources.append(f"Financial: {financial_data.source}")
    if broker_data:
        data_sources.append(f"Broker: {broker_data.source}")
    
    # Compile notes
    confidence_notes = []
    confidence_notes.extend(f_result.get("notes", []))
    confidence_notes.extend(q_result.get("notes", []))
    confidence_notes.extend(s_result.get("notes", []))
    
    return AlphaVScore(
        ticker=ticker.upper(),
        calculated_at=datetime.now().isoformat(),
        fundamental_score=round(f_score, 1),
        quality_score=round(q_score, 1),
        smart_money_score=round(s_score, 1),
        weight_fundamental=w_f,
        weight_quality=w_q,
        weight_smart_money=w_s,
        total_score=round(total_score, 1),
        grade=grade,
        strategy=strategy,
        fundamental_breakdown=f_result["breakdown"],
        quality_breakdown=q_result["breakdown"],
        smart_money_breakdown=s_result["breakdown"],
        data_sources=data_sources,
        confidence=round(confidence, 2),
        confidence_notes=confidence_notes
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_grade_color(grade: AlphaVGrade) -> str:
    """Get display color for grade"""
    colors = {
        AlphaVGrade.A: "#00FF88",  # Bright green
        AlphaVGrade.B: "#88FF00",  # Yellow-green
        AlphaVGrade.C: "#FFCC00",  # Yellow
        AlphaVGrade.D: "#FF8800",  # Orange
        AlphaVGrade.E: "#FF0044",  # Red
    }
    return colors.get(grade, "#888888")


def get_grade_label(grade: AlphaVGrade) -> str:
    """Get display label for grade"""
    labels = {
        AlphaVGrade.A: "High Conviction",
        AlphaVGrade.B: "Momentum Play",
        AlphaVGrade.C: "Watchlist",
        AlphaVGrade.D: "Value Trap",
        AlphaVGrade.E: "Toxic",
    }
    return labels.get(grade, "Unknown")
