"""
Telegram Alert Engine for Saham Indonesia Analysis

Sends real-time alerts for:
- Wyckoff Spring/UTAD patterns
- Silent Accumulation detection
- Unusual broker activity
- Price breakout/breakdown signals

Reference: Research Thesis Section 9 - Alert Engine Architecture
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# Lazy import to avoid dependency issues
try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    TelegramError = Exception

logger = logging.getLogger(__name__)


class AlertType(Enum):
    SPRING = "🔥 SPRING"
    UTAD = "⛔ UTAD"
    BREAKOUT = "🚀 BREAKOUT"
    BREAKDOWN = "📉 BREAKDOWN"
    ACCUMULATION = "💰 ACCUMULATION"
    DISTRIBUTION = "⚠️ DISTRIBUTION"
    UNUSUAL_VOLUME = "📊 UNUSUAL VOLUME"
    BANDAR_ALERT = "🏦 BANDAR ALERT"
    CHURN_WARNING = "🔄 CHURN WARNING"


@dataclass
class Alert:
    """Alert message structure."""
    type: AlertType
    symbol: str
    title: str
    message: str
    priority: str  # HIGH, MEDIUM, LOW
    price: Optional[float] = None
    target: Optional[float] = None
    stop_loss: Optional[float] = None
    broker_info: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AlertEngine:
    """
    Telegram-based Alert Engine for stock market signals.
    
    Features:
    - Rate limiting (max 20 alerts/minute per chat)
    - Alert deduplication (no duplicate alerts within 1 hour)
    - Priority-based formatting
    - Rich message formatting with emojis
    
    Usage:
        engine = AlertEngine()
        await engine.send_alert(alert)
    """
    
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.token and self.chat_id and TELEGRAM_AVAILABLE)
        
        # Rate limiting
        self._last_alerts: List[datetime] = []
        self._rate_limit = 20  # max alerts per minute
        
        # Deduplication cache (symbol -> last alert time)
        self._alert_cache: Dict[str, Dict[str, datetime]] = {}
        self._cache_duration = timedelta(hours=1)
        
        if self.enabled:
            self.bot = Bot(token=self.token)
            logger.info("Telegram Alert Engine initialized")
        else:
            self.bot = None
            if not TELEGRAM_AVAILABLE:
                logger.warning("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            elif not self.token:
                logger.warning("TELEGRAM_BOT_TOKEN not configured")
            elif not self.chat_id:
                logger.warning("TELEGRAM_CHAT_ID not configured")
    
    async def send_alert(self, alert: Alert) -> bool:
        """
        Send alert to Telegram.
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Alert not sent (Telegram disabled): {alert.symbol} - {alert.title}")
            return False
        
        # Rate limiting check
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded, alert dropped")
            return False
        
        # Deduplication check
        if self._is_duplicate(alert):
            logger.debug(f"Duplicate alert ignored: {alert.symbol} - {alert.type.value}")
            return False
        
        try:
            message = self._format_message(alert)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            # Update caches
            self._record_alert(alert)
            logger.info(f"Alert sent: {alert.symbol} - {alert.type.value}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram send error: {e}")
            return False
        except Exception as e:
            logger.error(f"Alert send error: {e}")
            return False
    
    def send_alert_sync(self, alert: Alert) -> bool:
        """Synchronous wrapper for send_alert."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, schedule it
                asyncio.create_task(self.send_alert(alert))
                return True
            else:
                return loop.run_until_complete(self.send_alert(alert))
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(self.send_alert(alert))
    
    def _format_message(self, alert: Alert) -> str:
        """Format alert as rich Telegram message."""
        lines = []
        
        # Header with type and symbol
        lines.append(f"<b>{alert.type.value} - {alert.symbol}</b>")
        lines.append("")
        
        # Title and message
        lines.append(f"📢 <b>{alert.title}</b>")
        lines.append(alert.message)
        lines.append("")
        
        # Price info if available
        if alert.price:
            lines.append(f"💵 Price: Rp {alert.price:,.0f}")
        if alert.target:
            lines.append(f"🎯 Target: Rp {alert.target:,.0f}")
        if alert.stop_loss:
            lines.append(f"🛑 Stop Loss: Rp {alert.stop_loss:,.0f}")
        
        # Broker info
        if alert.broker_info:
            lines.append("")
            lines.append(f"🏦 {alert.broker_info}")
        
        # Priority indicator
        priority_emoji = {
            "HIGH": "🔴",
            "MEDIUM": "🟡",
            "LOW": "🟢"
        }
        lines.append("")
        lines.append(f"{priority_emoji.get(alert.priority, '⚪')} Priority: {alert.priority}")
        
        # Timestamp
        lines.append(f"⏰ {alert.timestamp.strftime('%Y-%m-%d %H:%M WIB')}")
        
        # Disclaimer
        lines.append("")
        lines.append("<i>⚠️ This is an automated alert. Do your own research.</i>")
        
        return "\n".join(lines)
    
    def _check_rate_limit(self) -> bool:
        """Check if within rate limit."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        
        # Clean old entries
        self._last_alerts = [t for t in self._last_alerts if t > cutoff]
        
        if len(self._last_alerts) >= self._rate_limit:
            return False
        
        self._last_alerts.append(now)
        return True
    
    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if this is a duplicate alert."""
        key = f"{alert.symbol}:{alert.type.value}"
        
        if alert.symbol not in self._alert_cache:
            return False
        
        last_time = self._alert_cache[alert.symbol].get(alert.type.value)
        if not last_time:
            return False
        
        return datetime.now() - last_time < self._cache_duration
    
    def _record_alert(self, alert: Alert):
        """Record alert for deduplication."""
        if alert.symbol not in self._alert_cache:
            self._alert_cache[alert.symbol] = {}
        
        self._alert_cache[alert.symbol][alert.type.value] = datetime.now()
    
    # Factory methods for common alerts
    
    @staticmethod
    def create_spring_alert(symbol: str, support_level: float, current_price: float,
                           top_buyer: str, buy_value: float) -> Alert:
        """Create a Spring detection alert."""
        return Alert(
            type=AlertType.SPRING,
            symbol=symbol,
            title="Wyckoff Spring Detected!",
            message=f"Price broke below support Rp {support_level:,.0f} and recovered.\n"
                   f"This is a classic accumulation shakeout pattern.",
            priority="HIGH",
            price=current_price,
            target=round(current_price * 1.10),  # 10% target
            stop_loss=round(support_level * 0.97),  # 3% below support
            broker_info=f"Top Buyer: {top_buyer} (Rp {buy_value/1e9:.1f}B)"
        )
    
    @staticmethod
    def create_utad_alert(symbol: str, resistance_level: float, current_price: float,
                         top_seller: str, sell_value: float) -> Alert:
        """Create a UTAD detection alert."""
        return Alert(
            type=AlertType.UTAD,
            symbol=symbol,
            title="UTAD Warning - Bull Trap!",
            message=f"Price broke above resistance Rp {resistance_level:,.0f} but failed.\n"
                   f"Smart money is distributing. Avoid buying!",
            priority="HIGH",
            price=current_price,
            broker_info=f"Top Seller: {top_seller} (Rp {sell_value/1e9:.1f}B)"
        )
    
    @staticmethod
    def create_accumulation_alert(symbol: str, aqs_score: float, grade: str,
                                  concentration: float, message: str) -> Alert:
        """Create silent accumulation alert."""
        return Alert(
            type=AlertType.ACCUMULATION,
            symbol=symbol,
            title=f"Silent Accumulation - Grade {grade}",
            message=message,
            priority="MEDIUM" if aqs_score >= 70 else "LOW",
            broker_info=f"AQS: {aqs_score:.1f}% | Concentration: {concentration:.1%}"
        )
    
    @staticmethod
    def create_churn_alert(symbol: str, churn_ratio: float, level: str,
                           price_change: float) -> Alert:
        """Create churn/wash trading warning."""
        return Alert(
            type=AlertType.CHURN_WARNING,
            symbol=symbol,
            title=f"Churn Warning - {level}",
            message=f"Churn ratio {churn_ratio:.1f}x detected.\n"
                   f"Price change: {price_change:+.1f}%\n"
                   f"High churning may indicate wash trading or distribution.",
            priority="HIGH" if level in ["HIGH", "EXTREME"] else "MEDIUM"
        )


# Singleton instance
_engine_instance = None

def get_alert_engine() -> AlertEngine:
    """Get or create singleton alert engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AlertEngine()
    return _engine_instance


# Quick send functions

async def send_spring_alert(symbol: str, support: float, price: float,
                           buyer: str, value: float) -> bool:
    """Quick function to send spring alert."""
    engine = get_alert_engine()
    alert = AlertEngine.create_spring_alert(symbol, support, price, buyer, value)
    return await engine.send_alert(alert)


async def send_utad_alert(symbol: str, resistance: float, price: float,
                         seller: str, value: float) -> bool:
    """Quick function to send UTAD alert."""
    engine = get_alert_engine()
    alert = AlertEngine.create_utad_alert(symbol, resistance, price, seller, value)
    return await engine.send_alert(alert)
