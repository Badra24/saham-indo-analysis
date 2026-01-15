"""
Wyckoff Pattern Detection Service

Detects Wyckoff Accumulation/Distribution structures:
- Spring (Accumulation Phase C) - False breakdown below support
- UTAD (Distribution Phase C) - False breakout above resistance
- Breakout Confirmation with Bandarmology validation

Reference: "Audit Strategis dan Peta Jalan Arsitektur" Section 2.2
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WyckoffPattern(Enum):
    SPRING = "SPRING"
    UTAD = "UTAD"
    FAILED_BREAKDOWN = "FAILED_BREAKDOWN"
    FAILED_BREAKOUT = "FAILED_BREAKOUT"
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    NONE = "NONE"


@dataclass
class WyckoffResult:
    pattern: WyckoffPattern
    confidence: str  # HIGH, MEDIUM, LOW
    level: float  # Support or Resistance level
    action: str  # BUY_ZONE, SELL_ZONE, AVOID, WATCH
    bandar_confirmed: bool
    details: Dict


class WyckoffDetector:
    """
    Wyckoff Pattern Detector with Bandarmology Confirmation.
    
    Implements:
    1. Spring Detection (Accumulation Phase C)
    2. UTAD Detection (Distribution Phase C)
    3. Breakout/Breakdown Confirmation
    
    Usage:
        detector = WyckoffDetector()
        result = detector.detect(price_history, broker_data)
    """
    
    def __init__(self, lookback_period: int = 20, sensitivity: int = 5):
        """
        Args:
            lookback_period: Days to look back for pattern detection
            sensitivity: Order parameter for extrema detection (higher = more strict)
        """
        self.lookback_period = lookback_period
        self.sensitivity = sensitivity
    
    def detect(self, price_history: List[Dict], broker_data: Dict) -> WyckoffResult:
        """
        Main detection method - checks for Spring and UTAD patterns.
        
        Args:
            price_history: List of {open, high, low, close, volume} dicts
            broker_data: Current day broker summary with top_buyers/top_sellers
            
        Returns:
            WyckoffResult with pattern, confidence, and action
        """
        if len(price_history) < self.lookback_period:
            return WyckoffResult(
                pattern=WyckoffPattern.NONE,
                confidence="LOW",
                level=0,
                action="INSUFFICIENT_DATA",
                bandar_confirmed=False,
                details={"error": "Need more historical data"}
            )
        
        # Try Spring detection first
        spring_result = self.detect_spring(price_history, broker_data)
        if spring_result.pattern != WyckoffPattern.NONE:
            return spring_result
        
        # Try UTAD detection
        utad_result = self.detect_utad(price_history, broker_data)
        if utad_result.pattern != WyckoffPattern.NONE:
            return utad_result
        
        return WyckoffResult(
            pattern=WyckoffPattern.NONE,
            confidence="LOW",
            level=0,
            action="NO_PATTERN",
            bandar_confirmed=False,
            details={}
        )
    
    def detect_spring(self, price_history: List[Dict], broker_data: Dict) -> WyckoffResult:
        """
        Detect Spring pattern (false breakdown below support).
        
        Spring Conditions:
        1. Price breaks below recent support level
        2. Price recovers and closes above support
        3. Top brokers are net buyers (Bandar confirmation)
        
        Returns:
            WyckoffResult with SPRING or FAILED_BREAKDOWN
        """
        try:
            # Extract price arrays
            lows = np.array([float(c.get('low', c.get('Low', 0))) for c in price_history])
            closes = np.array([float(c.get('close', c.get('Close', 0))) for c in price_history])
            volumes = np.array([float(c.get('volume', c.get('Volume', 0))) for c in price_history])
            
            # Find support levels (local minima)
            support_levels = self._find_local_extrema(lows, mode='min')
            
            if len(support_levels) == 0:
                return WyckoffResult(
                    pattern=WyckoffPattern.NONE,
                    confidence="LOW",
                    level=0,
                    action="NO_SUPPORT_FOUND",
                    bandar_confirmed=False,
                    details={}
                )
            
            # Get most recent support level
            support_level = lows[support_levels[-1]]
            
            # Current bar data
            current_low = lows[-1]
            current_close = closes[-1]
            avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
            current_volume = volumes[-1]
            
            # Check Spring conditions
            broke_support = current_low < support_level * 0.995  # 0.5% tolerance
            recovered = current_close > support_level
            
            if broke_support and recovered:
                # Confirm with Bandarmology
                bandar_result = self._check_bandar_confirmation(broker_data, 'BUY')
                
                # Volume analysis
                volume_spike = current_volume > avg_volume * 1.5
                no_supply = current_volume < avg_volume * 0.5
                
                if bandar_result['confirmed']:
                    confidence = "HIGH" if volume_spike or no_supply else "MEDIUM"
                    return WyckoffResult(
                        pattern=WyckoffPattern.SPRING,
                        confidence=confidence,
                        level=support_level,
                        action="BUY_ZONE",
                        bandar_confirmed=True,
                        details={
                            "support": support_level,
                            "current_low": current_low,
                            "current_close": current_close,
                            "volume_spike": volume_spike,
                            "no_supply": no_supply,
                            "top_buyer": bandar_result.get('top_broker'),
                            "buy_value": bandar_result.get('buy_value'),
                            "message": "Spring detected with Bandar buying - Strong buy signal"
                        }
                    )
                else:
                    return WyckoffResult(
                        pattern=WyckoffPattern.FAILED_BREAKDOWN,
                        confidence="MEDIUM",
                        level=support_level,
                        action="AVOID",
                        bandar_confirmed=False,
                        details={
                            "support": support_level,
                            "message": "Price recovered but Bandar still selling - Potential bull trap"
                        }
                    )
            
            # Check for genuine breakdown
            if broke_support and not recovered:
                bandar_result = self._check_bandar_confirmation(broker_data, 'SELL')
                if bandar_result['confirmed']:
                    return WyckoffResult(
                        pattern=WyckoffPattern.BREAKDOWN,
                        confidence="HIGH",
                        level=support_level,
                        action="SELL_ZONE",
                        bandar_confirmed=True,
                        details={
                            "support": support_level,
                            "message": "Genuine breakdown with Bandar selling"
                        }
                    )
            
            return WyckoffResult(
                pattern=WyckoffPattern.NONE,
                confidence="LOW",
                level=support_level,
                action="WATCH",
                bandar_confirmed=False,
                details={"nearest_support": support_level}
            )
            
        except Exception as e:
            logger.error(f"Spring detection error: {e}")
            return WyckoffResult(
                pattern=WyckoffPattern.NONE,
                confidence="LOW",
                level=0,
                action="ERROR",
                bandar_confirmed=False,
                details={"error": str(e)}
            )
    
    def detect_utad(self, price_history: List[Dict], broker_data: Dict) -> WyckoffResult:
        """
        Detect UTAD pattern (Upthrust After Distribution - false breakout above resistance).
        
        UTAD Conditions:
        1. Price breaks above recent resistance level
        2. Price fails and closes below resistance
        3. Top brokers are net sellers (Bandar confirmation)
        
        Returns:
            WyckoffResult with UTAD or FAILED_BREAKOUT
        """
        try:
            # Extract price arrays
            highs = np.array([float(c.get('high', c.get('High', 0))) for c in price_history])
            closes = np.array([float(c.get('close', c.get('Close', 0))) for c in price_history])
            volumes = np.array([float(c.get('volume', c.get('Volume', 0))) for c in price_history])
            
            # Find resistance levels (local maxima)
            resistance_levels = self._find_local_extrema(highs, mode='max')
            
            if len(resistance_levels) == 0:
                return WyckoffResult(
                    pattern=WyckoffPattern.NONE,
                    confidence="LOW",
                    level=0,
                    action="NO_RESISTANCE_FOUND",
                    bandar_confirmed=False,
                    details={}
                )
            
            # Get most recent resistance level
            resistance_level = highs[resistance_levels[-1]]
            
            # Current bar data
            current_high = highs[-1]
            current_close = closes[-1]
            avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
            current_volume = volumes[-1]
            
            # Check UTAD conditions
            broke_resistance = current_high > resistance_level * 1.005  # 0.5% tolerance
            failed = current_close < resistance_level
            
            if broke_resistance and failed:
                # Confirm with Bandarmology
                bandar_result = self._check_bandar_confirmation(broker_data, 'SELL')
                
                # Volume analysis
                volume_spike = current_volume > avg_volume * 1.5
                
                if bandar_result['confirmed']:
                    confidence = "HIGH" if volume_spike else "MEDIUM"
                    return WyckoffResult(
                        pattern=WyckoffPattern.UTAD,
                        confidence=confidence,
                        level=resistance_level,
                        action="SELL_ZONE",
                        bandar_confirmed=True,
                        details={
                            "resistance": resistance_level,
                            "current_high": current_high,
                            "current_close": current_close,
                            "volume_spike": volume_spike,
                            "top_seller": bandar_result.get('top_broker'),
                            "sell_value": bandar_result.get('sell_value'),
                            "message": "UTAD detected with Bandar selling - Bull trap warning"
                        }
                    )
                else:
                    return WyckoffResult(
                        pattern=WyckoffPattern.FAILED_BREAKOUT,
                        confidence="MEDIUM",
                        level=resistance_level,
                        action="WATCH",
                        bandar_confirmed=False,
                        details={
                            "resistance": resistance_level,
                            "message": "Breakout failed but Bandar still buying - Possible retest"
                        }
                    )
            
            # Check for genuine breakout
            if broke_resistance and not failed:
                bandar_result = self._check_bandar_confirmation(broker_data, 'BUY')
                if bandar_result['confirmed']:
                    return WyckoffResult(
                        pattern=WyckoffPattern.BREAKOUT,
                        confidence="HIGH",
                        level=resistance_level,
                        action="BUY_ZONE",
                        bandar_confirmed=True,
                        details={
                            "resistance": resistance_level,
                            "message": "Genuine breakout with Bandar buying"
                        }
                    )
            
            return WyckoffResult(
                pattern=WyckoffPattern.NONE,
                confidence="LOW",
                level=resistance_level,
                action="WATCH",
                bandar_confirmed=False,
                details={"nearest_resistance": resistance_level}
            )
            
        except Exception as e:
            logger.error(f"UTAD detection error: {e}")
            return WyckoffResult(
                pattern=WyckoffPattern.NONE,
                confidence="LOW",
                level=0,
                action="ERROR",
                bandar_confirmed=False,
                details={"error": str(e)}
            )
    
    def _find_local_extrema(self, data: np.ndarray, mode: str = 'min') -> np.ndarray:
        """
        Find local minima or maxima in price data.
        
        Uses rolling window comparison instead of scipy for simpler deployment.
        """
        order = self.sensitivity
        indices = []
        
        for i in range(order, len(data) - order):
            window = data[i - order:i + order + 1]
            
            if mode == 'min':
                if data[i] == np.min(window):
                    indices.append(i)
            else:  # max
                if data[i] == np.max(window):
                    indices.append(i)
        
        return np.array(indices)
    
    def _check_bandar_confirmation(self, broker_data: Dict, direction: str) -> Dict:
        """
        Check if top brokers confirm the pattern direction.
        
        Args:
            broker_data: With top_buyers and top_sellers
            direction: 'BUY' or 'SELL'
            
        Returns:
            Dict with confirmed status and broker details
        """
        top_buyers = broker_data.get('top_buyers', [])
        top_sellers = broker_data.get('top_sellers', [])
        
        # Calculate top 3 values
        buy_value = sum(float(b.get('value', b.get('val', 0))) for b in top_buyers[:3])
        sell_value = sum(float(s.get('value', s.get('val', 0))) for s in top_sellers[:3])
        
        if direction == 'BUY':
            confirmed = buy_value > sell_value
            top_broker = top_buyers[0].get('code', 'N/A') if top_buyers else 'N/A'
            return {
                'confirmed': confirmed,
                'top_broker': top_broker,
                'buy_value': buy_value,
                'sell_value': sell_value,
                'ratio': buy_value / sell_value if sell_value > 0 else float('inf')
            }
        else:
            confirmed = sell_value > buy_value
            top_broker = top_sellers[0].get('code', 'N/A') if top_sellers else 'N/A'
            return {
                'confirmed': confirmed,
                'top_broker': top_broker,
                'buy_value': buy_value,
                'sell_value': sell_value,
                'ratio': sell_value / buy_value if buy_value > 0 else float('inf')
            }


# Singleton instance
_detector_instance = None

def get_wyckoff_detector() -> WyckoffDetector:
    """Get or create singleton detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = WyckoffDetector()
    return _detector_instance
