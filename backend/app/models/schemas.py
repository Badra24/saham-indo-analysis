from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union


# Enriched broker data (new format from GoAPI)
class EnrichedBrokerData(BaseModel):
    code: str
    name: str
    type: str = "UNKNOWN"  # INSTITUTION, RETAIL, MIXED, UNKNOWN
    value: float = 0
    volume: int = 0
    is_foreign: bool = False
    weight: int = 0


class BandarmologyData(BaseModel):
    status: str
    signal_strength: int = 0
    top_buyers: List[Union[str, EnrichedBrokerData, Dict[str, Any]]] = []
    top_sellers: List[Union[str, EnrichedBrokerData, Dict[str, Any]]] = []
    concentration_ratio: float = 0.0
    dominant_player: str = "UNKNOWN"
    institutional_net_flow: float = 0
    retail_net_flow: float = 0
    foreign_net_flow: float = 0
    buy_value: float = 0
    sell_value: float = 0
    net_flow: float = 0
    churn_detected: bool = False
    churning_brokers: List[Dict[str, Any]] = []
    is_demo: bool = False

# New: Order Book Level for Level 2 data
class OrderBookLevelData(BaseModel):
    price: float
    volume: int
    queue_count: int = 1


# New: Order Flow Analysis Data (OBI, HAKA/HAKI)
class OrderFlowData(BaseModel):
    """Order flow analysis result from SmartMoneyAnalyzer"""
    obi: float  # Order Book Imbalance: -1.0 to 1.0
    obi_interpretation: str
    haka_volume: int  # Aggressive buy volume
    haki_volume: int  # Aggressive sell volume
    net_flow: int  # HAKA - HAKI
    flow_ratio: float  # HAKA / (HAKA + HAKI)
    last_trade_classification: Optional[str] = None
    iceberg_detected: bool = False
    iceberg_details: Optional[Dict[str, Any]] = None
    institutional_levels: Optional[Dict[str, List[Dict]]] = None
    hidden_volume_estimate: int = 0
    divergence_detected: bool = False
    divergence_message: str = ""
    sweep_detected: bool = False
    signal: str  # "ACCUMULATION", "DISTRIBUTION", "NEUTRAL", "SPOOFING_DETECTED"
    signal_strength: float  # 0.0 to 1.0
    signal_strength: float  # 0.0 to 1.0
    recommendation: str
    order_book: Optional[Dict[str, Any]] = None  # New: Pass simulated order book to frontend


# New: Trading Signal for Looping Strategy
class TradingSignal(BaseModel):
    """Trading signal from strategy engine"""
    action: str  # "BUY", "SELL", "HOLD", "RE_ENTRY", "EXIT"
    confidence: float  # 0.0 to 1.0
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: float = 0.0  # Based on 30-30-40 pyramiding
    phase: str = "SCOUT"  # "SCOUT" (30%), "CONFIRM" (30%), "ATTACK" (40%)
    reasoning: str
    obi_signal: str = ""
    iceberg_support: bool = False


# New: Risk Management Status
class RiskStatus(BaseModel):
    """Current risk status for kill switch monitoring"""
    daily_pnl: float = 0.0
    daily_pnl_percent: float = 0.0
    kill_switch_active: bool = False
    remaining_risk_budget: float = 0.025  # Default 2.5%
    positions_count: int = 0
    total_exposure: float = 0.0
    max_drawdown: float = 0.0
    message: str = ""


# New: Position for tracking
class Position(BaseModel):
    """Individual position in portfolio"""
    ticker: str
    entry_price: float
    current_price: float
    quantity: int
    entry_time: str
    pnl: float = 0.0
    pnl_percent: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_phase: str = "SCOUT"


# New: Alpha-V Score Data
class AlphaVScoreData(BaseModel):
    total_score: float
    grade: str
    fundamental_score: float
    quality_score: float
    smart_money_score: float
    strategy: str


# New: ML Engine Analysis Data
class MLAnalysisData(BaseModel):
    is_anomaly: bool
    score: float
    description: str
    engine: str = "Isolation Forest"


class MarketData(BaseModel):
    ticker: str
    price: float
    market_cap: float = 0.0
    free_float_ratio: float = 0.5
    fol: float = 1.0
    atr: float = 0.0
    macd: float = 0.0
    rsi: float = 50.0  # New: RSI indicator
    vwap: float = 0.0  # New: VWAP
    volatility: float = 0.02
    description: Optional[str] = None
    historical_prices: List[Any] = []
    bandarmology: Optional[BandarmologyData] = None
    order_flow: Optional[OrderFlowData] = None  # New: Order flow data
    alpha_v: Optional[AlphaVScoreData] = None   # New: Alpha-V score
    ml_analysis: Optional[MLAnalysisData] = None # New: ML Analysis


class AnalysisResult(BaseModel):
    analyst: str
    score: float
    confidence: float
    reasoning: str
    timestamp: str


class ConsensusResult(BaseModel):
    ticker: str
    current_price: float
    consensus_price: float
    upper_bound: float
    lower_bound: float
    confidence_score: float
    analyst_breakdown: List[AnalysisResult]
    historical_prices: List[Any] = []
    timestamp: str
    order_flow: Optional[OrderFlowData] = None  # New: Include order flow
    trading_signal: Optional[TradingSignal] = None  # New: Trading signal
    alpha_v: Optional[AlphaVScoreData] = None   # New: Alpha-V score
    ml_analysis: Optional[MLAnalysisData] = None # New: ML Analysis
