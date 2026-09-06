"""
Strategy ensemble — combines six independent trading strategies into one consensus signal.

Why an ensemble instead of a single indicator?
No single technical indicator works well in every market regime. Trend-following
strategies lose in choppy markets; mean-reversion strategies get destroyed in
strong trends. Combining six approaches with a weighted vote — and gating on ADX
trend strength — produces much higher-quality signals than any one method alone.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from core.compat import np, pd

from strategies.indicators import (
    calculate_ema, calculate_rsi, calculate_macd,
    calculate_bollinger_bands, calculate_atr, calculate_adx,
    calculate_volume_anomaly
)
from strategies.sentiment import FinancialSentimentAnalyzer


@dataclass
class StrategySignal:
    """Output of a single strategy evaluation."""
    action: str          # 'BUY', 'SELL', or 'HOLD'
    confidence: float    # 0.0 – 1.0
    strategy_name: str
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseStrategy(ABC):
    """All trading strategies inherit from this and implement evaluate()."""
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        pass


class EMACrossStrategy(BaseStrategy):
    """
    EMA 9/21 trend-following crossover.

    BUY  — fast EMA crosses above slow EMA and price is above slow EMA.
    SELL — fast EMA crosses below slow EMA and price is below slow EMA.
    Fresh crossovers (happened on the current bar) score higher confidence.
    """
    def __init__(self, fast_span: int = 9, slow_span: int = 21):
        super().__init__("ema_cross")
        self.fast_span = fast_span
        self.slow_span = slow_span

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < self.slow_span:
            return StrategySignal('HOLD', 0.0, self.name)

        ema_fast = calculate_ema(df['close'], self.fast_span)
        ema_slow = calculate_ema(df['close'], self.slow_span)
        curr_close = df['close'].iloc[-1]

        fast_now, slow_now = ema_fast.iloc[-1], ema_slow.iloc[-1]
        fast_prev, slow_prev = ema_fast.iloc[-2], ema_slow.iloc[-2]

        if fast_now > slow_now and curr_close > slow_now:
            confidence = 0.85 if fast_prev <= slow_prev else 0.65
            return StrategySignal('BUY', confidence, self.name, {'fast': fast_now, 'slow': slow_now})

        elif fast_now < slow_now and curr_close < slow_now:
            confidence = 0.85 if fast_prev >= slow_prev else 0.65
            return StrategySignal('SELL', confidence, self.name, {'fast': fast_now, 'slow': slow_now})

        return StrategySignal('HOLD', 0.0, self.name)


class RSIReversionStrategy(BaseStrategy):
    """
    Adaptive RSI mean-reversion.

    The overbought/oversold thresholds adapt based on ATR volatility,
    preventing premature counter-trend entries in high-momentum markets.
    """
    def __init__(self, period: int = 14, lower_threshold: float = 30.0, upper_threshold: float = 70.0):
        super().__init__("rsi_reversion")
        self.period = period
        self.lower_threshold = lower_threshold
        self.upper_threshold = upper_threshold

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < self.period + 5:
            return StrategySignal('HOLD', 0.0, self.name)

        rsi = calculate_rsi(df['close'], self.period)
        atr = calculate_atr(df['high'], df['low'], df['close'], self.period)

        curr_close = df['close'].iloc[-1]
        volatility_ratio = (atr.iloc[-1] / curr_close) * 20.0

        lower_bound = max(18.0, self.lower_threshold - volatility_ratio)
        upper_bound = min(82.0, self.upper_threshold + volatility_ratio)

        current_rsi = rsi.iloc[-1]
        if current_rsi < lower_bound:
            conf = min(1.0, (lower_bound - current_rsi) / 10.0 + 0.6)
            return StrategySignal('BUY', conf, self.name, {'rsi': current_rsi, 'threshold': lower_bound})
        elif current_rsi > upper_bound:
            conf = min(1.0, (current_rsi - upper_bound) / 10.0 + 0.6)
            return StrategySignal('SELL', conf, self.name, {'rsi': current_rsi, 'threshold': upper_bound})

        return StrategySignal('HOLD', 0.0, self.name, {'rsi': current_rsi})


class MACDMomentumStrategy(BaseStrategy):
    """
    MACD momentum with a volume confirmation filter.

    A MACD crossover is only acted on when volume is at least 80% of its 20-bar
    average — this avoids signals that fire during thin, low-liquidity periods.
    """
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, vol_factor: float = 0.8):
        super().__init__("macd_momentum")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.vol_factor = vol_factor

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < max(35, self.slow_period + self.signal_period):
            return StrategySignal('HOLD', 0.0, self.name)

        macd_line, signal_line, hist = calculate_macd(df['close'], self.fast_period, self.slow_period, self.signal_period)
        mean_vol = df['volume'].rolling(20, min_periods=1).mean()
        has_volume = df['volume'].iloc[-1] >= (mean_vol.iloc[-1] * self.vol_factor)

        if macd_line.iloc[-1] > signal_line.iloc[-1] and hist.iloc[-1] > 0 and has_volume:
            conf = 0.85 if hist.iloc[-1] > hist.iloc[-2] else 0.60
            return StrategySignal('BUY', conf, self.name, {'macd': macd_line.iloc[-1], 'signal': signal_line.iloc[-1]})
        elif macd_line.iloc[-1] < signal_line.iloc[-1] and hist.iloc[-1] < 0 and has_volume:
            conf = 0.85 if hist.iloc[-1] < hist.iloc[-2] else 0.60
            return StrategySignal('SELL', conf, self.name, {'macd': macd_line.iloc[-1], 'signal': signal_line.iloc[-1]})

        return StrategySignal('HOLD', 0.0, self.name)


class BollingerSqueezeStrategy(BaseStrategy):
    """
    Bollinger Band squeeze breakout.

    When bandwidth contracts below the squeeze_cutoff threshold, the market is in
    a low-volatility coil. A close outside the bands signals the expansion/breakout.
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

        if curr_bw < self.squeeze_cutoff:
            if curr_close > upper.iloc[-1]:
                return StrategySignal('BUY', 0.80, self.name, {'bandwidth': curr_bw, 'breakout': 'upper'})
            elif curr_close < lower.iloc[-1]:
                return StrategySignal('SELL', 0.80, self.name, {'bandwidth': curr_bw, 'breakout': 'lower'})

        return StrategySignal('HOLD', 0.0, self.name, {'bandwidth': curr_bw})


