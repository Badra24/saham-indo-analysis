"""
Technical Indicators Module

Implements all indicators from the research documents:
- MACD-V (Volatility-Normalized MACD)
- RSI (Relative Strength Index)
- VWAP (Volume Weighted Average Price) - Key for Looping re-entry
- Bollinger Bands
- ATR (Average True Range)
- Volume Anomaly Detection (Isolation Forest concept)

Reference: Riset Bandarmologi, Chapter 5.1
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


def calculate_macd_v(df: pd.DataFrame, price_col='Close') -> pd.DataFrame:
    """
    Calculates Volatility-Normalized MACD (MACD-V).
    
    MACD-V = (EMA(12) - EMA(26)) / ATR(26) * 100
    
    This normalizes MACD by volatility, making signals comparable across stocks.
    """
    df = df.copy()
    
    if len(df) < 26:
        df['MACD'] = 0
        df['MACD_V'] = 0
        df['ATR_26'] = 0
        return df
    
    # Calculate EMAs
    df['EMA_12'] = df[price_col].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df[price_col].ewm(span=26, adjust=False).mean()
    
    # Calculate standard MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # Calculate ATR(26) for volatility normalization
    df['ATR_26'] = calculate_atr(df, period=26)
    
    # Calculate MACD-V (avoid division by zero)
    df['MACD_V'] = np.where(
        df['ATR_26'] > 0,
        (df['MACD'] / df['ATR_26']) * 100,
        0
    )
    
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14, price_col='Close') -> pd.Series:
    """
    Calculate Average True Range (ATR)
    
    ATR measures volatility. Used for:
    - Position sizing (volatility-adjusted sizing)
    - Stop loss placement
    - MACD-V normalization
    """
    df = df.copy()
    
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df[price_col].shift())
    low_close = np.abs(df['Low'] - df[price_col].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    atr = true_range.rolling(window=period).mean()
    return atr


def calculate_rsi(df: pd.DataFrame, period: int = 14, price_col='Close') -> pd.DataFrame:
    """
    Calculate Relative Strength Index (RSI)
    
    RSI measures momentum:
    - RSI > 70: Overbought (potential reversal down)
    - RSI < 30: Oversold (potential reversal up)
    - RSI 40-60: Neutral
    
    Used in conjunction with OBI for confirmation.
    """
    df = df.copy()
    
    if len(df) < period:
        df['RSI'] = 50
        return df
    
    # Calculate price changes
    delta = df[price_col].diff()
    
    # Separate gains and losses
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    
    # Calculate average gains and losses
    avg_gains = gains.rolling(window=period).mean()
    avg_losses = losses.rolling(window=period).mean()
    
    # Calculate RS and RSI
    rs = avg_gains / avg_losses.replace(0, np.inf)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Fill NaN with neutral value
    df['RSI'] = df['RSI'].fillna(50)
    
    return df


def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Volume Weighted Average Price (VWAP)
    
    VWAP is crucial for Looping Strategy:
    - Price above VWAP = Bullish (buyers in control)
    - Price below VWAP = Bearish (sellers in control)
    - Pullback to VWAP = Re-entry opportunity (Looping)
    
    Formula: VWAP = Cumulative(Typical Price × Volume) / Cumulative(Volume)
    """
    df = df.copy()
    
    # Typical Price = (High + Low + Close) / 3
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    
    # VWAP calculation (cumulative for intraday, or rolling for daily)
    df['VP'] = df['Typical_Price'] * df['Volume']
    df['Cumulative_VP'] = df['VP'].cumsum()
    df['Cumulative_Vol'] = df['Volume'].cumsum()
    
    df['VWAP'] = df['Cumulative_VP'] / df['Cumulative_Vol'].replace(0, np.nan)
    df['VWAP'] = df['VWAP'].fillna(df['Close'])
    
    # VWAP bands (standard deviation bands for support/resistance)
    df['VWAP_Distance'] = (df['Close'] - df['VWAP']) / df['VWAP'] * 100  # % distance from VWAP
    
    return df


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, 
                               std_dev: float = 2.0, price_col='Close') -> pd.DataFrame:
    """
    Calculate Bollinger Bands
    
    Measures volatility and mean reversion:
    - Price at upper band: Potentially overbought
    - Price at lower band: Potentially oversold
    - Band squeeze: Low volatility, breakout imminent
    
    Works well with OBI for confirmation.
    """
    df = df.copy()
    
    if len(df) < period:
        df['BB_Middle'] = df[price_col]
        df['BB_Upper'] = df[price_col]
        df['BB_Lower'] = df[price_col]
        df['BB_Width'] = 0
        df['BB_Percent'] = 0.5
        return df
    
    # Middle band (SMA)
    df['BB_Middle'] = df[price_col].rolling(window=period).mean()
    
    # Standard deviation
    df['BB_Std'] = df[price_col].rolling(window=period).std()
    
    # Upper and Lower bands
    df['BB_Upper'] = df['BB_Middle'] + (std_dev * df['BB_Std'])
    df['BB_Lower'] = df['BB_Middle'] - (std_dev * df['BB_Std'])
    
    # Bandwidth (measures volatility)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle'] * 100
    
    # %B (position within bands, 0 = lower, 1 = upper)
    df['BB_Percent'] = (df[price_col] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
    df['BB_Percent'] = df['BB_Percent'].clip(0, 1)
    
    return df


def detect_volume_anomaly(df: pd.DataFrame, lookback: int = 20, 
                          threshold: float = 1.5) -> pd.DataFrame:
    """
    Detect abnormal volume (potential whale activity)
    
    Based on Isolation Forest concept from research:
    - Volume > 2x average = Anomaly
    - Anomaly + Price breakout = Institutional activity
    
    This is a simplified version. Full Isolation Forest can be added later.
    """
    df = df.copy()
    
    if len(df) < lookback:
        df['Volume_SMA'] = df['Volume']
        df['Volume_Ratio'] = 1.0
        df['Volume_Anomaly'] = False
        return df
    
    # Calculate volume moving average
    df['Volume_SMA'] = df['Volume'].rolling(window=lookback).mean()
    
    # Volume ratio (current / average)
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA'].replace(0, np.nan)
    df['Volume_Ratio'] = df['Volume_Ratio'].fillna(1)
    
    # Flag anomalies
    df['Volume_Anomaly'] = df['Volume_Ratio'] > threshold
    
    # Additional: Check if anomaly coincides with price move
    df['Price_Change'] = df['Close'].pct_change()
    df['Whale_Buy'] = (df['Volume_Anomaly']) & (df['Price_Change'] > 0.01)  # 1%+ up
    df['Whale_Sell'] = (df['Volume_Anomaly']) & (df['Price_Change'] < -0.01)  # 1%+ down
    
    return df


def calculate_ema(df: pd.DataFrame, periods: list, price_col='Close') -> pd.DataFrame:
    """
    Calculate Exponential Moving Averages for multiple periods
    """
    df = df.copy()
    for period in periods:
        df[f'EMA_{period}'] = df[price_col].ewm(span=period, adjust=False).mean()
    return df


def calculate_sma(df: pd.DataFrame, periods: list, price_col='Close') -> pd.DataFrame:
    """
    Calculate Simple Moving Averages for multiple periods
    """
    df = df.copy()
    for period in periods:
        df[f'SMA_{period}'] = df[price_col].rolling(window=period).mean()
    return df


def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, 
                         d_period: int = 3, price_col='Close') -> pd.DataFrame:
    """
    Calculate Stochastic Oscillator
    
    Formula:
        %K = [(Close - Lowest Low) / (Highest High - Lowest Low)] × 100
        %D = SMA(3) of %K
    
    Interpretation:
        - %K > 80: Overbought
        - %K < 20: Oversold
        - %K crosses %D from below in oversold zone: Strong BUY
        - %K crosses %D from above in overbought zone: Strong SELL
    
    Reference: Lane, 1984 - More responsive than RSI for turning points
    """
    df = df.copy()
    
    if len(df) < k_period:
        df['Stoch_K'] = 50
        df['Stoch_D'] = 50
        df['Stoch_Zone'] = 'neutral'
        return df
    
    # Calculate highest high and lowest low over k_period
    df['Lowest_Low'] = df['Low'].rolling(window=k_period).min()
    df['Highest_High'] = df['High'].rolling(window=k_period).max()
    
    # Calculate %K
    df['Stoch_K'] = np.where(
        (df['Highest_High'] - df['Lowest_Low']) > 0,
        ((df[price_col] - df['Lowest_Low']) / 
         (df['Highest_High'] - df['Lowest_Low'])) * 100,
        50
    )
    
    # Calculate %D (SMA of %K)
    df['Stoch_D'] = df['Stoch_K'].rolling(window=d_period).mean()
    
    # Determine zone
    df['Stoch_Zone'] = np.where(
        df['Stoch_K'] > 80, 'overbought',
        np.where(df['Stoch_K'] < 20, 'oversold', 'neutral')
    )
    
    # Detect crossovers for signals
    df['Stoch_Cross_Up'] = (df['Stoch_K'] > df['Stoch_D']) & (df['Stoch_K'].shift(1) <= df['Stoch_D'].shift(1))
    df['Stoch_Cross_Down'] = (df['Stoch_K'] < df['Stoch_D']) & (df['Stoch_K'].shift(1) >= df['Stoch_D'].shift(1))
    
    # Clean up temporary columns
    df.drop(['Lowest_Low', 'Highest_High'], axis=1, inplace=True)
    
    return df


