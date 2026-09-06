"""
Core trading engine — coordinates data, signals, risk, and execution.

Pipeline per cycle:
    MarketDataFeed → StrategyEnsemble → RiskManager → Broker → Analytics
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from config import TradingConfig, default_config
from data.feed import MarketDataFeed
from strategies.ensemble import StrategyEnsemble
from risk.manager import RiskManager
from execution.broker import BaseBroker, Position, TradeRecord
from execution.paper_broker import PaperBroker
from execution.mt5_broker import MT5Broker
from analytics.metrics import PerformanceAnalytics


class TradingEngine:
    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or default_config

        self.feed = MarketDataFeed(seed=42)

        self.ensemble = StrategyEnsemble(
            initial_weights=self.config.strategies.weights.copy(),
            adx_threshold=self.config.strategies.adx_trend_threshold
        )

        self.risk_manager = RiskManager(self.config.risk, self.config.assets)

        if self.config.execution_mode == 'mt5':
            self.broker: BaseBroker = MT5Broker(
                account=self.config.mt5_account,
                password=self.config.mt5_password,
                server=self.config.mt5_server
            )
        else:
            self.broker = PaperBroker(
                initial_balance=self.config.risk.account_balance,
                assets=self.config.assets
            )

        self.is_running = False
        self.cycle_count = 0
        self.latest_signals: Dict[str, Dict] = {}
        self.event_logs: List[Dict] = []
        self._lock = threading.Lock()

    def log_event(self, level: str, message: str, metadata: Optional[Dict] = None):
        """Append a timestamped log entry and print it to stdout."""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = {
            'time': timestamp,
            'level': level,
            'message': message,
            'metadata': metadata or {}
        }
        with self._lock:
            self.event_logs.append(entry)
            # Keep buffer bounded to avoid unbounded memory growth
            if len(self.event_logs) > 100:
                self.event_logs.pop(0)
        print(f"[{timestamp}] [{level.upper()}] {message}")

    def process_symbol_cycle(self, symbol: str) -> Optional[Position]:
        """
        One full evaluation pass for a single symbol:

        1. Fetch the latest price tick and update open positions (check SL/TP).
        2. Pull the last 100 bars for indicator calculations.
        3. Run the strategy ensemble and collect a consensus signal.
        4. Ask the risk manager if we're allowed to open a new position.
        5. Size the position using ATR-based lot calculation.
        6. Submit the order to the broker.
        """
        tick = self.feed.stream_next_tick(symbol)
        closed_trades = self.broker.update_positions_with_market_tick(symbol, tick['price'])

        for trade in closed_trades:
            self.risk_manager.register_trade_closed(trade.pnl)
            won = trade.pnl > 0
            self.ensemble.record_trade_result(trade.contributing_strategies, won, trade.pnl)
            tag = "WIN" if won else "LOSS"
            self.log_event(
                "trade",
                f"{tag}: {trade.symbol} {trade.action} closed ({trade.reason}) | PnL: ${trade.pnl:+.2f}"
            )

        df = self.feed.get_latest_dataframe(symbol, lookback=100)
        action, confidence, individual_signals = self.ensemble.evaluate_all(symbol, df)

        self.latest_signals[symbol] = {
            'action': action or 'HOLD',
            'confidence': confidence,
            'price': tick['price'],
            'indicators': {k: v.action for k, v in individual_signals.items()}
        }

        if not action:
            return None

        open_positions = self.broker.get_open_positions()
        is_approved, rejection_reason = self.risk_manager.can_open_trade(symbol, len(open_positions))

        if not is_approved:
            self.log_event("risk", f"Signal {action} on {symbol} skipped: {rejection_reason}")
            return None

        current_equity = self.broker.get_equity()
        order_spec = self.risk_manager.calculate_position_order(
            symbol=symbol,
            signal_action=action,
            current_price=tick['price'],
            df=df,
            current_equity=current_equity
        )

        if not order_spec:
            return None

        contributing = [name for name, sig in individual_signals.items() if sig.action == action]
        position = self.broker.execute_order(order_spec, contributing_strategies=contributing)

        if position:
            self.risk_manager.record_trade_opened(symbol)
            self.log_event(
                "order",
                f"ENTRY: {action} {order_spec['lots']} lots {symbol} @ {position.entry_price:.4f} "
                f"(SL: {position.stop_loss:.4f} | TP: {position.take_profit:.4f} | Risk: ${order_spec['risk_amount']:.2f})"
            )
            return position

        return None

    def run_cycle_all_assets(self):
        """Run one evaluation cycle across every configured symbol."""
        self.cycle_count += 1
        for symbol in self.config.assets.keys():
            try:
                self.process_symbol_cycle(symbol)
            except Exception as e:
                self.log_event("error", f"Error on {symbol}: {str(e)}")

    def run_backtest(self, n_bars: int = 300) -> Dict[str, Any]:
        """
        Bar-by-bar historical simulation across all configured symbols.

        Uses isolated broker/risk/ensemble instances so it doesn't mutate live state.
        Closes any remaining open positions at the final bar price before reporting.
        """
        self.log_event("backtest", f"Running {n_bars}-bar backtest across {len(self.config.assets)} assets...")

        backtest_broker = PaperBroker(
            initial_balance=self.config.risk.account_balance,
            assets=self.config.assets
        )
        backtest_risk = RiskManager(self.config.risk, self.config.assets)
        backtest_ensemble = StrategyEnsemble(
            initial_weights=self.config.strategies.weights.copy(),
            adx_threshold=self.config.strategies.adx_trend_threshold
        )

        historical_data = {
            sym: self.feed.generate_historical_ohlcv(sym, n_bars=n_bars)
            for sym in self.config.assets.keys()
        }

        # Skip the first 35 bars so indicators have enough history to warm up
        warmup = 35
        for t in range(warmup, n_bars):
            for symbol, df_full in historical_data.items():
                df_window = df_full.iloc[:t].copy()
                curr_bar = df_window.iloc[-1]
                curr_price = float(curr_bar['close'])

                # Check high and low for SL/TP hits within the bar
                for pos in list(backtest_broker.get_open_positions()):
                    if pos.symbol == symbol:
                        backtest_broker.update_positions_with_market_tick(symbol, float(curr_bar['high']))
                        backtest_broker.update_positions_with_market_tick(symbol, float(curr_bar['low']))

                action, conf, individual = backtest_ensemble.evaluate_all(symbol, df_window)
                if action:
                    can_trade, _ = backtest_risk.can_open_trade(symbol, len(backtest_broker.get_open_positions()))
                    if can_trade:
                        order_spec = backtest_risk.calculate_position_order(
                            symbol=symbol,
                            signal_action=action,
                            current_price=curr_price,
                            df=df_window,
                            current_equity=backtest_broker.get_equity()
                        )
                        if order_spec:
                            contributing = [name for name, s in individual.items() if s.action == action]
                            backtest_broker.execute_order(order_spec, contributing)
                            backtest_risk.record_trade_opened(symbol)

        final_prices = {sym: float(df.iloc[-1]['close']) for sym, df in historical_data.items()}
        backtest_broker.close_all_positions(final_prices, reason="BACKTEST_END")

        report = PerformanceAnalytics.generate_full_report(
            trades=backtest_broker.get_closed_trades(),
            equity_snapshots=backtest_broker.equity_history,
            initial_balance=self.config.risk.account_balance
        )
        report['strategy_weights'] = backtest_ensemble.weights
        self.log_event(
            "backtest",
            f"Done: {report['total_trades']} trades | Win: {report['win_rate_pct']}% | "
            f"Sharpe: {report['sharpe_ratio']} | PnL: ${report['net_pnl']:+.2f}"
        )
        return report

    def get_telemetry(self) -> Dict[str, Any]:
        """Snapshot of current engine state — consumed by the web dashboard."""
        equity = self.broker.get_equity()
        balance = self.broker.get_balance()

        open_pos = [
            {
                'id': p.id,
                'symbol': p.symbol,
                'action': p.action,
                'lots': p.lots,
                'entry_price': p.entry_price,
                'current_price': p.current_price,
                'stop_loss': p.stop_loss,
                'take_profit': p.take_profit,
                'unrealized_pnl': p.unrealized_pnl
            }
            for p in self.broker.get_open_positions()
        ]

        closed = [
            {
                'id': t.id,
                'symbol': t.symbol,
                'action': t.action,
                'lots': t.lots,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'pnl': t.pnl,
                'reason': t.reason,
                'close_time': t.close_time.strftime("%H:%M:%S")
            }
            for t in reversed(self.broker.get_closed_trades()[-15:])
        ]

        metrics = PerformanceAnalytics.generate_full_report(
            trades=self.broker.get_closed_trades(),
            equity_snapshots=getattr(self.broker, 'equity_history', []),
            initial_balance=self.config.risk.account_balance
        )

        return {
            'equity': round(equity, 2),
            'balance': round(balance, 2),
            'open_positions': open_pos,
            'closed_trades': closed,
            'metrics': metrics,
            'signals': self.latest_signals,
            'strategy_weights': self.ensemble.weights,
            'logs': self.event_logs[-20:],
            'cycle_count': self.cycle_count,
            'circuit_breaker': self.risk_manager.circuit_breaker_active
        }