class VolumeAnomalyStrategy(BaseStrategy):
    """
    Institutional volume spike detector.

    When volume is more than multiplier × its rolling average, a large participant
    is likely active. Candle direction (open vs close) determines bias.
    """
    def __init__(self, period: int = 20, multiplier: float = 1.8):
        super().__init__("volume_anomaly")
        self.period = period
        self.multiplier = multiplier

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        if len(df) < self.period:
            return StrategySignal('HOLD', 0.0, self.name)

        mean_vol, ratio = calculate_volume_anomaly(df['volume'], self.period)
        vol_ratio = ratio.iloc[-1]

        if vol_ratio > self.multiplier:
            curr_close = df['close'].iloc[-1]
            curr_open = df['open'].iloc[-1]
            if curr_close > curr_open:
                return StrategySignal('BUY', min(1.0, 0.5 + vol_ratio * 0.15), self.name, {'vol_ratio': vol_ratio})
            elif curr_close < curr_open:
                return StrategySignal('SELL', min(1.0, 0.5 + vol_ratio * 0.15), self.name, {'vol_ratio': vol_ratio})

        return StrategySignal('HOLD', 0.0, self.name)


class MarketSentimentStrategy(BaseStrategy):
    """Financial news sentiment scoring via domain keyword analysis."""
    def __init__(self, analyzer: Optional[FinancialSentimentAnalyzer] = None, threshold: float = 0.25):
        super().__init__("market_sentiment")
        self.analyzer = analyzer or FinancialSentimentAnalyzer()
        self.threshold = threshold

    def evaluate(self, symbol: str, df: pd.DataFrame) -> StrategySignal:
        score = self.analyzer.get_asset_sentiment(symbol)
        if score > self.threshold:
            return StrategySignal('BUY', min(1.0, abs(score)), self.name, {'sentiment': score})
        elif score < -self.threshold:
            return StrategySignal('SELL', min(1.0, abs(score)), self.name, {'sentiment': score})

        return StrategySignal('HOLD', 0.0, self.name, {'sentiment': score})


