"""
Trading Strategy Module - Hengky Adinata's Looping Strategy

Implements the "Remora Trader" methodology:
1. Follow Smart Money (Whale/Bandar) using order flow analysis
2. Looping Strategy: Buy, Partial Sell, Re-entry on pullback
3. 30-30-40 Pyramiding Position Sizing

Reference: Riset Trader Saham Hengky Adinata.docx
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
from datetime import datetime
import math


class StrategyPhase(str, Enum):
    """Position sizing phases following 30-30-40 rule"""
    SCOUT = "SCOUT"      # 30% - Initial position on first signal
    CONFIRM = "CONFIRM"  # 30% - Add on confirmation (breakout/pullback)
    ATTACK = "ATTACK"    # 40% - Full position on strong momentum


class TradeAction(str, Enum):
    """Possible trading actions"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    RE_ENTRY = "RE_ENTRY"  # Looping re-entry
    PARTIAL_EXIT = "PARTIAL_EXIT"
    FULL_EXIT = "FULL_EXIT"


@dataclass
class StrategyConfig:
    """Configuration for the Looping Strategy"""
    # Position Sizing (30-30-40 rule)
    scout_size: float = 0.30      # 30% of available capital
    confirm_size: float = 0.30   # 30% additional
    attack_size: float = 0.40    # 40% final position
    
    # Take Profit / Stop Loss
    take_profit_percent: float = 0.05    # 5% default TP
    stop_loss_percent: float = 0.03      # 3% default SL
    trailing_stop_percent: float = 0.02  # 2% trailing stop
    
    # Looping Parameters
    pullback_threshold: float = 0.02     # 2% pullback for re-entry
    vwap_proximity: float = 0.01         # 1% near VWAP for re-entry
    
    # Risk Parameters
    max_position_per_stock: float = 0.15    # 15% max per stock
    max_portfolio_exposure: float = 0.80    # 80% max total exposure


@dataclass
class PositionState:
    """Current state of a position for strategy calculations"""
    ticker: str
    entry_price: float
    current_price: float
    quantity: int
    phase: StrategyPhase
    entry_time: datetime
    highest_price: float = 0.0  # For trailing stop
    loop_count: int = 0         # Number of looping cycles completed
    
    @property
    def pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity
    
    @property
    def pnl_percent(self) -> float:
        if self.entry_price > 0:
            return (self.current_price - self.entry_price) / self.entry_price
        return 0.0
    
    @property
    def value(self) -> float:
        return self.current_price * self.quantity


