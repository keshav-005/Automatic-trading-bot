"""
Quantitative Analytics & Performance Metrics Module
Author: Computer Science Student Project

This module calculates standard financial performance benchmarks.
Key interview talking point:
"Win rate by itself is a vanity metric. What matters in algorithmic trading is:
1. Sharpe Ratio (risk-adjusted return)
2. Maximum Drawdown (worst peak-to-valley loss)
3. Profit Factor (Gross Profits / Gross Losses)
4. Payoff Ratio (Average Win vs Average Loss)"
"""

from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from execution.broker import TradeRecord

class PerformanceAnalytics:
    """
    Computes performance statistics from completed trades and equity history.
    """

    @staticmethod
    def calculate_trade_metrics(trades: List[TradeRecord], initial_balance: float = 10000.0) -> Dict:
        """
        Analyzes the list of closed trades:
        - Win Rate % = (Winning Trades / Total Trades) * 100
        - Profit Factor = Sum(Profits) / Sum(|Losses|)
        - Net Realized PnL and ROI %
        - Payoff Ratio = Average Win / Average Loss
        """
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate_pct': 0.0,
                'profit_factor': 0.0,
                'net_pnl': 0.0,
                'roi_pct': 0.0,
                'gross_profit': 0.0,
                'gross_loss': 0.0,
                'avg_trade_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'payoff_ratio': 0.0
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

        # Profit Factor: Gross Profit divided by Gross Loss
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
        Calculates risk-adjusted metrics across the historical equity curve:
        
        1. Sharpe Ratio:
           Formula: (Mean(Returns) - Risk_Free_Rate) / Std(Returns) * sqrt(252)
           Measures excess return earned per unit of total risk.
           
        2. Sortino Ratio:
           Formula: (Mean(Returns) - Risk_Free_Rate) / Downside_Std * sqrt(252)
           Similar to Sharpe, but only penalizes downside volatility (negative returns).
           
        3. Maximum Drawdown (MDD):
           Formula: max((Peak_Equity - Current_Equity) / Peak_Equity)
           The largest drop from an all-time peak to a subsequent low.
        """
        if len(equity_series) < 2:
            return {
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'max_drawdown_dollars': 0.0,
                'max_drawdown_pct': 0.0,
                'current_equity': equity_series[-1] if equity_series else 10000.0,
                'peak_equity': equity_series[-1] if equity_series else 10000.0
            }

        eq = np.array(equity_series)
        
        # Percentage returns between consecutive equity points
        returns = np.diff(eq) / eq[:-1]
        
        # Calculate Peak and Drawdowns
        peak = np.maximum.accumulate(eq)
        drawdown_dollars = peak - eq
        drawdown_pct = np.where(peak > 0, drawdown_dollars / peak, 0.0)
        
        max_dd_dollars = round(float(np.max(drawdown_dollars)), 2)
        max_dd_pct = round(float(np.max(drawdown_pct)) * 100.0, 2)

        # Annualized Sharpe (assuming 252 trading periods per year)
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        rf_per_period = risk_free_rate / 252.0

        if std_ret > 1e-7:
            sharpe = (mean_ret - rf_per_period) / std_ret * np.sqrt(252.0)
        else:
            sharpe = 0.0

        # Downside deviation for Sortino (only negative returns relative to risk-free rate)
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
    def generate_full_report(trades: List[TradeRecord], equity_snapshots: List[Dict], initial_balance: float = 10000.0) -> Dict:
        """Combines trade execution stats and equity metrics into one complete dictionary."""
        equity_series = [s['equity'] for s in equity_snapshots] if equity_snapshots else [initial_balance]
        trade_metrics = PerformanceAnalytics.calculate_trade_metrics(trades, initial_balance)
        portfolio_metrics = PerformanceAnalytics.calculate_portfolio_metrics(equity_series)
        
        return {
            **trade_metrics,
            **portfolio_metrics
        }
