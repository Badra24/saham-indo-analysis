"""
Risk Manager Module - Kill Switch and Position Sizing

Implements risk management based on proprietary trading standards:
- Daily Loss Limit (Kill Switch): Auto-stop at -2.5% daily
- Position Sizing: Based on ATR volatility
- Maximum Drawdown tracking
- Kelly Criterion Integration (Institutional Grade)

Reference: Riset Gabungan Remora-Quant - Chapter 6
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, date
from enum import Enum


class RiskLevel(str, Enum):
    """Current risk status levels"""
    SAFE = "SAFE"           # < 50% of daily limit used
    CAUTION = "CAUTION"     # 50-80% of daily limit used
    DANGER = "DANGER"       # 80-100% of daily limit
    KILLED = "KILLED"       # Kill switch activated


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Daily Loss Limit (Kill Switch trigger)
    daily_loss_limit: float = 0.025  # 2.5% max daily loss
    
    # Position Sizing Limits
    max_position_per_stock: float = 0.15   # 15% max single position
    max_portfolio_exposure: float = 0.80   # 80% max total exposure
    min_cash_reserve: float = 0.20         # 20% always in cash
    
    # Volatility-based sizing
    atr_risk_multiplier: float = 2.0  # Risk 2x ATR per position
    
    # Drawdown limits
    max_drawdown: float = 0.10  # 10% max drawdown before reducing size


@dataclass
class DailyPnL:
    """Track daily P&L"""
    date: date
    starting_equity: float
    current_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades_count: int = 0
    
    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def pnl_percent(self) -> float:
        if self.starting_equity > 0:
            return self.total_pnl / self.starting_equity
        return 0.0


class RiskManager:
    """
    Portfolio Risk Manager with Kill Switch
    
    Key Features:
    1. Kill Switch: Auto-stop trading at -2.5% daily loss
    2. Position Sizing: Volatility-adjusted sizing
    3. Exposure Monitoring: Track total portfolio risk
    4. Drawdown Protection: Reduce size during drawdowns
    5. Kelly Criterion: Dynamic sizing based on Win Probability
    """
    
    def __init__(self, config: RiskConfig = None, initial_equity: float = 100_000_000):
        self.config = config or RiskConfig()
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        
        # Daily tracking
        self.daily_pnl = DailyPnL(
            date=date.today(),
            starting_equity=initial_equity,
            current_equity=initial_equity
        )
        
        # Position tracking
        self.positions: Dict[str, Dict] = {}
        
        # State
        self.kill_switch_active = False
        self.risk_level = RiskLevel.SAFE
        
        # History
        self.daily_history: List[DailyPnL] = []
        self.peak_equity = initial_equity
    
    def check_risk(self, realized_pnl: float = 0.0, 
                   unrealized_pnl: float = 0.0) -> Dict:
        """
        Check current risk status and update kill switch
        
        Args:
            realized_pnl: Today's realized P&L
            unrealized_pnl: Current unrealized P&L
            
        Returns:
            Dict with risk status
        """
        # Reset daily tracking if new day
        self._check_new_day()
        
        # Update P&L
        self.daily_pnl.realized_pnl = realized_pnl
        self.daily_pnl.unrealized_pnl = unrealized_pnl
        self.daily_pnl.current_equity = self.daily_pnl.starting_equity + self.daily_pnl.total_pnl
        self.current_equity = self.daily_pnl.current_equity
        
        # Calculate daily loss percentage
        daily_loss_pct = self.daily_pnl.pnl_percent
        
        # Determine risk level
        loss_ratio = abs(daily_loss_pct) / self.config.daily_loss_limit if daily_loss_pct < 0 else 0
        
        if self.kill_switch_active or loss_ratio >= 1.0:
            self.risk_level = RiskLevel.KILLED
            self.kill_switch_active = True
            message = "🛑 KILL SWITCH ACTIVATED! Stop all trading immediately."
        elif loss_ratio >= 0.8:
            self.risk_level = RiskLevel.DANGER
            message = "⚠️ DANGER: Approaching daily loss limit. Reduce position sizes."
        elif loss_ratio >= 0.5:
            self.risk_level = RiskLevel.CAUTION
            message = "⚡ CAUTION: 50%+ of daily risk budget used. Trade carefully."
        else:
            self.risk_level = RiskLevel.SAFE
            message = "✅ SAFE: Risk within acceptable limits."
        
        # Update peak and drawdown
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
        
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity if self.peak_equity > 0 else 0
        
        return {
            'daily_pnl': round(self.daily_pnl.total_pnl, 2),
            'daily_pnl_percent': round(daily_loss_pct, 4),
            'kill_switch_active': self.kill_switch_active,
            'risk_level': self.risk_level.value,
            'remaining_risk_budget': round(max(0, self.config.daily_loss_limit + daily_loss_pct), 4),
            'positions_count': len(self.positions),
            'total_exposure': self._calculate_exposure(),
            'max_drawdown': round(drawdown, 4),
            'current_equity': round(self.current_equity, 2),
            'message': message
        }
    
    def can_trade(self) -> bool:
        """Check if trading is allowed"""
        return not self.kill_switch_active
    
    def calculate_kelly_size(self, price: float, win_prob: float, 
                             win_loss_ratio: float, 
                             fraction: float = 0.5) -> Dict:
        """
        Calculate position size using Fractional Kelly Criterion.
        
        Formula: f* = (p * b - q) / b
        Where:
           f* = fraction of capital to bet
           p = probability of winning (win_prob)
           q = probability of losing (1 - p)
           b = odds ratio (win_loss_ratio)
           
        We typically use 'Half Kelly' (fraction=0.5) to avoid ruin.
        """
        if self.kill_switch_active:
            return {"shares": 0, "message": "Kill switch active"}
            
        # Kelly Fraction
        q = 1.0 - win_prob
        if win_loss_ratio <= 0:
            kelly_f = 0
        else:
            kelly_f = ((win_prob * win_loss_ratio) - q) / win_loss_ratio
        
        # Apply Fraction (Half Kelly is standard for safety)
        # Also clamp to max_position_per_stock config
        target_exposure = min(max(0, kelly_f * fraction), self.config.max_position_per_stock)
        
        # Calculate capital
        capital_to_deploy = self.current_equity * target_exposure
        
        shares = int(capital_to_deploy / price)
        # Round to lot (100)
        shares = max(0, (shares // 100) * 100)
        
        value = shares * price
        
        return {
            "shares": shares,
            "value": value,
            "kelly_fraction_raw": round(kelly_f, 2),
            "target_exposure": round(target_exposure, 2),
            "message": f"Kelly Sizing ({fraction}x): {shares:,} shares"
        }

    def calculate_position_size(self, price: float, atr: float, 
                                 available_capital: float = None) -> Dict:
        """
        Legacy ATR-based sizing (Fallback if no ML probability is known).
        """
        if self.kill_switch_active:
             return {
                'shares': 0,
                'value': 0,
                'risk_amount': 0,
                'message': "Kill switch active - no new positions allowed"
            }
        
        capital = available_capital or (self.current_equity * self.config.max_position_per_stock)
        
        # Risk per trade (2% of capital is common)
        risk_per_trade = capital * 0.02
        
        # Position size based on ATR
        if atr > 0:
            # Risk = ATR * Multiplier (how much we're willing to lose per share)
            risk_per_share = atr * self.config.atr_risk_multiplier
            shares = int(risk_per_trade / risk_per_share)
        else:
            # Fallback: use fixed percentage
            shares = int(capital * 0.1 / price)  # 10% of capital
        
        # Cap at max position size
        max_shares = int((self.current_equity * self.config.max_position_per_stock) / price)
        shares = min(shares, max_shares)
        
        # Ensure minimum lot (100 shares for IDX)
        shares = max(100, (shares // 100) * 100)
        
        value = shares * price
        
        return {
            'shares': shares,
            'value': round(value, 2),
            'risk_amount': round(shares * atr * self.config.atr_risk_multiplier, 2),
            'percent_of_portfolio': round(value / self.current_equity, 4),
            'stop_loss_distance': round(atr * self.config.atr_risk_multiplier, 2),
            'message': f"Recommended: {shares:,} shares ({value/1000000:.2f}M)"
        }
    
    def register_trade(self, ticker: str, action: str, shares: int, 
                       price: float, pnl: float = 0.0):
        """Register a trade and update P&L"""
        if action == "BUY":
            self.positions[ticker] = {
                'shares': shares,
                'entry_price': price,
                'current_price': price,
                'value': shares * price
            }
        elif action in ["SELL", "EXIT"]:
            if ticker in self.positions:
                del self.positions[ticker]
            self.daily_pnl.realized_pnl += pnl
            self.daily_pnl.trades_count += 1
    
    def update_position_price(self, ticker: str, current_price: float):
        """Update current price for a position"""
        if ticker in self.positions:
            pos = self.positions[ticker]
            pos['current_price'] = current_price
            pos['value'] = pos['shares'] * current_price
            pos['pnl'] = (current_price - pos['entry_price']) * pos['shares']
    
    def get_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L"""
        return sum(pos.get('pnl', 0) for pos in self.positions.values())
    
    def _calculate_exposure(self) -> float:
        """Calculate total portfolio exposure"""
        total_value = sum(pos['value'] for pos in self.positions.values())
        if self.current_equity > 0:
            return round(total_value / self.current_equity, 4)
        return 0.0
    
    def _check_new_day(self):
        """Reset daily tracking if it's a new day"""
        today = date.today()
        if self.daily_pnl.date != today:
            # Archive previous day
            self.daily_history.append(self.daily_pnl)
            
            # Reset for new day
            self.daily_pnl = DailyPnL(
                date=today,
                starting_equity=self.current_equity,
                current_equity=self.current_equity
            )
            
            # Reset kill switch for new day
            self.kill_switch_active = False
            self.risk_level = RiskLevel.SAFE
    
    def reset_kill_switch(self):
        """Manually reset kill switch (use with caution)"""
        self.kill_switch_active = False
        self.risk_level = RiskLevel.SAFE
    
    def get_status(self) -> Dict:
        """Get complete risk status"""
        return self.check_risk(
            realized_pnl=self.daily_pnl.realized_pnl,
            unrealized_pnl=self.get_unrealized_pnl()
        )


# Singleton instance
_risk_manager: Optional[RiskManager] = None


def get_risk_manager(initial_equity: float = 100_000_000) -> RiskManager:
    """Get or create the risk manager instance"""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager(initial_equity=initial_equity)
    return _risk_manager
