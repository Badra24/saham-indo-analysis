"""
Data Models for File Upload and Parsing

Pydantic models for:
- Broker Summary data (from uploaded CSV/PDF)
- Financial Report data (from uploaded reports)
- Alpha-V Scoring results
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class FileType(str, Enum):
    """Supported file types for upload"""
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    UNKNOWN = "unknown"


class BrokerType(str, Enum):
    """Broker classification based on research"""
    INSTITUTIONAL_FOREIGN = "institutional_foreign"  # AK, BK, ZP, KZ, RX, MS
    INSTITUTIONAL_LOCAL = "institutional_local"      # MG, RF
    RETAIL_PLATFORM = "retail_platform"              # XL, XC, YP, PD, CC, NI
    UNKNOWN = "unknown"


class BrokerEntry(BaseModel):
    """Individual broker entry with transaction details"""
    broker_code: str = Field(..., description="Broker code (e.g., XL, AK, ZP)")
    broker_name: Optional[str] = Field(None, description="Full broker name")
    broker_type: BrokerType = Field(BrokerType.UNKNOWN, description="Classification")
    buy_value: float = Field(0, description="Total buy value in IDR")
    sell_value: float = Field(0, description="Total sell value in IDR")
    buy_volume: float = Field(0, description="Total buy volume in lots")
    sell_volume: float = Field(0, description="Total sell volume in lots")
    net_value: float = Field(0, description="Net value (buy - sell)")
    net_volume: float = Field(0, description="Net volume (buy - sell)")
    avg_buy_price: Optional[float] = Field(None, description="Average buy price")
    avg_sell_price: Optional[float] = Field(None, description="Average sell price")
    is_foreign: bool = Field(False, description="Is foreign broker")


class BrokerSummaryData(BaseModel):
    """
    Parsed broker summary data from uploaded file.
    Contains all information needed for Bandarmology analysis.
    """
    ticker: str = Field(..., description="Stock ticker symbol")
    date: str = Field(..., description="Trading date (YYYY-MM-DD)")
    source: str = Field("upload", description="Data source: api, upload, cache")
    
    # Broker lists
    top_buyers: List[BrokerEntry] = Field(default_factory=list)
    top_sellers: List[BrokerEntry] = Field(default_factory=list)
    
    # Calculated metrics (from research)
    bcr: float = Field(0, description="Broker Concentration Ratio")
    bcr_interpretation: str = Field("NEUTRAL", description="BCR interpretation")
    
    # Foreign flow metrics
    foreign_buy: float = Field(0, description="Total foreign buy value")
    foreign_sell: float = Field(0, description="Total foreign sell value")
    net_foreign_flow: float = Field(0, description="Net foreign flow")
    foreign_flow_pct: float = Field(0, description="Foreign flow as % of total volume")
    
    # Smart Money Flow Score (from Alpha-V research)
    smf_score: float = Field(0, description="Smart Money Flow score 0-100")
    
    # Retail disguise detection (from Bandar research)
    retail_disguise_detected: bool = Field(False)
    retail_disguise_signals: List[str] = Field(default_factory=list)
    
    # Phase detection
    phase: str = Field("UNKNOWN", description="ACCUMULATION, DISTRIBUTION, NEUTRAL, UNKNOWN")
    phase_confidence: float = Field(0, description="Phase detection confidence 0-1")
    
    # Raw data
    total_buy: float = Field(0, description="Explicit total buy value from all rows")
    total_sell: float = Field(0, description="Explicit total sell value from all rows")
    total_transaction_value: float = Field(0)
    total_transaction_volume: float = Field(0)
    
    # Metadata
    file_name: Optional[str] = Field(None)
    parsed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class FinancialReportData(BaseModel):
    """
    Parsed financial report data from uploaded file.
    Contains metrics needed for Alpha-V Fundamental and Quality scores.
    """
    ticker: str = Field(..., description="Stock ticker symbol")
    period: str = Field(..., description="Report period (e.g., Q3 2025, FY 2024)")
    report_type: str = Field("quarterly", description="quarterly, annual, interim")
    source: str = Field("upload", description="Data source")
    
    # Valuation Metrics (for Fundamental Score)
    per: Optional[float] = Field(None, description="Price to Earnings Ratio")
    pbv: Optional[float] = Field(None, description="Price to Book Value")
    pcf: Optional[float] = Field(None, description="Price to Cash Flow")
    ev_ebitda: Optional[float] = Field(None, description="EV/EBITDA")
    peg: Optional[float] = Field(None, description="PEG Ratio")
    
    # Profitability Metrics
    roe: Optional[float] = Field(None, description="Return on Equity %")
    roa: Optional[float] = Field(None, description="Return on Assets %")
    npm: Optional[float] = Field(None, description="Net Profit Margin %")
    opm: Optional[float] = Field(None, description="Operating Profit Margin %")
    
    # Quality Metrics (for Quality Score)
    ocf: Optional[float] = Field(None, description="Operating Cash Flow")
    net_income: Optional[float] = Field(None, description="Net Income")
    ocf_to_net_income: Optional[float] = Field(None, description="OCF/Net Income ratio")
    
    # Solvency Metrics
    der: Optional[float] = Field(None, description="Debt to Equity Ratio")
    current_ratio: Optional[float] = Field(None, description="Current Ratio")
    quick_ratio: Optional[float] = Field(None, description="Quick Ratio")
    
    # Growth Metrics
    revenue_growth: Optional[float] = Field(None, description="Revenue growth YoY %")
    earnings_growth: Optional[float] = Field(None, description="Earnings growth YoY %")
    
    # Sector context
    sector: Optional[str] = Field(None, description="IDX sector classification")
    sector_avg_per: Optional[float] = Field(None, description="Sector average PER")
    sector_avg_pbv: Optional[float] = Field(None, description="Sector average PBV")
    
    # Z-Scores (for relative valuation)
    per_zscore: Optional[float] = Field(None, description="PER Z-score vs 5-year history")
    pbv_zscore: Optional[float] = Field(None, description="PBV Z-score vs 5-year history")
    
    # Metadata
    file_name: Optional[str] = Field(None)
    parsed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AlphaVGrade(str, Enum):
    """Alpha-V grade classification from research"""
    A = "A"  # 80-100: High Conviction - Aggressive Buy
    B = "B"  # 60-79: Momentum Play - Buy on Dip
    C = "C"  # 40-59: Watchlist - Wait & See
    D = "D"  # 20-39: Value Trap - Avoid
    E = "E"  # 0-19: Toxic/Distribution - Sell/Short


class AlphaVScore(BaseModel):
    """
    Alpha-V Hybrid Scoring System results.
    
    Formula: TS = (0.3 × F) + (0.2 × Q) + (0.5 × S)
    
    Where:
    - F = Fundamental Score (0-100)
    - Q = Quality Score (0-100)  
    - S = Smart Money Flow Score (0-100)
    """
    ticker: str
    calculated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Component Scores
    fundamental_score: float = Field(0, ge=0, le=100, description="F: Fundamental Score")
    quality_score: float = Field(0, ge=0, le=100, description="Q: Quality Score")
    smart_money_score: float = Field(0, ge=0, le=100, description="S: Smart Money Flow Score")
    
    # Weights (from research)
    weight_fundamental: float = Field(0.3)
    weight_quality: float = Field(0.2)
    weight_smart_money: float = Field(0.5)
    
    # Total Score
    total_score: float = Field(0, ge=0, le=100, description="Weighted total score")
    grade: AlphaVGrade = Field(AlphaVGrade.C, description="Grade A-E")
    
    # Strategy recommendation
    strategy: str = Field("Wait & See", description="Recommended action")
    
    # Score breakdown details
    fundamental_breakdown: Dict[str, Any] = Field(default_factory=dict)
    quality_breakdown: Dict[str, Any] = Field(default_factory=dict)
    smart_money_breakdown: Dict[str, Any] = Field(default_factory=dict)
    
    # Data sources used
    data_sources: List[str] = Field(default_factory=list)
    
    # Confidence
    confidence: float = Field(0, ge=0, le=1, description="Overall confidence 0-1")
    confidence_notes: List[str] = Field(default_factory=list)


class FileUploadResponse(BaseModel):
    """Response model for file upload endpoints"""
    success: bool
    message: str
    file_type: FileType
    file_name: str
    parsed_data: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ComprehensiveAnalysis(BaseModel):
    """
    Comprehensive conviction analysis combining all data sources.
    Integrates chart data, indicators, broker summary, and Alpha-V scoring.
    """
    ticker: str
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Alpha-V Score
    alpha_v: AlphaVScore
    
    # Broker Summary
    broker_summary: Optional[BrokerSummaryData] = None
    
    # Financial Data
    financial_data: Optional[FinancialReportData] = None
    
    # Technical Analysis
    technical_signals: Dict[str, Any] = Field(default_factory=dict)
    
    # Order Flow
    order_flow: Dict[str, Any] = Field(default_factory=dict)
    
    # AI Insights
    ai_analysis: Optional[str] = None
    ai_model_used: Optional[str] = None
    
    # Data completeness
    data_completeness: float = Field(0, description="% of data available 0-100")
    missing_data: List[str] = Field(default_factory=list)
    
    # Final recommendation
    conviction_level: str = Field("LOW", description="LOW, MEDIUM, HIGH, VERY_HIGH")
    action: str = Field("HOLD", description="BUY, SELL, HOLD, AVOID")
    rationale: List[str] = Field(default_factory=list)