def calculate_obv(df: pd.DataFrame, price_col='Close') -> pd.DataFrame:
    """
    Calculate On-Balance Volume (OBV)
    
    Formula:
        If Close > Close_prev: OBV = OBV_prev + Volume
        If Close < Close_prev: OBV = OBV_prev - Volume
        If Close = Close_prev: OBV = OBV_prev
    
    Interpretation:
        - OBV rising with price: Confirms uptrend (volume supporting move)
        - OBV falling with price: Confirms downtrend
        - OBV divergence from price: Early warning of reversal
    
    Reference: Granville, 1963 - "Volume precedes price"
    """
    df = df.copy()
    
    if len(df) < 2:
        df['OBV'] = 0
        df['OBV_SMA'] = 0
        df['OBV_Trend'] = 'neutral'
        return df
    
    # Calculate price direction
    df['Price_Direction'] = np.sign(df[price_col].diff())
    
    # Calculate OBV
    df['OBV'] = (df['Volume'] * df['Price_Direction']).fillna(0).cumsum()
    
    # OBV moving average for trend
    df['OBV_SMA'] = df['OBV'].rolling(window=20).mean()
    
    # OBV trend
    df['OBV_Trend'] = np.where(
        df['OBV'] > df['OBV_SMA'], 'bullish',
        np.where(df['OBV'] < df['OBV_SMA'], 'bearish', 'neutral')
    )
    
    # Clean up
    df.drop(['Price_Direction'], axis=1, inplace=True)
    
    return df


