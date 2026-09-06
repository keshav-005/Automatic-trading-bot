"""
Market data feed — generates realistic synthetic OHLCV candles.

Uses Geometric Brownian Motion with periodic volatility regime changes
and volume spikes. Works entirely offline — no API keys or subscriptions needed.
"""

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from core.compat import np, pd


class MarketDataFeed:
    """Supplies realistic multi-asset OHLCV data for backtesting and live simulation."""

    # Starting price and volatility profiles per instrument
    ASSET_PROFILES = {
        "EURUSD": {"initial_price": 1.0850, "volatility": 0.0006, "drift": 0.00001,  "point_size": 0.0001},
        "GBPUSD": {"initial_price": 1.2720, "volatility": 0.0008, "drift": 0.00001,  "point_size": 0.0001},
        "USDJPY": {"initial_price": 154.50, "volatility": 0.0800, "drift": 0.0005,   "point_size": 0.01},
        "USDCAD": {"initial_price": 1.3650, "volatility": 0.0007, "drift": -0.00001, "point_size": 0.0001},
        "XAUUSD": {"initial_price": 2380.0, "volatility": 2.2000, "drift": 0.0500,   "point_size": 0.01},
        "XAGUSD": {"initial_price": 30.50,  "volatility": 0.0600, "drift": 0.0020,   "point_size": 0.001},
        "USOIL":  {"initial_price": 78.50,  "volatility": 0.1500, "drift": 0.0010,   "point_size": 0.01},
        "NAS100": {"initial_price": 18500., "volatility": 15.000, "drift": 1.2000,   "point_size": 0.1},
    }

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

        self.cached_history: Dict[str, pd.DataFrame] = {}
        self.current_live_prices: Dict[str, float] = {
            sym: profile["initial_price"] for sym, profile in self.ASSET_PROFILES.items()
        }

    def generate_historical_ohlcv(self, symbol: str, n_bars: int = 250, timeframe_minutes: int = 5) -> pd.DataFrame:
        """
        Build a synthetic OHLCV DataFrame for the given symbol.

        - Price steps are Gaussian with instrument-specific volatility and drift.
        - Wicks are modelled with exponential random offsets.
        - Every 30 bars a volatility regime is resampled to simulate quiet vs news-driven markets.
        - Results are cached so repeated calls with the same bar count skip regeneration.
        """
        if symbol in self.cached_history and len(self.cached_history[symbol]) >= n_bars:
            return self.cached_history[symbol].iloc[-n_bars:].copy()

        profile = self.ASSET_PROFILES.get(symbol, {
            "initial_price": 100.0, "volatility": 0.1, "drift": 0.0001, "point_size": 0.01
        })

        price = profile["initial_price"]
        vol = profile["volatility"]
        drift = profile["drift"]

        now = datetime.now(timezone.utc)
        timestamps = [now - timedelta(minutes=(n_bars - i) * timeframe_minutes) for i in range(n_bars)]

        opens, highs, lows, closes, volumes = [], [], [], [], []
        regime = 1.0

        for i in range(n_bars):
            if i % 30 == 0:
                regime = random.choice([0.7, 1.0, 1.6, 2.2])

            step_vol = vol * regime
            delta = np.random.normal(drift, step_vol)

            bar_open = price
            bar_close = price + delta

            wick_high = abs(np.random.exponential(step_vol * 0.6))
            wick_low = abs(np.random.exponential(step_vol * 0.6))

            bar_high = max(bar_open, bar_close) + wick_high
            bar_low = min(bar_open, bar_close) - wick_low

            base_vol = random.randint(800, 2200)
            if regime > 1.5:
                base_vol = int(base_vol * random.uniform(1.8, 3.2))

            opens.append(round(bar_open, 5))
            highs.append(round(bar_high, 5))
            lows.append(round(bar_low, 5))
            closes.append(round(bar_close, 5))
            volumes.append(base_vol)

            price = bar_close

        df = pd.DataFrame({
            'time': timestamps,
            'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes
        })

        self.cached_history[symbol] = df
        self.current_live_prices[symbol] = closes[-1]
        return df.copy()

    def stream_next_tick(self, symbol: str) -> Dict:
        """Simulate a single live price tick and update the latest candle in the cache."""
        profile = self.ASSET_PROFILES.get(symbol, {"volatility": 0.0005, "point_size": 0.0001})
        current_price = self.current_live_prices.get(symbol, 1.0)

        tick_delta = np.random.normal(0.0, profile["volatility"] * 0.25)
        new_price = round(max(0.0001, current_price + tick_delta), 5)
        self.current_live_prices[symbol] = new_price

        if symbol in self.cached_history:
            df = self.cached_history[symbol]
            last_idx = df.index[-1]
            df.loc[last_idx, 'close'] = new_price
            df.loc[last_idx, 'high'] = max(df.loc[last_idx, 'high'], new_price)
            df.loc[last_idx, 'low'] = min(df.loc[last_idx, 'low'], new_price)
            df.loc[last_idx, 'volume'] += random.randint(10, 40)

        return {
            'symbol': symbol,
            'price': new_price,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'change': round(new_price - current_price, 5)
        }

    def get_latest_dataframe(self, symbol: str, lookback: int = 100) -> pd.DataFrame:
        """Return the last N bars for the symbol, generating history if needed."""
        if symbol not in self.cached_history:
            return self.generate_historical_ohlcv(symbol, n_bars=lookback)
        return self.cached_history[symbol].iloc[-lookback:].copy()
