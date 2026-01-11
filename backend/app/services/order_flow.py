"""
Order Flow Analysis Module - Core of Remora-Quant System

This module implements market microstructure analysis based on:
- Riset Bandarmologi: OBI, HAKA/HAKI detection
- Riset Hengky Adinata: Smart Money tracking

Key Concepts:
- OBI (Order Book Imbalance): Measures buying vs selling pressure
- HAKA (Hajar Kanan): Aggressive buy hitting the ask
- HAKI (Hajar Kiri): Aggressive sell hitting the bid
- Iceberg Orders: Hidden liquidity detection via refill patterns
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum


class OrderFlowSignal(str, Enum):
    """Trading signals based on order flow analysis"""
    STRONG_ACCUMULATION = "STRONG_ACCUMULATION"   # Whale buying aggressively
    ACCUMULATION = "ACCUMULATION"                  # Smart money accumulating
    NEUTRAL = "NEUTRAL"                            # No clear direction
    DISTRIBUTION = "DISTRIBUTION"                  # Smart money distributing
    STRONG_DISTRIBUTION = "STRONG_DISTRIBUTION"    # Whale selling aggressively
    SPOOFING_DETECTED = "SPOOFING_DETECTED"       # Fake bid/ask detected


@dataclass
class OrderBookLevel:
    """Single level in the order book"""
    price: float
    volume: int
    queue_count: int = 1  # Number of orders at this level
    
    @property
    def avg_order_size(self) -> float:
        """Average order size - high values indicate institutional participation"""
        return self.volume / max(self.queue_count, 1)


@dataclass
class OrderBook:
    """Complete order book snapshot"""
    ticker: str
    timestamp: float
    bids: List[OrderBookLevel] = field(default_factory=list)  # Best bid first
    asks: List[OrderBookLevel] = field(default_factory=list)  # Best ask first
    last_price: float = 0.0
    last_volume: int = 0
    
    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0
    
    @property
    def mid_price(self) -> float:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return self.last_price
    
    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return 0.0
    
    @property
    def spread_percent(self) -> float:
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 100
        return 0.0


class OrderBookImbalanceCalculator:
    """
    Calculate Order Book Imbalance (OBI)
    
    Formula: OBI = (Sum(Bid_Vol) - Sum(Ask_Vol)) / (Sum(Bid_Vol) + Sum(Ask_Vol))
    
    Interpretation:
    - OBI > 0.5: Strong buying pressure (bullish)
    - OBI < -0.5: Strong selling pressure (bearish)
    - OBI near 0: Balanced/neutral
    
    Anomaly Detection:
    - OBI > 0.8 but price not rising = Fake Bid (Spoofing)
    - OBI < -0.8 but price not falling = Fake Ask (Spoofing)
    """
    
    def __init__(self, depth: int = 5):
        """
        Args:
            depth: Number of price levels to analyze (default: 5)
        """
        self.depth = depth
        self.history: List[Dict] = []  # Track OBI history for divergence detection
    
    def calculate(self, order_book: OrderBook) -> float:
        """
        Calculate OBI from order book snapshot
        
        Returns:
            float: OBI value between -1.0 and 1.0
        """
        bid_vol = sum(level.volume for level in order_book.bids[:self.depth])
        ask_vol = sum(level.volume for level in order_book.asks[:self.depth])
        
        total_vol = bid_vol + ask_vol
        if total_vol == 0:
            return 0.0
        
        obi = (bid_vol - ask_vol) / total_vol
        
        # Store in history for later analysis
        self.history.append({
            'timestamp': order_book.timestamp,
            'obi': obi,
            'price': order_book.last_price,
            'bid_vol': bid_vol,
            'ask_vol': ask_vol
        })
        
        # Keep only last 100 data points
        if len(self.history) > 100:
            self.history.pop(0)
        
        return obi
    
    def detect_divergence(self, lookback: int = 10) -> Tuple[bool, str]:
        """
        Detect OBI Divergence (potential spoofing)
        
        Returns:
            Tuple of (is_divergence, description)
        """
        if len(self.history) < lookback:
            return False, "Insufficient data"
        
        recent = self.history[-lookback:]
        avg_obi = np.mean([h['obi'] for h in recent])
        price_change = (recent[-1]['price'] - recent[0]['price']) / recent[0]['price'] if recent[0]['price'] > 0 else 0
        
        # Bullish OBI but price falling = Fake Bid
        if avg_obi > 0.5 and price_change < -0.005:  # OBI bullish but price down 0.5%+
            return True, "FAKE_BID_DETECTED: Strong bid wall but price declining. Possible distribution trap."
        
        # Bearish OBI but price rising = Fake Ask
        if avg_obi < -0.5 and price_change > 0.005:  # OBI bearish but price up 0.5%+
            return True, "FAKE_ASK_DETECTED: Strong ask wall but price rising. Possible accumulation stealth."
        
        return False, "No divergence detected"


class TradeClassifier:
    """
    Lee-Ready Algorithm for Trade Classification
    
    Determines whether a trade was buyer-initiated (HAKA) or seller-initiated (HAKI)
    
    Logic:
    1. If trade_price > midpoint → HAKA (buyer aggressive)
    2. If trade_price < midpoint → HAKI (seller aggressive)
    3. If trade_price == midpoint → Use Tick Test (compare with previous trade)
    """
    
    def __init__(self):
        self.trade_history: List[Dict] = []
        self.haka_volume: int = 0
        self.haki_volume: int = 0
    
    def classify(self, trade_price: float, trade_volume: int, 
                 best_bid: float, best_ask: float) -> str:
        """
        Classify a single trade using Lee-Ready algorithm
        
        Returns:
            "HAKA" for aggressive buy, "HAKI" for aggressive sell
        """
        midpoint = (best_bid + best_ask) / 2 if (best_bid and best_ask) else trade_price
        
        # Primary classification: Quote Rule
        if trade_price > midpoint:
            classification = "HAKA"
        elif trade_price < midpoint:
            classification = "HAKI"
        else:
            # Tick Test: Compare with previous trade
            if self.trade_history:
                prev_price = self.trade_history[-1]['price']
                if trade_price > prev_price:
                    classification = "HAKA"  # Uptick
                elif trade_price < prev_price:
                    classification = "HAKI"  # Downtick
                else:
                    # Use previous classification if no change
                    classification = self.trade_history[-1].get('classification', "NEUTRAL")
            else:
                classification = "NEUTRAL"
        
        # Update volume counters
        if classification == "HAKA":
            self.haka_volume += trade_volume
        elif classification == "HAKI":
            self.haki_volume += trade_volume
        
        # Record trade
        self.trade_history.append({
            'price': trade_price,
            'volume': trade_volume,
            'classification': classification
        })
        
        # Keep only last 500 trades
        if len(self.trade_history) > 500:
            oldest = self.trade_history.pop(0)
            # Adjust counters
            if oldest['classification'] == "HAKA":
                self.haka_volume -= oldest['volume']
            elif oldest['classification'] == "HAKI":
                self.haki_volume -= oldest['volume']
        
        return classification
    
    @property
    def net_flow(self) -> int:
        """Net order flow (positive = buying pressure, negative = selling)"""
        return self.haka_volume - self.haki_volume
    
    @property
    def flow_ratio(self) -> float:
        """Ratio of HAKA to total volume"""
        total = self.haka_volume + self.haki_volume
        return self.haka_volume / total if total > 0 else 0.5
    
    def detect_sweep(self, threshold_trades: int = 10, time_window_ms: int = 1000) -> bool:
        """
        Detect aggressive sweep (institutional buying/selling)
        
        A sweep is when multiple aggressive trades hit the book in quick succession,
        eating through multiple price levels. This is a typical institutional pattern.
        """
        if len(self.trade_history) < threshold_trades:
            return False
        
        recent = self.trade_history[-threshold_trades:]
        
        # All same direction?
        classifications = [t['classification'] for t in recent]
        if len(set(classifications)) == 1 and classifications[0] in ["HAKA", "HAKI"]:
            # Check if volume is significant
            total_vol = sum(t['volume'] for t in recent)
            avg_vol = sum(t['volume'] for t in self.trade_history) / len(self.trade_history)
            
            if total_vol > avg_vol * 3:  # 3x average volume
                return True
        
        return False


class IcebergDetector:
    """
    Iceberg Order Detection
    
    Detects hidden liquidity by monitoring refill patterns in the order book.
    
    Logic:
    1. Track volume at a price level
    2. When trades occur, calculate expected remaining volume
    3. If actual volume > expected (refill occurred), flag as iceberg
    
    Example:
    - Bid at 1000 has 5000 lots
    - Trade of 3000 lots occurs (HAKI)
    - Expected remaining: 2000 lots
    - If actual is 5000 again → Iceberg detected (refill)
    """
    
    def __init__(self):
        self.level_snapshots: Dict[float, int] = {}  # price -> last known volume
        self.iceberg_levels: Dict[float, Dict] = {}  # Detected iceberg levels
        self.hidden_volume_estimate: int = 0
    
    def update(self, order_book: OrderBook, last_trade_price: float, 
               last_trade_volume: int, trade_side: str) -> Optional[Dict]:
        """
        Update detector with new order book snapshot after a trade
        
        Returns:
            Dict with iceberg info if detected, None otherwise
        """
        detection = None
        
        # Check bid side for iceberg (if HAKI trade hit the bid)
        if trade_side == "HAKI" and order_book.bids:
            bid_level = order_book.bids[0]
            if bid_level.price == last_trade_price:
                expected_vol = self.level_snapshots.get(last_trade_price, 0) - last_trade_volume
                actual_vol = bid_level.volume
                
                if actual_vol > expected_vol and expected_vol >= 0:
                    refill_amount = actual_vol - max(expected_vol, 0)
                    if refill_amount > 0:
                        self.hidden_volume_estimate += refill_amount
                        detection = {
                            'type': 'ICEBERG_BID',
                            'price': last_trade_price,
                            'refill_volume': refill_amount,
                            'interpretation': f"Institutional support at {last_trade_price}. Hidden buying detected."
                        }
                        self._record_iceberg(last_trade_price, 'BID', refill_amount)
        
        # Check ask side for iceberg (if HAKA trade hit the ask)
        elif trade_side == "HAKA" and order_book.asks:
            ask_level = order_book.asks[0]
            if ask_level.price == last_trade_price:
                expected_vol = self.level_snapshots.get(last_trade_price, 0) - last_trade_volume
                actual_vol = ask_level.volume
                
                if actual_vol > expected_vol and expected_vol >= 0:
                    refill_amount = actual_vol - max(expected_vol, 0)
                    if refill_amount > 0:
                        self.hidden_volume_estimate += refill_amount
                        detection = {
                            'type': 'ICEBERG_ASK',
                            'price': last_trade_price,
                            'refill_volume': refill_amount,
                            'interpretation': f"Institutional resistance at {last_trade_price}. Hidden selling detected."
                        }
                        self._record_iceberg(last_trade_price, 'ASK', refill_amount)
        
        # Update snapshots for next comparison
        for level in order_book.bids[:5]:
            self.level_snapshots[level.price] = level.volume
        for level in order_book.asks[:5]:
            self.level_snapshots[level.price] = level.volume
        
        return detection
    
    def _record_iceberg(self, price: float, side: str, volume: int):
        """Record iceberg level for analysis"""
        if price not in self.iceberg_levels:
            self.iceberg_levels[price] = {'side': side, 'total_hidden': 0, 'detections': 0}
        
        self.iceberg_levels[price]['total_hidden'] += volume
        self.iceberg_levels[price]['detections'] += 1
    
    def get_institutional_levels(self) -> Dict[str, List[Dict]]:
        """Get significant iceberg levels (support/resistance)"""
        supports = []
        resistances = []
        
        for price, data in self.iceberg_levels.items():
            level_info = {
                'price': price,
                'hidden_volume': data['total_hidden'],
                'detection_count': data['detections'],
                'strength': data['detections'] * data['total_hidden']  # Combined metric
            }
            
            if data['side'] == 'BID':
                supports.append(level_info)
            else:
                resistances.append(level_info)
        
        # Sort by strength
        supports.sort(key=lambda x: x['strength'], reverse=True)
        resistances.sort(key=lambda x: x['strength'], reverse=True)
        
        return {
            'institutional_support': supports[:5],
            'institutional_resistance': resistances[:5]
        }


class SmartMoneyAnalyzer:
    """
    Main analyzer combining all order flow tools
    
    This is the "MM Detector" mentioned in Hengky Adinata's methodology
    """
    
    def __init__(self, depth: int = 5):
        self.obi_calc = OrderBookImbalanceCalculator(depth=depth)
        self.trade_classifier = TradeClassifier()
        self.iceberg_detector = IcebergDetector()
        
        self.signal_history: List[OrderFlowSignal] = []
    
    def analyze(self, order_book: OrderBook, 
                trade_price: float = None, 
                trade_volume: int = None) -> Dict:
        """
        Comprehensive order flow analysis
        
        Returns:
            Dict with all analysis results
        """
        # Calculate OBI
        obi = self.obi_calc.calculate(order_book)
        
        # Classify trade if provided
        trade_class = None
        iceberg_detection = None
        if trade_price and trade_volume:
            trade_class = self.trade_classifier.classify(
                trade_price, trade_volume,
                order_book.best_bid, order_book.best_ask
            )
            iceberg_detection = self.iceberg_detector.update(
                order_book, trade_price, trade_volume, trade_class
            )
        
        # Detect divergence
        is_divergence, divergence_msg = self.obi_calc.detect_divergence()
        
        # Detect sweep pattern
        is_sweep = self.trade_classifier.detect_sweep()
        
        # Determine overall signal
        signal = self._determine_signal(obi, is_divergence, is_sweep, iceberg_detection)
        self.signal_history.append(signal)
        
        # Build result
        result = {
            'obi': round(obi, 4),
            'obi_interpretation': self._interpret_obi(obi),
            'haka_volume': self.trade_classifier.haka_volume,
            'haki_volume': self.trade_classifier.haki_volume,
            'net_flow': self.trade_classifier.net_flow,
            'flow_ratio': round(self.trade_classifier.flow_ratio, 4),
            'last_trade_classification': trade_class,
            'iceberg_detected': iceberg_detection is not None,
            'iceberg_details': iceberg_detection,
            'institutional_levels': self.iceberg_detector.get_institutional_levels(),
            'hidden_volume_estimate': self.iceberg_detector.hidden_volume_estimate,
            'divergence_detected': is_divergence,
            'divergence_message': divergence_msg,
            'sweep_detected': is_sweep,
            'signal': signal.value,
            'signal_strength': self._calculate_signal_strength(obi, is_sweep, iceberg_detection),
            'recommendation': self._generate_recommendation(signal, obi)
        }
        
        return result
    
    def _determine_signal(self, obi: float, is_divergence: bool, 
                          is_sweep: bool, iceberg: Optional[Dict]) -> OrderFlowSignal:
        """Determine trading signal from all factors"""
        
        if is_divergence:
            return OrderFlowSignal.SPOOFING_DETECTED
        
        # Iceberg on bid side = institutional support
        if iceberg and iceberg['type'] == 'ICEBERG_BID':
            if obi > 0.3:
                return OrderFlowSignal.STRONG_ACCUMULATION
            return OrderFlowSignal.ACCUMULATION
        
        # Iceberg on ask side = institutional resistance
        if iceberg and iceberg['type'] == 'ICEBERG_ASK':
            if obi < -0.3:
                return OrderFlowSignal.STRONG_DISTRIBUTION
            return OrderFlowSignal.DISTRIBUTION
        
        # Sweep pattern
        if is_sweep:
            net_flow = self.trade_classifier.net_flow
            if net_flow > 0:
                return OrderFlowSignal.STRONG_ACCUMULATION
            elif net_flow < 0:
                return OrderFlowSignal.STRONG_DISTRIBUTION
        
        # Regular OBI-based signal
        if obi > 0.5:
            return OrderFlowSignal.ACCUMULATION
        elif obi < -0.5:
            return OrderFlowSignal.DISTRIBUTION
        
        return OrderFlowSignal.NEUTRAL
    
    def _interpret_obi(self, obi: float) -> str:
        """Human-readable OBI interpretation"""
        if obi > 0.7:
            return "Very strong buying pressure - institutional accumulation likely"
        elif obi > 0.3:
            return "Moderate buying pressure - bullish bias"
        elif obi > -0.3:
            return "Balanced order flow - no clear direction"
        elif obi > -0.7:
            return "Moderate selling pressure - bearish bias"
        else:
            return "Very strong selling pressure - institutional distribution likely"
    
    def _calculate_signal_strength(self, obi: float, is_sweep: bool, 
                                    iceberg: Optional[Dict]) -> float:
        """Calculate confidence in the signal (0.0 to 1.0)"""
        strength = abs(obi) * 0.5  # OBI contributes 50%
        
        if is_sweep:
            strength += 0.25
        
        if iceberg:
            strength += 0.25
        
        return min(strength, 1.0)
    
    def _generate_recommendation(self, signal: OrderFlowSignal, obi: float) -> str:
        """Generate actionable recommendation"""
        recommendations = {
            OrderFlowSignal.STRONG_ACCUMULATION: "🟢 STRONG BUY SIGNAL: Whale accumulation detected. Consider entry with 30% position (Scout).",
            OrderFlowSignal.ACCUMULATION: "🟢 BUY SIGNAL: Smart money buying. Watch for breakout confirmation.",
            OrderFlowSignal.NEUTRAL: "⚪ HOLD: No clear institutional activity. Wait for direction.",
            OrderFlowSignal.DISTRIBUTION: "🔴 SELL SIGNAL: Smart money distributing. Consider reducing position.",
            OrderFlowSignal.STRONG_DISTRIBUTION: "🔴 STRONG SELL SIGNAL: Whale distribution detected. Exit immediately.",
            OrderFlowSignal.SPOOFING_DETECTED: "⚠️ CAUTION: Possible manipulation detected. Do NOT trade until resolved."
        }
        return recommendations.get(signal, "Analysis inconclusive")


# Factory function for easy creation
def create_analyzer(depth: int = 5) -> SmartMoneyAnalyzer:
    """Create a new SmartMoneyAnalyzer instance"""
    return SmartMoneyAnalyzer(depth=depth)