def calculate_cci(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Calculate Commodity Channel Index (CCI)
    
    Formula:
        Typical Price = (High + Low + Close) / 3
        CCI = (Typical Price - SMA of TP) / (0.015 × Mean Deviation)
    
    Interpretation:
        - CCI > +100: Strong uptrend
        - CCI < -100: Strong downtrend
        - CCI returning to -100/+100 range: Potential consolidation
    
    Reference: Lambert, 1980 - Effective for commodity stocks (BUMI, ANTM, INCO)
    """
    df = df.copy()
    
    if len(df) < period:
        df['CCI'] = 0
        df['CCI_Zone'] = 'neutral'
        return df
    
    # Calculate Typical Price
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    
    # SMA of Typical Price
    df['TP_SMA'] = df['TP'].rolling(window=period).mean()
    
    # Mean Deviation
    df['Mean_Deviation'] = df['TP'].rolling(window=period).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )
    
    # Calculate CCI
    df['CCI'] = np.where(
        df['Mean_Deviation'] > 0,
        (df['TP'] - df['TP_SMA']) / (0.015 * df['Mean_Deviation']),
        0
    )
    
    # CCI Zone
    df['CCI_Zone'] = np.where(
        df['CCI'] > 100, 'bullish_strong',
        np.where(df['CCI'] < -100, 'bearish_strong', 'neutral')
    )
    
    # Clean up
    df.drop(['TP', 'TP_SMA', 'Mean_Deviation'], axis=1, inplace=True)
    
    return df


def calculate_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Ichimoku Kinko Hyo (Ichimoku Cloud)
    
    Components:
        - Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        - Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        - Senkou Span A: (Tenkan + Kijun) / 2, projected 26 periods ahead
        - Senkou Span B: (52-period high + 52-period low) / 2, projected 26 periods ahead
        - Chikou Span: Current close, plotted 26 periods back
    
    Interpretation:
        - Price above Kumo (cloud): Bullish
        - Tenkan crosses Kijun from below: Buy signal
        - Kumo twist (Senkou A crosses Senkou B): Trend change
    
    Reference: Hosoda, 1996 - Win Rate 67%, Sharpe Ratio 1.58
    """
    df = df.copy()
    
    # Tenkan-sen (Conversion Line) - 9 periods
    tenkan_high = df['High'].rolling(window=9).max()
    tenkan_low = df['Low'].rolling(window=9).min()
    df['Ichimoku_Tenkan'] = (tenkan_high + tenkan_low) / 2
    
    # Kijun-sen (Base Line) - 26 periods
    kijun_high = df['High'].rolling(window=26).max()
    kijun_low = df['Low'].rolling(window=26).min()
    df['Ichimoku_Kijun'] = (kijun_high + kijun_low) / 2
    
    # Senkou Span A (Leading Span A) - projected 26 periods ahead
    df['Ichimoku_SpanA'] = ((df['Ichimoku_Tenkan'] + df['Ichimoku_Kijun']) / 2).shift(26)
    
    # Senkou Span B (Leading Span B) - 52 periods, projected 26 periods ahead
    span_b_high = df['High'].rolling(window=52).max()
    span_b_low = df['Low'].rolling(window=52).min()
    df['Ichimoku_SpanB'] = ((span_b_high + span_b_low) / 2).shift(26)
    
    # Chikou Span (Lagging Span) - current close, plotted 26 periods back
    df['Ichimoku_Chikou'] = df['Close'].shift(-26)
    
    # Cloud color (bullish when Span A > Span B)
    df['Ichimoku_Cloud'] = np.where(
        df['Ichimoku_SpanA'] > df['Ichimoku_SpanB'], 'bullish', 'bearish'
    )
    
    # Price position relative to cloud
    df['Ichimoku_Signal'] = np.where(
        df['Close'] > df[['Ichimoku_SpanA', 'Ichimoku_SpanB']].max(axis=1), 'above_cloud',
        np.where(
            df['Close'] < df[['Ichimoku_SpanA', 'Ichimoku_SpanB']].min(axis=1), 'below_cloud',
            'in_cloud'
        )
    )
    
    # Tenkan/Kijun crossover
    df['Ichimoku_TK_Cross'] = np.where(
        (df['Ichimoku_Tenkan'] > df['Ichimoku_Kijun']) & 
        (df['Ichimoku_Tenkan'].shift(1) <= df['Ichimoku_Kijun'].shift(1)),
        'bullish_cross',
        np.where(
            (df['Ichimoku_Tenkan'] < df['Ichimoku_Kijun']) & 
            (df['Ichimoku_Tenkan'].shift(1) >= df['Ichimoku_Kijun'].shift(1)),
            'bearish_cross',
            'none'
        )
    )
    
    return df


def calculate_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Pivot Points (Standard/Floor Pivot)
    
    Formula:
        Pivot = (High + Low + Close) / 3
        R1 = (2 × Pivot) - Low
        S1 = (2 × Pivot) - High
        R2 = Pivot + (High - Low)
        S2 = Pivot - (High - Low)
        R3 = High + 2 × (Pivot - Low)
        S3 = Low - 2 × (High - Pivot)
    
    Usage:
        - Intraday support/resistance levels
        - Used by market makers for price targets
    
    Note: Uses previous period's OHLC for current period pivots
    """
    df = df.copy()
    
    if len(df) < 2:
        df['Pivot'] = df['Close']
        df['Pivot_R1'] = df['Close']
        df['Pivot_R2'] = df['Close']
        df['Pivot_R3'] = df['Close']
        df['Pivot_S1'] = df['Close']
        df['Pivot_S2'] = df['Close']
        df['Pivot_S3'] = df['Close']
        df['Pivot_Position'] = 'at_pivot'
        return df
    
    # Use previous period data for pivot calculation
    prev_high = df['High'].shift(1)
    prev_low = df['Low'].shift(1)
    prev_close = df['Close'].shift(1)
    
    # Pivot Point
    df['Pivot'] = (prev_high + prev_low + prev_close) / 3
    
    # Resistance levels
    df['Pivot_R1'] = (2 * df['Pivot']) - prev_low
    df['Pivot_R2'] = df['Pivot'] + (prev_high - prev_low)
    df['Pivot_R3'] = prev_high + 2 * (df['Pivot'] - prev_low)
    
    # Support levels
    df['Pivot_S1'] = (2 * df['Pivot']) - prev_high
    df['Pivot_S2'] = df['Pivot'] - (prev_high - prev_low)
    df['Pivot_S3'] = prev_low - 2 * (prev_high - df['Pivot'])
    
    # Current price position relative to pivot
    df['Pivot_Position'] = np.where(
        df['Close'] > df['Pivot_R1'], 'above_R1',
        np.where(
            df['Close'] > df['Pivot'], 'above_pivot',
            np.where(
                df['Close'] > df['Pivot_S1'], 'below_pivot',
                'below_S1'
            )
        )
    )
    
    return df


def calculate_fibonacci_levels(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
    """
    Calculate Fibonacci Retracement Levels
    
    Levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
    
    Uses swing high and swing low within lookback period
    """
    df = df.copy()
    
    if len(df) < lookback:
        lookback = len(df)
    
    # Find swing high and swing low in lookback period
    recent_data = df.tail(lookback)
    swing_high = recent_data['High'].max()
    swing_low = recent_data['Low'].min()
    
    price_range = swing_high - swing_low
    
    # Fibonacci levels (for uptrend retracement)
    df['Fib_0'] = swing_low  # 0% - Swing Low
    df['Fib_236'] = swing_low + (price_range * 0.236)  # 23.6%
    df['Fib_382'] = swing_low + (price_range * 0.382)  # 38.2%
    df['Fib_500'] = swing_low + (price_range * 0.500)  # 50%
    df['Fib_618'] = swing_low + (price_range * 0.618)  # 61.8% - Golden Ratio
    df['Fib_786'] = swing_low + (price_range * 0.786)  # 78.6%
    df['Fib_100'] = swing_high  # 100% - Swing High
    
    # Current price relative to Fibonacci levels
    df['Fib_Level'] = np.where(
        df['Close'] >= df['Fib_786'], 'above_78.6',
        np.where(
            df['Close'] >= df['Fib_618'], 'at_61.8',
            np.where(
                df['Close'] >= df['Fib_500'], 'at_50.0',
                np.where(
                    df['Close'] >= df['Fib_382'], 'at_38.2',
                    np.where(
                        df['Close'] >= df['Fib_236'], 'at_23.6',
                        'below_23.6'
                    )
                )
            )
        )
    )
    
    return df


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators at once
    
    Includes all indicators from LAPORAN_RISET_INDIKATOR_TEKNIKAL:
    - Trend: EMA, SMA, MACD-V
    - Momentum: RSI, Stochastic, CCI
    - Volatility: Bollinger Bands, ATR
    - Volume: VWAP, OBV, Volume Anomaly
    - Advanced: Ichimoku, Fibonacci, Pivot Points
    
    Returns DataFrame with all indicator columns added.
    """
    df = df.copy()
    
    # Core indicators (existing)
    df = calculate_macd_v(df)
    df = calculate_rsi(df)
    df = calculate_vwap(df)
    df = calculate_bollinger_bands(df)
    df = detect_volume_anomaly(df)
    
    # Add EMA and SMA for chart overlay
    df = calculate_ema(df, [9, 21, 55, 200])  # Added EMA 9 for scalping
    df = calculate_sma(df, [50, 100, 200])    # Added SMA 100
    
    # Add ATR separately if not already present
    if 'ATR_14' not in df.columns:
        df['ATR_14'] = calculate_atr(df, period=14)
    
    # NEW INDICATORS from Riset
    # Momentum
    df = calculate_stochastic(df)
    df = calculate_cci(df)
    
    # Volume
    df = calculate_obv(df)
    
    # Advanced
    df = calculate_ichimoku(df)
    df = calculate_pivot_points(df)
    df = calculate_fibonacci_levels(df)
    
    # VPVR (Volume Profile) - Requires significant computation, so we optimize
    # Calculate for the visible range (last 100 periods or full df if shorter)
    df = calculate_vpvr(df, bins=24)
    
    return df


def calculate_vpvr(df: pd.DataFrame, bins: int = 24, lookback: int = 100) -> pd.DataFrame:
    """
    Calculate Volume Profile Visible Range (VPVR)
    
    Crucial for Bandarmology:
    - POC (Point of Control): Price level with highest volume (Institutional "Host" Price)
    - VA (Value Area): Range where 70% of volume occurred
    - HVN/LVN: High/Low Volume Nodes
    
    Logic:
    1. Slice last 'lookback' periods.
    2. Bin prices into 'bins' buckets.
    3. Sum volume for each bin.
    4. Find POC and VA.
    
    Returns DataFrame with POC and Value Area columns repeated for the last rows.
    """
    df = df.copy()
    
    # Initialize columns
    df['VPVR_POC'] = np.nan
    df['VPVR_VAH'] = np.nan # Value Area High
    df['VPVR_VAL'] = np.nan # Value Area Low
    
    # Use recent data for "Visible Range"
    if len(df) > lookback:
        window = df.tail(lookback)
    else:
        window = df
        
    if window.empty:
        return df
        
    # Create price bins
    price_min = window['Low'].min()
    price_max = window['High'].max()
    
    if price_min == price_max:
        return df
        
    # Create bins
    bins_array = np.linspace(price_min, price_max, bins + 1)
    
    # Calculate volume per bin
    # We assign the volume of the candle to the bin of its Close price (simplified)
    # A more accurate way is to split volume across High-Low, but Close is faster for MVP
    window = window.copy()
    window['Bin_Index'] = np.digitize(window['Close'], bins_array) - 1
    
    # Group by bin and sum volume
    volume_profile = window.groupby('Bin_Index')['Volume'].sum()
    
    # Find POC (Bin with max volume)
    if volume_profile.empty:
        return df
    
    poc_index = volume_profile.idxmax()
    poc_price = (bins_array[poc_index] + bins_array[poc_index+1]) / 2
    
    # Calculate Value Area (70%)
    total_volume = volume_profile.sum()
    target_volume = total_volume * 0.70
    
    # Sort bins by volume descending to accumulate VA
    sorted_profile = volume_profile.sort_values(ascending=False)
    accumulated_vol = 0
    va_indices = []
    
    for idx, vol in sorted_profile.items():
        accumulated_vol += vol
        va_indices.append(idx)
        if accumulated_vol >= target_volume:
            break
            
    # Find VAH and VAL from indices
    if va_indices:
        min_va_idx = min(va_indices)
        max_va_idx = max(va_indices)
        
        # Valid indices check
        if 0 <= min_va_idx < len(bins_array)-1 and 0 <= max_va_idx < len(bins_array)-1:
            val_price = bins_array[min_va_idx]
            vah_price = bins_array[max_va_idx+1]
        else:
            val_price = price_min
            vah_price = price_max
    else:
        val_price = price_min
        vah_price = price_max
        
    # Assign to DataFrame (only for the window, or broadcast to all?)
    # Broadcasting to whole DF for easier access in get_latest
    df['VPVR_POC'] = poc_price
    df['VPVR_VAH'] = vah_price
    df['VPVR_VAL'] = val_price
    
    return df


def get_latest_indicators(df: pd.DataFrame) -> Dict:
    """
    Get latest indicator values as a dictionary
    
    Useful for API responses.
    """
    if df.empty:
        return {}
    
    # Ensure all indicators are calculated
    df = calculate_all_indicators(df)
    
    latest = df.iloc[-1]
    
    return {
        # Price
        'price': float(latest.get('Close', 0)),
        
        # Trend Indicators
        'macd': float(latest.get('MACD', 0)),
        'macd_v': float(latest.get('MACD_V', 0)),
        'macd_signal': float(latest.get('MACD_Signal', 0)),
        'macd_histogram': float(latest.get('MACD_Histogram', 0)),
        
        # Momentum Indicators
        'rsi': float(latest.get('RSI', 50)),
        'stoch_k': float(latest.get('Stoch_K', 50)),
        'stoch_d': float(latest.get('Stoch_D', 50)),
        'stoch_zone': str(latest.get('Stoch_Zone', 'neutral')),
        'cci': float(latest.get('CCI', 0)),
        'cci_zone': str(latest.get('CCI_Zone', 'neutral')),
        
        # VWAP
        'vwap': float(latest.get('VWAP', 0)),
        'vwap_distance': float(latest.get('VWAP_Distance', 0)),
        
        # Volatility
        'atr_14': float(latest.get('ATR_14', 0)),
        'atr_26': float(latest.get('ATR_26', 0)),
        'bb_upper': float(latest.get('BB_Upper', 0)),
        'bb_middle': float(latest.get('BB_Middle', 0)),
        'bb_lower': float(latest.get('BB_Lower', 0)),
        'bb_width': float(latest.get('BB_Width', 0)),
        'bb_percent': float(latest.get('BB_Percent', 0.5)),
        
        # Volume Indicators
        'volume_ratio': float(latest.get('Volume_Ratio', 1)),
        'volume_anomaly': bool(latest.get('Volume_Anomaly', False)),
        'whale_buy': bool(latest.get('Whale_Buy', False)),
        'whale_sell': bool(latest.get('Whale_Sell', False)),
        'obv': float(latest.get('OBV', 0)),
        'obv_trend': str(latest.get('OBV_Trend', 'neutral')),
        
        # Ichimoku
        'ichimoku_tenkan': float(latest.get('Ichimoku_Tenkan', 0)),
        'ichimoku_kijun': float(latest.get('Ichimoku_Kijun', 0)),
        'ichimoku_span_a': float(latest.get('Ichimoku_SpanA', 0)),
        'ichimoku_span_b': float(latest.get('Ichimoku_SpanB', 0)),
        'ichimoku_signal': str(latest.get('Ichimoku_Signal', 'neutral')),
        'ichimoku_cloud': str(latest.get('Ichimoku_Cloud', 'neutral')),
        
        # Pivot Points
        'pivot': float(latest.get('Pivot', 0)),
        'pivot_r1': float(latest.get('Pivot_R1', 0)),
        'pivot_r2': float(latest.get('Pivot_R2', 0)),
        'pivot_s1': float(latest.get('Pivot_S1', 0)),
        'pivot_s2': float(latest.get('Pivot_S2', 0)),
        'pivot_position': str(latest.get('Pivot_Position', 'at_pivot')),
        
        # Fibonacci Levels
        'fib_0': float(latest.get('Fib_0', 0)),
        'fib_236': float(latest.get('Fib_236', 0)),
        'fib_382': float(latest.get('Fib_382', 0)),
        'fib_500': float(latest.get('Fib_500', 0)),
        'fib_618': float(latest.get('Fib_618', 0)),
        'fib_786': float(latest.get('Fib_786', 0)),
        'fib_100': float(latest.get('Fib_100', 0)),
        'fib_level': str(latest.get('Fib_Level', 'neutral')),
        
        # VPVR
        'vpvr_poc': float(latest.get('VPVR_POC', 0)),
        'vpvr_vah': float(latest.get('VPVR_VAH', 0)),
        'vpvr_val': float(latest.get('VPVR_VAL', 0))
    }


def get_indicator_signals(df: pd.DataFrame) -> Dict:
    """
    Generate trading signals from all indicators
    
    Includes signals from:
    - RSI, Stochastic, CCI (Momentum)
    - MACD-V (Trend)
    - VWAP, Bollinger Bands (Mean Reversion)
    - OBV, Volume Anomaly (Volume)
    - Ichimoku (Trend + Momentum)
    
    Returns:
        Dict with signal interpretation and confluence score
    """
    indicators = get_latest_indicators(df)
    
    signals = []
    overall_bias = 0  # -1 to 1
    confluence_count = 0  # Number of confirming signals
    
    # === MOMENTUM SIGNALS ===
    
    # RSI Signal
    rsi = indicators.get('rsi', 50)
    if rsi > 70:
        signals.append("RSI overbought (>70) - potential pullback")
        overall_bias -= 0.15
    elif rsi < 30:
        signals.append("RSI oversold (<30) - potential bounce")
        overall_bias += 0.15
    
    # Stochastic Signal
    stoch_k = indicators.get('stoch_k', 50)
    stoch_zone = indicators.get('stoch_zone', 'neutral')
    if stoch_zone == 'overbought':
        signals.append("Stochastic overbought (>80) - potential reversal")
        overall_bias -= 0.15
    elif stoch_zone == 'oversold':
        signals.append("Stochastic oversold (<20) - potential reversal")
        overall_bias += 0.15
    
    # CCI Signal
    cci = indicators.get('cci', 0)
    if cci > 100:
        signals.append(f"CCI bullish momentum ({cci:.0f}) - strong uptrend")
        overall_bias += 0.1
        confluence_count += 1
    elif cci < -100:
        signals.append(f"CCI bearish momentum ({cci:.0f}) - strong downtrend")
        overall_bias -= 0.1
        confluence_count += 1
    
    # === TREND SIGNALS ===
    
    # MACD Signal
    macd_v = indicators.get('macd_v', 0)
    if macd_v > 50:
        signals.append("MACD-V bullish momentum")
        overall_bias += 0.15
        confluence_count += 1
    elif macd_v < -50:
        signals.append("MACD-V bearish momentum")
        overall_bias -= 0.15
        confluence_count += 1
    
    # Ichimoku Signal
    ichimoku_signal = indicators.get('ichimoku_signal', 'neutral')
    ichimoku_cloud = indicators.get('ichimoku_cloud', 'neutral')
    if ichimoku_signal == 'above_cloud':
        signals.append("Price above Ichimoku Cloud - bullish trend")
        overall_bias += 0.2
        confluence_count += 1
    elif ichimoku_signal == 'below_cloud':
        signals.append("Price below Ichimoku Cloud - bearish trend")
        overall_bias -= 0.2
        confluence_count += 1
    else:
        signals.append("Price inside Ichimoku Cloud - consolidation")
    
    # === MEAN REVERSION SIGNALS ===
    
    # VWAP Signal
    vwap_dist = indicators.get('vwap_distance', 0)
    if vwap_dist > 2:
        signals.append("Price extended above VWAP - wait for pullback")
        overall_bias -= 0.1
    elif -1 < vwap_dist < 1:
        signals.append("Price near VWAP - good re-entry zone")
        overall_bias += 0.1
    elif vwap_dist < -2:
        signals.append("Price below VWAP - weak trend")
        overall_bias -= 0.15
    
    # Bollinger Bands
    bb_percent = indicators.get('bb_percent', 0.5)
    if bb_percent > 0.95:
        signals.append("Price at upper Bollinger Band - overbought")
        overall_bias -= 0.1
    elif bb_percent < 0.05:
        signals.append("Price at lower Bollinger Band - oversold")
        overall_bias += 0.1
    
    # === VOLUME SIGNALS ===
    
    # OBV Trend
    obv_trend = indicators.get('obv_trend', 'neutral')
    if obv_trend == 'bullish':
        signals.append("OBV bullish - volume confirming uptrend")
        overall_bias += 0.1
        confluence_count += 1
    elif obv_trend == 'bearish':
        signals.append("OBV bearish - volume confirming downtrend")
        overall_bias -= 0.1
        confluence_count += 1
    
    # Volume Anomaly
    if indicators.get('whale_buy'):
        signals.append("🐋 WHALE BUY detected - large volume with price up")
        overall_bias += 0.25
        confluence_count += 1
    elif indicators.get('whale_sell'):
        signals.append("🐋 WHALE SELL detected - large volume with price down")
        overall_bias -= 0.25
        confluence_count += 1
    
    # === SUPPORT/RESISTANCE ===
    
    # Pivot Position
    pivot_position = indicators.get('pivot_position', 'at_pivot')
    if pivot_position == 'above_R1':
        signals.append("Price above R1 Pivot - strong bullish")
        overall_bias += 0.1
    elif pivot_position == 'below_S1':
        signals.append("Price below S1 Pivot - strong bearish")
        overall_bias -= 0.1
    
    # Fibonacci Level
    fib_level = indicators.get('fib_level', 'neutral')
    if fib_level == 'at_61.8':
        signals.append("Price at Fibonacci 61.8% - Golden Ratio support")
    elif fib_level == 'at_38.2':
        signals.append("Price at Fibonacci 38.2% - potential support")
    
    # === DETERMINE OVERALL BIAS ===
    
    if overall_bias > 0.4:
        bias = "STRONG_BULLISH"
    elif overall_bias > 0.2:
        bias = "BULLISH"
    elif overall_bias < -0.4:
        bias = "STRONG_BEARISH"
    elif overall_bias < -0.2:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    
    # Confluence score (how many indicators agree)
    confluence_score = min(confluence_count / 5 * 100, 100)  # Max 100%
    
    return {
        'signals': signals,
        'overall_bias': bias,
        'bias_score': round(overall_bias, 2),
        'confluence_count': confluence_count,
        'confluence_score': round(confluence_score, 1),
        'indicators': indicators
    }

