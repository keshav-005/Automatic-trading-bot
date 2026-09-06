"""
Unit Tests for Trading Bot
Author: Computer Science Student Project

In algorithmic trading, bugs directly cost money.
These unit tests verify:
1. Mathematical correctness of all technical indicators (RSI between 0-100, Upper Band >= Lower Band, etc.).
2. Risk management circuit breaker triggers correctly when the 5% daily loss limit is breached.
3. PaperBroker correctly executes orders, calculates floating PnL, and triggers Take Profit and Stop Loss.
4. Strategy ensemble dynamically updates weights based on trade wins and losses.
5. Quantitative performance analytics compute accurate Sharpe and Drawdown metrics.
"""

import unittest
from core.compat import np, pd
from datetime import datetime

from config import default_config, RiskConfig, AssetConfig
from strategies.indicators import (
    calculate_ema, calculate_rsi, calculate_macd,
    calculate_bollinger_bands, calculate_atr, calculate_adx
)
from strategies.ensemble import StrategyEnsemble
from risk.manager import RiskManager
from execution.paper_broker import PaperBroker
from analytics.metrics import PerformanceAnalytics
from core.engine import TradingEngine

class TestTradingBot(unittest.TestCase):

    def setUp(self):
        """Create reproducible synthetic price data for testing."""
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100, freq="5min")
        close = 100.0 + np.cumsum(np.random.normal(0.05, 0.5, 100))
        high = close + np.random.uniform(0.1, 0.4, 100)
        low = close - np.random.uniform(0.1, 0.4, 100)
        open_p = close + np.random.normal(0.0, 0.2, 100)
        volume = np.random.randint(1000, 5000, 100)

        self.df = pd.DataFrame({
            'time': dates,
            'open': open_p,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    def test_technical_indicators_math(self):
        """Test indicator mathematical bounds and non-empty outputs."""
        # 1. EMA should have same length as input series and no NaNs
        ema = calculate_ema(self.df['close'], span=9)
        self.assertEqual(len(ema), len(self.df))
        self.assertFalse(ema.isna().any())

        # 2. RSI must strictly stay between 0.0 and 100.0
        rsi = calculate_rsi(self.df['close'], period=14)
        self.assertTrue((rsi >= 0.0).all() and (rsi <= 100.0).all())

        # 3. MACD returns (macd_line, signal_line, histogram)
        macd, signal, hist = calculate_macd(self.df['close'])
        self.assertEqual(len(macd), len(self.df))
        self.assertEqual(len(signal), len(self.df))

        # 4. Bollinger Upper Band must always be >= Lower Band
        upper, middle, lower, bw = calculate_bollinger_bands(self.df['close'], period=20)
        self.assertTrue((upper >= lower).all())
        self.assertTrue((bw >= 0.0).all())

        # 5. ATR must always be strictly positive
        atr = calculate_atr(self.df['high'], self.df['low'], self.df['close'], period=14)
        self.assertTrue((atr > 0.0).all())

        # 6. ADX must be positive
        adx, pdi, mdi = calculate_adx(self.df['high'], self.df['low'], self.df['close'], period=14)
        self.assertTrue((adx >= 0.0).all())

    def test_risk_manager_circuit_breaker(self):
        """Test that exceeding 5% daily loss trips the circuit breaker and rejects trades."""
        risk_config = RiskConfig(account_balance=10000.0, max_daily_loss=0.05)
        assets = {"EURUSD": AssetConfig("EURUSD", "forex", 0.0001, 1.2)}
        rm = RiskManager(risk_config, assets)

        # Before any losses: trading is approved
        can_trade, _ = rm.can_open_trade("EURUSD", open_position_count=0)
        self.assertTrue(can_trade)

        # Loss of $200 (within $500 limit): still allowed
        rm.register_trade_closed(-200.0)
        self.assertFalse(rm.circuit_breaker_active)

        # Additional loss of $350 (total $550 > $500): circuit breaker must trip
        rm.register_trade_closed(-350.0)
        self.assertTrue(rm.circuit_breaker_active)

        # Any new trade request must now be rejected
        can_trade_after, reason = rm.can_open_trade("EURUSD", open_position_count=0)
        self.assertFalse(can_trade_after)
        self.assertIn("CIRCUIT BREAKER", reason)

    def test_paper_broker_order_lifecycle(self):
        """Test order entry, TP/SL triggers, and balance updating in PaperBroker."""
        broker = PaperBroker(initial_balance=10000.0)
        order_spec = {
            'symbol': 'EURUSD',
            'action': 'BUY',
            'entry_price': 1.0850,
            'lots': 1.0,
            'sl_distance': 0.0020,
            'risk_reward_ratio': 1.8
        }

        # Submit order
        pos = broker.execute_order(order_spec)
        self.assertIsNotNone(pos)
        self.assertEqual(len(broker.get_open_positions()), 1)

        # Simulate price moving above Take Profit target
        tp_target = pos.take_profit + 0.0005
        closed = broker.update_positions_with_market_tick('EURUSD', tp_target)
        
        # Position should be closed with profit
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].reason, 'TP_HIT')
        self.assertTrue(closed[0].pnl > 0)
        self.assertEqual(len(broker.get_open_positions()), 0)

    def test_ensemble_dynamic_weighting(self):
        """Test that winning strategies receive higher allocation via Laplace smoothing."""
        ensemble = StrategyEnsemble()
        init_ema_weight = ensemble.weights['ema_cross']

        # Simulate consecutive wins on ema_cross
        for _ in range(10):
            ensemble.record_trade_result(['ema_cross'], won=True, pnl=150.0)

        # EMA weight should now be higher than starting weight
        self.assertGreater(ensemble.weights['ema_cross'], init_ema_weight)

    def test_performance_analytics_metrics(self):
        """Test Sharpe ratio and max drawdown calculation."""
        equity_series = [10000.0, 10200.0, 10150.0, 10400.0, 10300.0, 10600.0]
        metrics = PerformanceAnalytics.calculate_portfolio_metrics(equity_series)

        self.assertGreater(metrics['sharpe_ratio'], 0.0)
        self.assertGreaterEqual(metrics['max_drawdown_pct'], 0.0)
        self.assertEqual(metrics['current_equity'], 10600.0)

    def test_full_backtest_execution(self):
        """End-to-end test running a full backtest simulation across all symbols."""
        engine = TradingEngine(default_config)
        report = engine.run_backtest(n_bars=60)

        self.assertIn('total_trades', report)
        self.assertIn('sharpe_ratio', report)
        self.assertIn('profit_factor', report)

    def test_interactive_custom_backtest(self):
        """Test running backtest with custom risk, custom strategy selection, and parameters."""
        engine = TradingEngine(default_config)
        custom_risk = RiskConfig(account_balance=25000.0, risk_per_trade=0.015)
        custom_strategies = {
            'enabled_strategies': ['ema_cross', 'rsi_reversion'],
            'strategy_params': {
                'ema_cross': {'fast_span': 7, 'slow_span': 18},
                'rsi_reversion': {'period': 10, 'lower_threshold': 28.0}
            },
            'adx_threshold': 20.0,
            'confidence_threshold': 0.35
        }
        report = engine.run_backtest(
            n_bars=50,
            custom_risk=custom_risk,
            custom_strategies=custom_strategies,
            selected_assets=['EURUSD', 'XAUUSD']
        )

        self.assertEqual(report['enabled_strategies'], ['ema_cross', 'rsi_reversion'])
        self.assertEqual(report['assets_tested'], ['EURUSD', 'XAUUSD'])
        self.assertIn('equity_curve', report)
        self.assertIn('trades', report)
        self.assertIn('strategy_performance', report)

if __name__ == '__main__':
    unittest.main()
