"""
Technical indicators — implemented directly with NumPy/Pandas.

We avoid third-party indicator libraries (TA-Lib, pandas-ta) because:
- TA-Lib requires compiled C extensions that fail on restrictive environments.
- pandas-ta has numba compatibility issues on Python 3.12+.
- Writing the formulas ourselves makes the math auditable and dependency-free.
"""

from core.compat import np, pd
from typing import Tuple


def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """
    Exponential Moving Average.
    alpha = 2 / (span + 1) — recent bars are weighted more than older ones.
    """
    return series.ewm(span=span, adjust=False).mean()


def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average — unweighted mean over a rolling window."""
    return series.rolling(window=window, min_periods=1).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index using Wilder's smoothing (alpha = 1/period).

    RSI = 100 - 100 / (1 + avg_gain / avg_loss)
    Clamped to [0, 100]. NaN warmup values are filled with 50 (neutral).
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def calculate_macd(
    series: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD = EMA(fast) - EMA(slow).
    Signal = EMA(MACD, signal_period).
    Histogram = MACD - Signal.
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
    Bollinger Bands and normalized bandwidth.

    middle = SMA(period)
    upper  = middle + 2 * std(period)
    lower  = middle - 2 * std(period)
    bandwidth = (upper - lower) / middle

    Low bandwidth (the "squeeze") precedes high-volatility breakout moves.
    """
    middle = calculate_sma(series, period)
    std = series.rolling(window=period, min_periods=1).std(ddof=0).fillna(0.0)

    upper = middle + (std * std_dev_multiplier)
    lower = middle - (std * std_dev_multiplier)

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
    Average True Range — volatility measure that accounts for overnight gaps.

    True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    ATR = Wilder-smoothed True Range over `period` bars.
    """
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr.fillna(tr1)


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Average Directional Index — measures trend strength, not direction.

    ADX > 25 → strong trend. ADX < 20 → choppy/ranging market.
    We use ADX as a trade filter: signals are skipped when ADX < 22.

    Returns (ADX, +DI, -DI).
    """
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = calculate_atr(high, low, close, period)
    atr_clean = atr.replace(0, np.nan)

    plus_di = 100.0 * (pd.Series(plus_dm, index=high.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr_clean)
    minus_di = 100.0 * (pd.Series(minus_dm, index=low.index).ewm(alpha=1.0 / period, adjust=False).mean() / atr_clean)

    dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean().fillna(0.0)

    return adx, plus_di.fillna(0.0), minus_di.fillna(0.0)


def calculate_volume_anomaly(volume: pd.Series, period: int = 20) -> Tuple[pd.Series, pd.Series]:
    """
    Volume relative to its rolling mean.

    Returns (rolling_mean, ratio). ratio > 1.8 suggests institutional participation.
    """
    mean_vol = volume.rolling(window=period, min_periods=1).mean()
    ratio = volume / mean_vol.replace(0, np.nan)
    return mean_vol, ratio.fillna(1.0)
