"""
Simulated Order Book Generator

Since real-time Level 2 data requires expensive API subscriptions,
this module generates realistic order book data based on yfinance prices.

This is a placeholder that can be replaced with real GoAPI/IDX integration later.
"""

import random
import time
import math
from typing import List, Dict, Tuple
from dataclasses import dataclass

from app.services.order_flow import OrderBook, OrderBookLevel


class IDXTickSize:
    """
    Indonesia Stock Exchange (IDX) Tick Size Rules
    
    Based on current IDX regulations:
    - Rp < 200: tick = Rp 1
    - Rp 200-500: tick = Rp 2
    - Rp 500-2000: tick = Rp 5
    - Rp 2000-5000: tick = Rp 10
    - Rp > 5000: tick = Rp 25
    """
    
    @staticmethod
    def get_tick_size(price: float) -> float:
        if price < 200:
            return 1.0
        elif price < 500:
            return 2.0
        elif price < 2000:
            return 5.0
        elif price < 5000:
            return 10.0
        else:
            return 25.0
    
    @staticmethod
    def normalize_price(price: float) -> float:
        """Round price to nearest valid tick"""
        tick = IDXTickSize.get_tick_size(price)
        return round(price / tick) * tick
    
    @staticmethod
    def get_ara_arb_limits(reference_price: float) -> Tuple[float, float]:
        """
        Get Auto Rejection limits (ARA = upper, ARB = lower)
        Standard is ±20-35% depending on stock type
        """
        ara = reference_price * 1.25  # +25% for simplicity
        arb = reference_price * 0.75  # -25% for simplicity
        return ara, arb


