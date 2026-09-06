"""
Performance analytics — computes standard quantitative finance metrics from
closed trade records and equity history snapshots.
"""

from typing import List, Dict, Optional
from core.compat import np, pd
from execution.broker import TradeRecord


class PerformanceAnalytics:
    """
    Computes performance statistics from completed trades and equity history.

    Core metrics reported:
    - Win Rate, Profit Factor, Payoff Ratio (trade-level stats)
    - Sharpe Ratio, Sortino Ratio (risk-adjusted return)
    - Maximum Drawdown % (worst peak-to-valley decline)
    """

    @staticmethod
    def calculate_trade_metrics(trades: List[TradeRecord], initial_balance: float = 10000.0) -> Dict:
        if not trades:
            return {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'win_rate_pct': 0.0, 'profit_factor': 0.0, 'net_pnl': 0.0,
                'roi_pct': 0.0, 'gross_profit': 0.0, 'gross_loss': 0.0,
                'avg_trade_pnl': 0.0, 'avg_win': 0.0, 'avg_loss': 0.0,
                'max_win': 0.0, 'max_loss': 0.0, 'payoff_ratio': 0.0
            }

        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        total_trades = len(pnls)
        win_count = len(wins)
        loss_count = len(losses)

        win_rate = (win_count / total_trades) * 100.0 if total_trades > 0 else 0.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        net_pnl = round(sum(pnls), 2)
        roi_pct = round((net_pnl / initial_balance) * 100.0, 2)

        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)
        avg_win = (gross_profit / win_count) if win_count > 0 else 0.0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0.0
        payoff_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0

        return {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate_pct': round(win_rate, 2),
            'profit_factor': profit_factor,
            'net_pnl': net_pnl,
            'roi_pct': roi_pct,
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'avg_trade_pnl': round(float(np.mean(pnls)), 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'max_win': round(max(pnls), 2) if pnls else 0.0,
            'max_loss': round(min(pnls), 2) if pnls else 0.0,
            'payoff_ratio': payoff_ratio
        }

    @staticmethod
    def calculate_portfolio_metrics(equity_series: List[float], risk_free_rate: float = 0.02) -> Dict:
        """
        Compute Sharpe ratio, Sortino ratio, and maximum drawdown from the equity curve.

        Sharpe  = (mean_return - rf) / std_return * sqrt(252)
        Sortino = (mean_return - rf) / downside_std * sqrt(252)
        MDD     = max((peak_equity - current_equity) / peak_equity)
        """
        if len(equity_series) < 2:
            return {
                'sharpe_ratio': 0.0, 'sortino_ratio': 0.0,
                'max_drawdown_dollars': 0.0, 'max_drawdown_pct': 0.0,
                'current_equity': equity_series[-1] if equity_series else 10000.0,
                'peak_equity': equity_series[-1] if equity_series else 10000.0
            }

        eq = np.array(equity_series)
        returns = np.diff(eq) / eq[:-1]

        peak = np.maximum.accumulate(eq)
        drawdown_dollars = peak - eq
        drawdown_pct = np.where(peak > 0, drawdown_dollars / peak, 0.0)

        max_dd_dollars = round(float(np.max(drawdown_dollars)), 2)
        max_dd_pct = round(float(np.max(drawdown_pct)) * 100.0, 2)

        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        rf_per_period = risk_free_rate / 252.0

        sharpe = (mean_ret - rf_per_period) / std_ret * np.sqrt(252.0) if std_ret > 1e-7 else 0.0

        downside_returns = returns[returns < rf_per_period]
        if len(downside_returns) > 0:
            downside_std = np.sqrt(np.mean((downside_returns - rf_per_period) ** 2))
            sortino = (mean_ret - rf_per_period) / downside_std * np.sqrt(252.0) if downside_std > 1e-7 else 0.0
        else:
            sortino = sharpe * 1.5 if sharpe > 0 else 0.0

        return {
            'sharpe_ratio': round(float(sharpe), 2),
            'sortino_ratio': round(float(sortino), 2),
            'max_drawdown_dollars': max_dd_dollars,
            'max_drawdown_pct': max_dd_pct,
            'current_equity': round(float(eq[-1]), 2),
            'peak_equity': round(float(np.max(peak)), 2)
        }

    @staticmethod
    def generate_full_report(
        trades: List[TradeRecord],
        equity_snapshots: List[Dict],
        initial_balance: float = 10000.0
    ) -> Dict:
        """Merge trade-level and portfolio-level metrics into a single report dict."""
        equity_series = [s['equity'] for s in equity_snapshots] if equity_snapshots else [initial_balance]
        trade_metrics = PerformanceAnalytics.calculate_trade_metrics(trades, initial_balance)
        portfolio_metrics = PerformanceAnalytics.calculate_portfolio_metrics(equity_series)
        return {**trade_metrics, **portfolio_metrics}
