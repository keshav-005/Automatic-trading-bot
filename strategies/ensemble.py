"""
Multi-Strategy Ensemble Module
Author: Computer Science Student Project

Why combine multiple strategies instead of just using one?
In quantitative finance, no single indicator works in all market conditions:
- Moving Average Crossovers make money in trending markets, but lose money in choppy/ranging markets.
- RSI Mean Reversion makes money in choppy/ranging markets, but gets destroyed in runaway trends.
- Bollinger Squeezes catch sudden breakouts after quiet consolidation periods.

By combining all 6 strategies into an Ensemble and requiring ADX trend confirmation,
we get much higher quality signals and reduce false breakout trades.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np

from strategies.indicators import (
    calculate_ema, calculate_rsi, calculate_macd,
    calculate_bollinger_bands, calculate_atr, calculate_adx,
    calculate_volume_anomaly
)
from strategies.sentiment import FinancialSentimentAnalyzer

@dataclass
class StrategySignal:
    """
    Standard data container for a signal emitted by any strategy.
    action: 'BUY', 'SELL', or 'HOLD'
    confidence: float between 0.0 and 1.0
    strategy_name: string identifier
    metadata: optional dictionary with debug values (e.g., current RSI, EMA levels)
    """
    action: str
    confidence: float
    strategy_name: str
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class BaseStrategy(ABC):
    """Abstract base class that every trading strategy must inherit from."""
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        """Takes recent price bars (df) and decides BUY, SELL, or HOLD."""
        pass

class EMACrossStrategy(BaseStrategy):
    """
    Strategy 1: EMA 9 / 21 Trend Following
    - BUY when Fast EMA (9) crosses above Slow EMA (21) and price is above slow EMA.
    - SELL when Fast EMA (9) crosses below Slow EMA (21) and price is below slow EMA.
    """
    def __init__(self, fast_span: int = 9, slow_span: int = 21):
        super().__init__("ema_cross")
        self.fast_span = fast_span
        self.slow_span = slow_span

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        # Need at least slow_span bars of history to compute EMA
        if len(df) < self.slow_span:
            return StrategySignal('HOLD', 0.0, self.name)
            
        ema_fast = calculate_ema(df['close'], self.fast_span)
        ema_slow = calculate_ema(df['close'], self.slow_span)
        curr_close = df['close'].iloc[-1]
        
        fast_now, slow_now = ema_fast.iloc[-1], ema_slow.iloc[-1]
        fast_prev, slow_prev = ema_fast.iloc[-2], ema_slow.iloc[-2]
        
        # Bullish condition: Fast is above slow, and price is supporting above slow
        if fast_now > slow_now and curr_close > slow_now:
            # Stronger confidence if the crossover just happened on this bar
            confidence = 0.85 if fast_prev <= slow_prev else 0.65
            return StrategySignal('BUY', confidence, self.name, {'fast': fast_now, 'slow': slow_now})
            
        # Bearish condition: Fast is below slow, and price is resisting below slow
        elif fast_now < slow_now and curr_close < slow_now:
            confidence = 0.85 if fast_prev >= slow_prev else 0.65
            return StrategySignal('SELL', confidence, self.name, {'fast': fast_now, 'slow': slow_now})
            
        return StrategySignal('HOLD', 0.0, self.name)

class RSIReversionStrategy(BaseStrategy):
    """
    Strategy 2: Adaptive RSI Mean Reversion
    Instead of fixed 30/70 thresholds, we adapt thresholds using current market volatility.
    In higher volatility, price can stay oversold longer, so we widen the thresholds.
    """
    def __init__(self, period: int = 14):
        super().__init__("rsi_reversion")
        self.period = period

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < self.period + 5:
            return StrategySignal('HOLD', 0.0, self.name)
            
        rsi = calculate_rsi(df['close'], self.period)
        atr = calculate_atr(df['high'], df['low'], df['close'], self.period)
        
        curr_close = df['close'].iloc[-1]
        # Volatility ratio: how big is ATR relative to price
        volatility_ratio = (atr.iloc[-1] / curr_close) * 20.0
        
        # Dynamic boundaries: wider in high volatility, tighter in low volatility
        lower_threshold = max(22.0, 30.0 - volatility_ratio)
        upper_threshold = min(78.0, 70.0 + volatility_ratio)
        
        current_rsi = rsi.iloc[-1]
        if current_rsi < lower_threshold:
            conf = min(1.0, (lower_threshold - current_rsi) / 10.0 + 0.6)
            return StrategySignal('BUY', conf, self.name, {'rsi': current_rsi, 'threshold': lower_threshold})
        elif current_rsi > upper_threshold:
            conf = min(1.0, (current_rsi - upper_threshold) / 10.0 + 0.6)
            return StrategySignal('SELL', conf, self.name, {'rsi': current_rsi, 'threshold': upper_threshold})
            
        return StrategySignal('HOLD', 0.0, self.name, {'rsi': current_rsi})

class MACDMomentumStrategy(BaseStrategy):
    """
    Strategy 3: MACD Momentum with Volume Filter
    A MACD cross is much more reliable when backed by volume above average.
    """
    def __init__(self):
        super().__init__("macd_momentum")

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < 35:
            return StrategySignal('HOLD', 0.0, self.name)
            
        macd_line, signal_line, hist = calculate_macd(df['close'])
        mean_vol = df['volume'].rolling(20, min_periods=1).mean()
        
        # Ensure volume is at least 80% of normal to prevent trading on dead liquidity
        has_volume = df['volume'].iloc[-1] >= (mean_vol.iloc[-1] * 0.8)
        
        if macd_line.iloc[-1] > signal_line.iloc[-1] and hist.iloc[-1] > 0 and has_volume:
            conf = 0.85 if hist.iloc[-1] > hist.iloc[-2] else 0.60
            return StrategySignal('BUY', conf, self.name, {'macd': macd_line.iloc[-1], 'signal': signal_line.iloc[-1]})
        elif macd_line.iloc[-1] < signal_line.iloc[-1] and hist.iloc[-1] < 0 and has_volume:
            conf = 0.85 if hist.iloc[-1] < hist.iloc[-2] else 0.60
            return StrategySignal('SELL', conf, self.name, {'macd': macd_line.iloc[-1], 'signal': signal_line.iloc[-1]})
            
        return StrategySignal('HOLD', 0.0, self.name)

class BollingerSqueezeStrategy(BaseStrategy):
    """
    Strategy 4: Bollinger Band Squeeze Breakout
    When Bollinger bandwidth shrinks below 0.12, the market is coiled like a spring.
    When price breaks above upper band -> BUY.
    When price breaks below lower band -> SELL.
    """
    def __init__(self, period: int = 20, squeeze_cutoff: float = 0.12):
        super().__init__("bollinger_squeeze")
        self.period = period
        self.squeeze_cutoff = squeeze_cutoff

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < self.period:
            return StrategySignal('HOLD', 0.0, self.name)
            
        upper, middle, lower, bandwidth = calculate_bollinger_bands(df['close'], self.period)
        curr_close = df['close'].iloc[-1]
        curr_bw = bandwidth.iloc[-1]
        
        # Only trade if recent bandwidth was tight (the squeeze)
        if curr_bw < self.squeeze_cutoff:
            if curr_close > upper.iloc[-1]:
                return StrategySignal('BUY', 0.80, self.name, {'bandwidth': curr_bw, 'breakout': 'upper'})
            elif curr_close < lower.iloc[-1]:
                return StrategySignal('SELL', 0.80, self.name, {'bandwidth': curr_bw, 'breakout': 'lower'})
                
        return StrategySignal('HOLD', 0.0, self.name, {'bandwidth': curr_bw})

class VolumeAnomalyStrategy(BaseStrategy):
    """
    Strategy 5: Volume Spike Detection
    Identifies sudden institutional volume (> 1.8x the 20-bar average).
    If volume surges on a green candle -> BUY.
    If volume surges on a red candle -> SELL.
    """
    def __init__(self, period: int = 20):
        super().__init__("volume_anomaly")
        self.period = period

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < self.period:
            return StrategySignal('HOLD', 0.0, self.name)
            
        mean_vol, ratio = calculate_volume_anomaly(df['volume'], self.period)
        vol_ratio = ratio.iloc[-1]
        
        if vol_ratio > 1.8:
            curr_close = df['close'].iloc[-1]
            curr_open = df['open'].iloc[-1]
            if curr_close > curr_open:
                return StrategySignal('BUY', min(1.0, 0.5 + vol_ratio * 0.15), self.name, {'vol_ratio': vol_ratio})
            elif curr_close < curr_open:
                return StrategySignal('SELL', min(1.0, 0.5 + vol_ratio * 0.15), self.name, {'vol_ratio': vol_ratio})
                
        return StrategySignal('HOLD', 0.0, self.name)

class MarketSentimentStrategy(BaseStrategy):
    """
    Strategy 6: Financial News Sentiment
    Uses domain keyword analysis to determine market bias.
    """
    def __init__(self, analyzer: Optional[FinancialSentimentAnalyzer] = None):
        super().__init__("market_sentiment")
        self.analyzer = analyzer or FinancialSentimentAnalyzer()

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        score = self.analyzer.get_asset_sentiment(symbol)
        if score > 0.25:
            return StrategySignal('BUY', min(1.0, abs(score)), self.name, {'sentiment': score})
        elif score < -0.25:
            return StrategySignal('SELL', min(1.0, abs(score)), self.name, {'sentiment': score})
            
        return StrategySignal('HOLD', 0.0, self.name, {'sentiment': score})

class StrategyEnsemble:
    """
    Ensemble Orchestrator:
    1. Collects signals from all 6 strategies simultaneously.
    2. Checks ADX to verify market is actually trending (filters out choppy noise).
    3. Calculates a weighted voting score.
    4. Dynamically reallocates strategy weights after trades close (rewards winning strategies).
    """
    def __init__(self, initial_weights: Optional[Dict[str, float]] = None, adx_threshold: float = 22.0):
        self.adx_threshold = adx_threshold
        
        # Instantiate each strategy
        self.strategies: Dict[str, BaseStrategy] = {
            'ema_cross': EMACrossStrategy(),
            'rsi_reversion': RSIReversionStrategy(),
            'macd_momentum': MACDMomentumStrategy(),
            'bollinger_squeeze': BollingerSqueezeStrategy(),
            'volume_anomaly': VolumeAnomalyStrategy(),
            'market_sentiment': MarketSentimentStrategy()
        }
        
        # Starting weights
        self.weights = initial_weights or {
            'ema_cross': 0.25,
            'rsi_reversion': 0.20,
            'macd_momentum': 0.18,
            'bollinger_squeeze': 0.15,
            'volume_anomaly': 0.12,
            'market_sentiment': 0.10
        }
        self._normalize_weights()
        
        # Performance ledger for each strategy
        self.performance: Dict[str, Dict[str, float]] = {
            k: {'wins': 0, 'losses': 0, 'pnl': 0.0} for k in self.strategies
        }

    def _normalize_weights(self):
        """Ensures all weights sum up to exactly 1.0 (100%)."""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: round(v / total, 4) for k, v in self.weights.items()}

    def check_adx_trend(self, df: pd.DataFrame) -> bool:
        """
        Trend confirmation check:
        If ADX < 22, the market is choppy/flat. We avoid trading to save fees and avoid whipsaws.
        """
        if len(df) < 20:
            return True
        adx, _, _ = calculate_adx(df['high'], df['low'], df['close'])
        return float(adx.iloc[-1]) >= self.adx_threshold

    def evaluate_all(self, symbol: str, df: pd.DataFrame) -> Tuple[Optional[str], float, Dict[str, StrategySignal]]:
        """
        Evaluates all strategies and calculates the consensus vote.
        Returns:
            action: 'BUY', 'SELL', or None (no trade)
            confidence: float 0.0 to 1.0
            signals: dictionary of individual strategy signals
        """
        # Step 1: Run each strategy
        signals = {name: strat.evaluate(symbol, df) for name, strat in self.strategies.items()}
        
        # Step 2: Check trend filter
        if not self.check_adx_trend(df):
            return None, 0.0, signals
            
        # Step 3: Compute weighted voting score
        buy_score = 0.0
        sell_score = 0.0
        
        for name, sig in signals.items():
            weight = self.weights.get(name, 0.0)
            if sig.action == 'BUY':
                buy_score += weight * sig.confidence
            elif sig.action == 'SELL':
                sell_score += weight * sig.confidence
                
        # Step 4: Decision threshold (>40% confidence and clearly dominates opposite side)
        if buy_score > 0.40 and buy_score > (sell_score * 1.3):
            return 'BUY', round(buy_score, 3), signals
        elif sell_score > 0.40 and sell_score > (buy_score * 1.3):
            return 'SELL', round(sell_score, 3), signals
            
        return None, max(buy_score, sell_score), signals

    def record_trade_result(self, contributing_strategies: list, won: bool, pnl: float):
        """
        Called when a trade closes.
        Updates performance history and rebalances strategy weights using Laplace smoothing:
        new_weight = (wins + 1) / (wins + losses + 2)
        
        This prevents dividing by zero when a strategy has zero trades, while gradually
        rewarding strategies that produce winning trades.
        """
        for strat in contributing_strategies:
            if strat in self.performance:
                if won:
                    self.performance[strat]['wins'] += 1
                else:
                    self.performance[strat]['losses'] += 1
                self.performance[strat]['pnl'] += pnl
                
        total_trades = sum(s['wins'] + s['losses'] for s in self.performance.values())
        if total_trades >= 5:
            new_weights = {}
            for strat, stats in self.performance.items():
                w = stats['wins']
                l = stats['losses']
                # Laplace smoothing formula: (w + 1) / (w + l + 2)
                new_weights[strat] = (w + 1.0) / (w + l + 2.0)
                
            total = sum(new_weights.values())
            self.weights = {k: round(v / total, 4) for k, v in new_weights.items()}