class LoopingStrategy:
    """
    Implements Hengky Adinata's Looping Strategy
    
    Core Logic:
    1. Entry when Smart Money accumulation detected (OBI > threshold)
    2. Partial exit at resistance / take profit
    3. Re-entry on pullback to VWAP or support
    4. Repeat (Loop) until trend exhaustion
    
    The key insight is: Don't fully exit a winning trade.
    Instead, loop your profits back into the same stock.
    """
    
    def __init__(self, config: StrategyConfig = None):
        self.config = config or StrategyConfig()
        self.positions: Dict[str, PositionState] = {}
        self.completed_loops: List[Dict] = []
    
    def analyze(self, ticker: str, current_price: float, 
                order_flow_data: Dict, indicators: Dict = None) -> Dict:
        """
        Generate trading signal based on order flow and indicators
        
        Args:
            ticker: Stock ticker
            current_price: Current market price
            order_flow_data: Output from SmartMoneyAnalyzer.analyze()
            indicators: Dict with RSI, VWAP, ATR, etc.
            
        Returns:
            Dict with action, confidence, and position sizing
        """
        indicators = indicators or {}
        
        # Extract key signals
        obi = order_flow_data.get('obi', 0)
        signal = order_flow_data.get('signal', 'NEUTRAL')
        signal_strength = order_flow_data.get('signal_strength', 0)
        iceberg_detected = order_flow_data.get('iceberg_detected', False)
        divergence = order_flow_data.get('divergence_detected', False)
        
        # Get VWAP for re-entry logic
        vwap = indicators.get('vwap', current_price)
        rsi = indicators.get('rsi', 50)
        atr = indicators.get('atr', current_price * 0.02)
        
        # Check existing position
        has_position = ticker in self.positions
        position = self.positions.get(ticker)
        
        # Divergence = Spoofing - DO NOT TRADE
        if divergence:
            return self._create_signal(
                action=TradeAction.HOLD,
                confidence=0.0,
                price=current_price,
                reasoning="⚠️ Spoofing detected (OBI divergence). Avoid trading.",
                obi_signal=signal
            )
        
        # No position - look for entry
        if not has_position:
            return self._analyze_entry(ticker, current_price, obi, signal, 
                                       signal_strength, iceberg_detected, 
                                       vwap, rsi, atr)
        
        # Has position - manage it
        return self._analyze_exit_or_loop(ticker, position, current_price, 
                                          obi, signal, signal_strength,
                                          vwap, rsi, atr)
    
    def _analyze_entry(self, ticker: str, price: float, obi: float,
                       signal: str, strength: float, iceberg: bool,
                       vwap: float, rsi: float, atr: float) -> Dict:
        """Analyze for new entry opportunity"""
        
        # Strong accumulation = Entry signal
        if signal in ["STRONG_ACCUMULATION", "ACCUMULATION"] and strength > 0.4:
            # Iceberg support strengthens the signal
            if iceberg:
                confidence = min(strength + 0.2, 1.0)
                phase = StrategyPhase.CONFIRM  # Skip to confirm if iceberg
            else:
                confidence = strength
                phase = StrategyPhase.SCOUT
            
            # Calculate stop loss and take profit using ATR
            stop_loss = price - (atr * 1.5)  # 1.5x ATR below entry
            take_profit = price + (atr * 3)   # 3x ATR above entry (2:1 risk-reward)
            
            return self._create_signal(
                action=TradeAction.BUY,
                confidence=confidence,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                phase=phase,
                position_size=self._get_position_size(phase),
                reasoning=f"🟢 {signal} detected. OBI={obi:.2f}, Strength={strength:.2f}. "
                         f"{'Iceberg support at this level.' if iceberg else 'Enter SCOUT position.'}",
                obi_signal=signal,
                iceberg_support=iceberg
            )
        
        # Neutral or distribution - no entry
        return self._create_signal(
            action=TradeAction.HOLD,
            confidence=0.0,
            price=price,
            reasoning=f"No entry signal. Current signal: {signal}, OBI={obi:.2f}",
            obi_signal=signal
        )
    
    def _analyze_exit_or_loop(self, ticker: str, position: PositionState,
                              price: float, obi: float, signal: str,
                              strength: float, vwap: float, 
                              rsi: float, atr: float) -> Dict:
        """Analyze for exit, partial exit, or looping re-entry"""
        
        # Update position tracking
        position.current_price = price
        if price > position.highest_price:
            position.highest_price = price
        
        pnl_pct = position.pnl_percent
        
        # Check stop loss (hard exit)
        if pnl_pct < -self.config.stop_loss_percent:
            return self._create_signal(
                action=TradeAction.FULL_EXIT,
                confidence=1.0,
                price=price,
                reasoning=f"🔴 STOP LOSS triggered. PnL: {pnl_pct:.2%}. Exit immediately.",
                obi_signal=signal
            )
        
        # Check distribution signal (exit before dump)
        if signal in ["STRONG_DISTRIBUTION", "DISTRIBUTION"] and strength > 0.5:
            return self._create_signal(
                action=TradeAction.FULL_EXIT,
                confidence=strength,
                price=price,
                reasoning=f"🔴 Distribution detected! OBI={obi:.2f}. Smart money exiting. "
                         f"Exit to protect {pnl_pct:.2%} profit.",
                obi_signal=signal
            )
        
        # In profit - consider partial exit for looping
        if pnl_pct > self.config.take_profit_percent:
            # Trailing stop check
            drawdown_from_high = (position.highest_price - price) / position.highest_price
            if drawdown_from_high > self.config.trailing_stop_percent:
                return self._create_signal(
                    action=TradeAction.PARTIAL_EXIT,
                    confidence=0.8,
                    price=price,
                    position_size=0.5,  # Exit 50% of position
                    reasoning=f"📊 Trailing stop triggered after {pnl_pct:.2%} gain. "
                             f"Take partial profit (50%) and prepare for looping.",
                    obi_signal=signal
                )
        
        # Check for looping re-entry (price near VWAP after pullback)
        vwap_distance = abs(price - vwap) / vwap if vwap > 0 else 1
        pullback_from_high = (position.highest_price - price) / position.highest_price if position.highest_price > 0 else 0
        
        # Re-entry conditions: pullback to VWAP + accumulation resuming
        if (pullback_from_high > self.config.pullback_threshold and 
            vwap_distance < self.config.vwap_proximity and
            signal in ["ACCUMULATION", "STRONG_ACCUMULATION"] and
            position.phase != StrategyPhase.ATTACK):  # Can still add
            
            next_phase = self._get_next_phase(position.phase)
            return self._create_signal(
                action=TradeAction.RE_ENTRY,
                confidence=strength,
                price=price,
                phase=next_phase,
                position_size=self._get_position_size(next_phase),
                reasoning=f"🔄 LOOPING RE-ENTRY! Price pulled back {pullback_from_high:.2%} to VWAP. "
                         f"Accumulation resuming. Add {next_phase.value} position.",
                obi_signal=signal
            )
        
        # Default: Hold
        return self._create_signal(
            action=TradeAction.HOLD,
            confidence=0.5,
            price=price,
            reasoning=f"Hold position. PnL: {pnl_pct:.2%}. Signal: {signal}.",
            obi_signal=signal
        )
    
    def _get_position_size(self, phase: StrategyPhase) -> float:
        """Get position size based on phase"""
        if phase == StrategyPhase.SCOUT:
            return self.config.scout_size
        elif phase == StrategyPhase.CONFIRM:
            return self.config.confirm_size
        elif phase == StrategyPhase.ATTACK:
            return self.config.attack_size
        return 0.0
    
    def _get_next_phase(self, current: StrategyPhase) -> StrategyPhase:
        """Get next phase in pyramiding"""
        if current == StrategyPhase.SCOUT:
            return StrategyPhase.CONFIRM
        elif current == StrategyPhase.CONFIRM:
            return StrategyPhase.ATTACK
        return StrategyPhase.ATTACK  # Already at max
    
    def _create_signal(self, action: TradeAction, confidence: float,
                       price: float, stop_loss: float = None,
                       take_profit: float = None, phase: StrategyPhase = None,
                       position_size: float = 0.0, reasoning: str = "",
                       obi_signal: str = "", iceberg_support: bool = False) -> Dict:
        """Create standardized signal output"""
        return {
            'action': action.value,
            'confidence': round(confidence, 4),
            'entry_price': price if action in [TradeAction.BUY, TradeAction.RE_ENTRY] else None,
            'stop_loss': round(stop_loss, 2) if stop_loss else None,
            'take_profit': round(take_profit, 2) if take_profit else None,
            'position_size': position_size,
            'phase': phase.value if phase else StrategyPhase.SCOUT.value,
            'reasoning': reasoning,
            'obi_signal': obi_signal,
            'iceberg_support': iceberg_support
        }
    
    def register_position(self, ticker: str, entry_price: float, 
                          quantity: int, phase: StrategyPhase = StrategyPhase.SCOUT):
        """Register a new position for tracking"""
        self.positions[ticker] = PositionState(
            ticker=ticker,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            phase=phase,
            entry_time=datetime.now(),
            highest_price=entry_price
        )
    
    def close_position(self, ticker: str, exit_price: float) -> Optional[Dict]:
        """Close position and record the trade"""
        if ticker not in self.positions:
            return None
        
        position = self.positions.pop(ticker)
        position.current_price = exit_price
        
        trade_record = {
            'ticker': ticker,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'quantity': position.quantity,
            'pnl': position.pnl,
            'pnl_percent': position.pnl_percent,
            'loop_count': position.loop_count,
            'entry_time': position.entry_time.isoformat(),
            'exit_time': datetime.now().isoformat()
        }
        
        self.completed_loops.append(trade_record)
        return trade_record


# Singleton instance
_strategy_instance: Optional[LoopingStrategy] = None


def get_strategy() -> LoopingStrategy:
    """Get or create the strategy instance"""
    global _strategy_instance
    if _strategy_instance is None:
        _strategy_instance = LoopingStrategy()
    return _strategy_instance