class StrategyEnsemble:
    """
    Orchestrates any combination of trading strategies into a consensus signal.

    Workflow per bar:
    1. Collect signals from all active strategies.
    2. Gate on ADX — skip the vote entirely if the market isn't trending.
    3. Compute weighted BUY/SELL scores. The dominant side must exceed
       confidence_threshold AND be 1.3× the opposing score to trigger a trade.
    4. After each trade closes, update strategy win/loss records and rebalance
       weights using Laplace-smoothed empirical win rates.
    """
    def __init__(
        self,
        initial_weights: Optional[Dict[str, float]] = None,
        adx_threshold: float = 22.0,
        confidence_threshold: float = 0.40,
        enabled_strategies: Optional[list] = None,
        strategy_params: Optional[Dict[str, Dict]] = None
    ):
        self.adx_threshold = float(adx_threshold)
        self.confidence_threshold = float(confidence_threshold)
        params = strategy_params or {}

        all_factories = {
            'ema_cross': lambda: EMACrossStrategy(
                fast_span=int(params.get('ema_cross', {}).get('fast_span', 9)),
                slow_span=int(params.get('ema_cross', {}).get('slow_span', 21))
            ),
            'rsi_reversion': lambda: RSIReversionStrategy(
                period=int(params.get('rsi_reversion', {}).get('period', 14)),
                lower_threshold=float(params.get('rsi_reversion', {}).get('lower_threshold', 30.0)),
                upper_threshold=float(params.get('rsi_reversion', {}).get('upper_threshold', 70.0))
            ),
            'macd_momentum': lambda: MACDMomentumStrategy(
                fast_period=int(params.get('macd_momentum', {}).get('fast_period', 12)),
                slow_period=int(params.get('macd_momentum', {}).get('slow_period', 26)),
                signal_period=int(params.get('macd_momentum', {}).get('signal_period', 9))
            ),
            'bollinger_squeeze': lambda: BollingerSqueezeStrategy(
                period=int(params.get('bollinger_squeeze', {}).get('period', 20)),
                squeeze_cutoff=float(params.get('bollinger_squeeze', {}).get('squeeze_cutoff', 0.12))
            ),
            'volume_anomaly': lambda: VolumeAnomalyStrategy(
                period=int(params.get('volume_anomaly', {}).get('period', 20)),
                multiplier=float(params.get('volume_anomaly', {}).get('multiplier', 1.8))
            ),
            'market_sentiment': lambda: MarketSentimentStrategy(
                threshold=float(params.get('market_sentiment', {}).get('threshold', 0.25))
            )
        }

        if enabled_strategies:
            active_keys = [k for k in enabled_strategies if k in all_factories]
            if not active_keys:
                active_keys = list(all_factories.keys())
        else:
            active_keys = list(all_factories.keys())

        self.strategies: Dict[str, BaseStrategy] = {k: all_factories[k]() for k in active_keys}

        default_weights = {
            'ema_cross':         0.25,
            'rsi_reversion':     0.20,
            'macd_momentum':     0.18,
            'bollinger_squeeze': 0.15,
            'volume_anomaly':    0.12,
            'market_sentiment':  0.10
        }

        if initial_weights:
            self.weights = {k: float(initial_weights.get(k, default_weights.get(k, 1.0))) for k in self.strategies}
        else:
            self.weights = {k: default_weights.get(k, 1.0) for k in self.strategies}
        self._normalize_weights()

        self.performance: Dict[str, Dict[str, float]] = {
            k: {'wins': 0, 'losses': 0, 'pnl': 0.0} for k in self.strategies
        }

    def _normalize_weights(self):
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: round(v / total, 4) for k, v in self.weights.items()}

    def check_adx_trend(self, df: pd.DataFrame) -> bool:
        """Returns False when ADX is below the threshold — market is too choppy to trade."""
        if len(df) < 20:
            return True
        adx, _, _ = calculate_adx(df['high'], df['low'], df['close'])
        return float(adx.iloc[-1]) >= self.adx_threshold

    def evaluate_all(self, symbol: str, df: pd.DataFrame) -> Tuple[Optional[str], float, Dict[str, StrategySignal]]:
        """
        Returns (action, confidence, per-strategy signals).
        action is None if the ensemble doesn't reach a clear consensus.
        """
        signals = {name: strat.evaluate(symbol, df) for name, strat in self.strategies.items()}

        if not self.check_adx_trend(df):
            return None, 0.0, signals

        buy_score = 0.0
        sell_score = 0.0

        for name, sig in signals.items():
            weight = self.weights.get(name, 0.0)
            if sig.action == 'BUY':
                buy_score += weight * sig.confidence
            elif sig.action == 'SELL':
                sell_score += weight * sig.confidence

        if buy_score > self.confidence_threshold and buy_score > (sell_score * 1.3):
            return 'BUY', round(buy_score, 3), signals
        elif sell_score > self.confidence_threshold and sell_score > (buy_score * 1.3):
            return 'SELL', round(sell_score, 3), signals

        return None, max(buy_score, sell_score), signals

        return None, max(buy_score, sell_score), signals

    def record_trade_result(self, contributing_strategies: list, won: bool, pnl: float):
        """
        Update performance stats after a trade closes and rebalance weights.

        Weights are recalculated using Laplace smoothing once at least 5 trades
        have been recorded, preventing noisy early rebalancing:

            weight_i = (wins + 1) / (wins + losses + 2)
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
                new_weights[strat] = (w + 1.0) / (w + l + 2.0)

            total = sum(new_weights.values())
            self.weights = {k: round(v / total, 4) for k, v in new_weights.items()}