class SimulatedOrderBook:
    """
    Generates realistic order book data based on price input
    
    Features:
    - Realistic spread based on tick size
    - Volume distribution following power law
    - Random institutional patterns (iceberg, sweeps)
    - Configurable "mode" for different market conditions
    """
    
    def __init__(self, ticker: str, base_volume: int = 10000):
        self.ticker = ticker
        self.base_volume = base_volume
        self.last_price = 0.0
        self.trade_history: List[Dict] = []
        
        # Simulation state
        self.current_mode = "NEUTRAL"  # ACCUMULATION, DISTRIBUTION, NEUTRAL
        self.mode_duration = 0
        
        # Track for iceberg simulation
        self.iceberg_active = False
        self.iceberg_price = 0.0
        self.iceberg_side = None
    
    def generate(self, current_price: float, depth: int = 10) -> OrderBook:
        """
        Generate a realistic order book snapshot
        
        Args:
            current_price: Current market price
            depth: Number of levels on each side
            
        Returns:
            OrderBook instance
        """
        tick = IDXTickSize.get_tick_size(current_price)
        mid_price = IDXTickSize.normalize_price(current_price)
        
        # Generate bid side (best bid first, descending prices)
        bids = []
        for i in range(depth):
            price = mid_price - (tick * (i + 1))
            volume = self._generate_volume(i, 'BID')
            queue = self._generate_queue_count(volume)
            bids.append(OrderBookLevel(price=price, volume=volume, queue_count=queue))
        
        # Generate ask side (best ask first, ascending prices)
        asks = []
        for i in range(depth):
            price = mid_price + (tick * (i + 1))
            volume = self._generate_volume(i, 'ASK')
            queue = self._generate_queue_count(volume)
            asks.append(OrderBookLevel(price=price, volume=volume, queue_count=queue))
        
        # Apply mode-specific modifications
        bids, asks = self._apply_mode_effects(bids, asks)
        
        # Handle iceberg simulation
        if self.iceberg_active:
            bids, asks = self._apply_iceberg(bids, asks)
        
        self.last_price = current_price
        
        return OrderBook(
            ticker=self.ticker,
            timestamp=time.time(),
            bids=bids,
            asks=asks,
            last_price=current_price,
            last_volume=self._last_trade_volume()
        )
    
    def _generate_volume(self, level: int, side: str) -> int:
        """Generate volume with power law distribution (larger at top of book)"""
        # Base volume decreases with level
        level_factor = 1.0 / (level + 1) ** 0.5
        
        # Random variation
        noise = random.uniform(0.5, 1.5)
        
        # Mode adjustment
        mode_factor = 1.0
        if self.current_mode == "ACCUMULATION" and side == "BID":
            mode_factor = 1.5  # More bid volume during accumulation
        elif self.current_mode == "DISTRIBUTION" and side == "ASK":
            mode_factor = 1.5  # More ask volume during distribution
        
        volume = int(self.base_volume * level_factor * noise * mode_factor)
        return max(100, volume)  # Minimum 100 lots
    
    def _generate_queue_count(self, volume: int) -> int:
        """Generate realistic queue count based on volume"""
        # Higher volume = fewer orders (institutional)
        # Lower volume = more orders (retail)
        avg_order_size = random.choice([50, 100, 200, 500, 1000])
        queue = max(1, volume // avg_order_size)
        return int(queue * random.uniform(0.8, 1.2))
    
    def _apply_mode_effects(self, bids: List[OrderBookLevel], 
                            asks: List[OrderBookLevel]) -> Tuple[List, List]:
        """Apply mode-specific volume adjustments"""
        if self.current_mode == "ACCUMULATION":
            # Thicken top bids
            for i in range(min(3, len(bids))):
                bids[i].volume = int(bids[i].volume * random.uniform(1.5, 2.5))
        elif self.current_mode == "DISTRIBUTION":
            # Thicken top asks
            for i in range(min(3, len(asks))):
                asks[i].volume = int(asks[i].volume * random.uniform(1.5, 2.5))
        
        return bids, asks
    
    def _apply_iceberg(self, bids: List[OrderBookLevel], 
                       asks: List[OrderBookLevel]) -> Tuple[List, List]:
        """Apply iceberg order effects"""
        if self.iceberg_side == "BID" and bids:
            # Maintain constant volume at iceberg level
            for bid in bids:
                if abs(bid.price - self.iceberg_price) < 1:
                    bid.volume = int(self.base_volume * random.uniform(2, 3))
                    bid.queue_count = 1  # Single large order
        elif self.iceberg_side == "ASK" and asks:
            for ask in asks:
                if abs(ask.price - self.iceberg_price) < 1:
                    ask.volume = int(self.base_volume * random.uniform(2, 3))
                    ask.queue_count = 1
        
        return bids, asks
    
    def _last_trade_volume(self) -> int:
        """Get last trade volume or generate one"""
        if self.trade_history:
            return self.trade_history[-1]['volume']
        return random.randint(100, 5000)
    
    def simulate_trade(self, order_book: OrderBook) -> Dict:
        """
        Simulate a trade based on current order flow mode
        
        Returns trade details
        """
        if random.random() < 0.5:  # 50% chance of trade
            return None
        
        # Determine trade direction based on mode
        if self.current_mode == "ACCUMULATION":
            # 70% HAKA (aggressive buying)
            is_haka = random.random() < 0.7
        elif self.current_mode == "DISTRIBUTION":
            # 70% HAKI (aggressive selling)
            is_haka = random.random() < 0.3
        else:
            # 50/50 in neutral
            is_haka = random.random() < 0.5
        
        if is_haka and order_book.asks:
            price = order_book.asks[0].price
            max_vol = order_book.asks[0].volume
        elif not is_haka and order_book.bids:
            price = order_book.bids[0].price
            max_vol = order_book.bids[0].volume
        else:
            return None
        
        # Volume: usually small (retail), occasionally large (institutional)
        if random.random() < 0.1:  # 10% institutional
            volume = int(max_vol * random.uniform(0.3, 0.7))
        else:  # 90% retail
            volume = random.randint(100, 2000)
        
        trade = {
            'price': price,
            'volume': volume,
            'side': 'HAKA' if is_haka else 'HAKI',
            'timestamp': time.time()
        }
        
        self.trade_history.append(trade)
        if len(self.trade_history) > 1000:
            self.trade_history.pop(0)
        
        return trade
    
    def set_mode(self, mode: str, duration: int = 10):
        """
        Set market simulation mode
        
        Args:
            mode: "ACCUMULATION", "DISTRIBUTION", or "NEUTRAL"
            duration: Number of updates to maintain this mode
        """
        self.current_mode = mode
        self.mode_duration = duration
    
    def activate_iceberg(self, price: float, side: str):
        """Activate iceberg order simulation at given price"""
        self.iceberg_active = True
        self.iceberg_price = price
        self.iceberg_side = side
    
    def deactivate_iceberg(self):
        """Deactivate iceberg simulation"""
        self.iceberg_active = False
        self.iceberg_price = 0.0
        self.iceberg_side = None


# Global cache for order book simulators
_simulators: Dict[str, SimulatedOrderBook] = {}


def get_simulated_order_book(ticker: str, price: float, depth: int = 10) -> OrderBook:
    """
    Get or create a simulated order book for a ticker
    
    Args:
        ticker: Stock ticker
        price: Current price
        depth: Number of levels
        
    Returns:
        OrderBook instance
    """
    if ticker not in _simulators:
        _simulators[ticker] = SimulatedOrderBook(ticker)
    
    return _simulators[ticker].generate(price, depth)


def simulate_trade_for_ticker(ticker: str) -> Dict:
    """Simulate a trade for the given ticker"""
    if ticker not in _simulators:
        return None
    
    simulator = _simulators[ticker]
    order_book = simulator.generate(simulator.last_price)
    return simulator.simulate_trade(order_book)


def set_simulation_mode(ticker: str, mode: str, duration: int = 10):
    """Set simulation mode for testing different market conditions"""
    if ticker not in _simulators:
        _simulators[ticker] = SimulatedOrderBook(ticker)
    
    _simulators[ticker].set_mode(mode, duration)
