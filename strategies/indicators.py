"""
Technical Indicators Module
Author: Computer Science Student Project

We implemented all indicators using pure NumPy and Pandas vectorized operations.
Why did we write them ourselves instead of using a third-party library like 'pandas-ta' or 'TA-Lib'?
1. TA-Lib requires external C-libraries which fail to install easily on Windows/Mac.
2. pandas-ta breaks on newer Python versions (3.12, 3.13, 3.14) due to numba build issues.
3. Implementing the formulas directly proves deep understanding of financial mathematics.
"""

from core.compat import np, pd
from typing import Tuple

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """
    Calculates the Exponential Moving Average (EMA).
    
    Formula: EMA_today = Price_today * alpha + EMA_yesterday * (1 - alpha)
    where alpha = 2 / (span + 1).
    
    We use EMA over SMA because EMA gives higher weight to recent prices,
    making it react faster to recent price changes.
    """
    return series.ewm(span=span, adjust=False).mean()

def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    """
    Calculates the Simple Moving Average (SMA).
    Takes the unweighted arithmetic mean over the rolling window.
    """
    return series.rolling(window=window, min_periods=1).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI) using Wilder's smoothing.
    
    How it works:
    1. Calculate price differences between consecutive closes (delta).
    2. Separate gains (positive deltas) and losses (negative deltas).
    3. Smooth average gains and losses using Wilder's smoothing (alpha = 1 / period).
    4. Compute Relative Strength (RS) = Average Gain / Average Loss.
    5. RSI = 100 - (100 / (1 + RS)).
    
    Result is always normalized between 0 and 100:
    - RSI > 70 generally indicates overbought conditions (price might drop).
    - RSI < 30 generally indicates oversold conditions (price might bounce).
    """
    delta = series.diff()
    gain = delta.clip(lower=0)       # Only keep positive moves
    loss = -delta.clip(upper=0)      # Only keep negative moves (as positive numbers)

    # Wilder's exponential smoothing method
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    # Fill any warmup NaN values with 50.0 (neutral baseline)
    return rsi.fillna(50.0)

def calculate_macd(
    series: pd.Series, 
    fast_period: int = 12, 
    slow_period: int = 26, 
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculates Moving Average Convergence Divergence (MACD).
    
    Formula:
    1. MACD Line = 12-period EMA - 26-period EMA
    2. Signal Line = 9-period EMA of the MACD Line
    3. Histogram = MACD Line - Signal Line
    
    How to trade it:
    - When MACD crosses ABOVE the Signal Line -> Bullish momentum (potential BUY)
    - When MACD crosses BELOW the Signal Line -> Bearish momentum (potential SELL)
    """
    ema_fast = calculate_ema(series, fast_period)
    ema_slow = calculate_ema(series, slow_period)
    
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(
    series: pd.Series, 
    period: int = 20, 
    std_dev_multiplier: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Calculates Bollinger Bands and Bandwidth.
    
    Formula:
    1. Middle Band = 20-period Simple Moving Average (SMA)
    2. Upper Band = Middle Band + (2.0 * 20-period standard deviation)
    3. Lower Band = Middle Band - (2.0 * 20-period standard deviation)
    4. Bandwidth = (Upper Band - Lower Band) / Middle Band
    
    Why Bandwidth matters (The "Squeeze"):
    When bandwidth contracts to a very low value (< 0.12), it means the market is
    in a period of low volatility. In trading, low volatility is almost always
    followed by a violent expansion/breakout.
    """
    middle = calculate_sma(series, period)
    std = series.rolling(window=period, min_periods=1).std(ddof=0).fillna(0.0)
    
    upper = middle + (std * std_dev_multiplier)
    lower = middle - (std * std_dev_multiplier)
    
    # Normalized bandwidth
    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    bandwidth = bandwidth.fillna(0.0)
    
    return upper, middle, lower, bandwidth

def calculate_atr(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    period: int = 14
) -> pd.Series:
    """
    Calculates Average True Range (ATR).
    
    Unlike standard deviation, ATR measures volatility by factoring in gaps between bars.
    True Range (TR) is the greatest of:
    1. Current High minus Current Low
    2. Absolute value of Current High minus Previous Close
    3. Absolute value of Current Low minus Previous Close
    
    We smooth True Range over 14 periods.
    We use ATR in our risk manager to dynamically set Stop Loss distances:
    high volatility market -> wider stop loss, smaller lot size.
    low volatility market -> tighter stop loss, larger lot size.
    """
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    # Take max across all three definitions
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Smooth with Wilder's method
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr.fillna(tr1)

def calculate_adx(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculates Average Directional Index (ADX).
    
    Measures trend STRENGTH, regardless of direction.
    - ADX > 25 indicates a strong trending market (good for trend-following strategies).
    - ADX < 20 indicates a choppy, sideways market (trend strategies will get whipsawed).
    
    We use ADX as a filter: if ADX < 22, we skip trades because the market has no clear direction.
    """
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    # Directional movement (+DM and -DM)
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    atr = calculate_atr(high, low, close, period)
    atr_clean = atr.replace(0, np.nan)
    
    # +DI and -DI (normalized by ATR)
    plus_di = 100.0 * (pd.Series(plus_dm, index=high.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr_clean)
    minus_di = 100.0 * (pd.Series(minus_dm, index=low.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr_clean)
    
    # Directional Index (DX)
    dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    
    # Smooth DX to get ADX
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean().fillna(0.0)
    
    return adx, plus_di.fillna(0.0), minus_di.fillna(0.0)

def calculate_volume_anomaly(volume: pd.Series, period: int = 20) -> Tuple[pd.Series, pd.Series]:
    """
    Checks if current bar volume is unusually high compared to its 20-period average.
    Returns (rolling_mean_volume, volume_ratio).
    If volume_ratio > 1.8, institutional participants are likely entering the market.
    """
    mean_vol = volume.rolling(window=period, min_periods=1).mean()
    ratio = volume / mean_vol.replace(0, np.nan)
    return mean_vol, ratio.fillna(1.0)
