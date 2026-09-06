"""
Risk Management Module
Author: Computer Science Student Project

In trading, amateurs focus only on entries, but professionals focus on RISK.
Even a 70% win-rate strategy will go bankrupt if position sizing is flawed.

This module implements two essential risk controls:
1. Dynamic ATR-based Position Sizing (we risk the same dollar amount on every trade,
   regardless of whether the market is volatile or quiet).
2. Daily Drawdown Circuit Breaker (if the account loses 5% in a single day,
   trading is halted immediately to protect capital from extreme market events).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict
from core.compat import pd

from config import RiskConfig, AssetConfig
from strategies.indicators import calculate_atr

class RiskManager:
    """
    Manages portfolio risk, calculates trade sizing, and enforces safety limits.
    """
    
    def __init__(self, config: RiskConfig, assets: Dict[str, AssetConfig]):
        self.config = config
        self.assets = assets
        
        # State tracking for daily metrics
        self.daily_start_balance = config.account_balance
        self.realized_daily_pnl = 0.0
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.last_trade_times: Dict[str, datetime] = {}

    def reset_daily_metrics(self, current_balance: float):
        """Called at the start of a new trading session to reset daily loss counters."""
        self.daily_start_balance = current_balance
        self.realized_daily_pnl = 0.0
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""

    def register_trade_closed(self, pnl: float):
        """
        Whenever a trade is closed, add its profit/loss to the daily accumulator.
        If cumulative daily loss hits the max limit (5%), trip the circuit breaker.
        """
        self.realized_daily_pnl += pnl
        max_allowed_loss = self.daily_start_balance * self.config.max_daily_loss
        
        # Check if loss exceeds our safety limit
        if self.realized_daily_pnl <= -max_allowed_loss:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = (
                f"Daily drawdown limit reached: lost ${abs(self.realized_daily_pnl):.2f} "
                f"(Max allowed: ${max_allowed_loss:.2f})"
            )

    def can_open_trade(self, symbol: str, open_position_count: int) -> Tuple[bool, str]:
        """
        Validates whether we are allowed to take a new trade.
        Returns (True, "Approved") or (False, "Reason for rejection").
        """
        # Rule 1: Has the circuit breaker been triggered today?
        if self.circuit_breaker_active:
            return False, f"CIRCUIT BREAKER: {self.circuit_breaker_reason}"
            
        # Rule 2: Are we already holding too many simultaneous trades?
        if open_position_count >= self.config.max_open_positions:
            return False, f"Max concurrent trades reached ({open_position_count}/{self.config.max_open_positions})"
            
        # Rule 3: Is this symbol currently cooling down?
        if symbol in self.last_trade_times:
            elapsed = (datetime.now(timezone.utc) - self.last_trade_times[symbol]).total_seconds()
            if elapsed < self.config.trade_cooldown_seconds:
                remaining = int(self.config.trade_cooldown_seconds - elapsed)
                return False, f"Cooldown on {symbol}: wait {remaining}s"
                
        return True, "Approved"

    def calculate_position_order(
        self, 
        symbol: str, 
        signal_action: str, 
        current_price: float, 
        df: pd.DataFrame,
        current_equity: float
    ) -> Optional[Dict]:
        """
        Calculates ATR-volatility position sizing, stop loss, and take profit.
        
        How the math works:
        Step 1: Determine risk capital = Account Equity * 1% ($100 on $10k equity).
        Step 2: Calculate Stop Loss distance using 14-period ATR:
                SL distance = 1.5 * ATR.
        Step 3: Calculate Take Profit distance using 1:1.8 Risk/Reward:
                TP distance = 1.8 * SL distance.
        Step 4: Compute Lot Size so that if SL is triggered, the loss equals exactly $100.
                Lot size = Risk Amount / (SL distance in pips * pip value per lot).
        Step 5: Clamp lot size between min (0.01) and max (10.0) lots.
        """
        if len(df) < 15:
            return None
            
        atr_series = calculate_atr(df['high'], df['low'], df['close'], period=14)
        atr = float(atr_series.iloc[-1])
        if atr <= 0:
            return None
            
        asset = self.assets.get(symbol, AssetConfig(symbol, 'forex', 0.0001, 1.5))
        
        # Stop loss distance: at least 10 pips, or 1.5x ATR
        sl_distance = max(atr * self.config.atr_multiplier_sl, asset.point_size * 10)
        tp_distance = sl_distance * self.config.risk_reward_ratio
        
        # Exactly 1% of current equity at risk
        risk_capital = current_equity * self.config.risk_per_trade
        
        # Calculate volume based on asset class
        if asset.asset_class == 'forex':
            sl_pips = sl_distance / asset.point_size
            pip_value_per_standard_lot = 10.0  # Approx $10 per pip on a standard lot
            raw_lots = risk_capital / (sl_pips * pip_value_per_standard_lot) if sl_pips > 0 else 0.01
        elif asset.asset_class == 'metals':
            # Gold: 1 lot = 100 oz ($1 move = $100)
            raw_lots = risk_capital / (sl_distance * 100.0) if sl_distance > 0 else 0.01
        else:
            raw_lots = risk_capital / (sl_distance * 10.0) if sl_distance > 0 else 0.01
            
        # Ensure lot size stays within valid broker limits
        lots = round(max(self.config.min_lot_size, min(self.config.max_lot_size, raw_lots)), 2)
        
        # Set entry, SL, and TP prices
        if signal_action == 'BUY':
            stop_loss = round(current_price - sl_distance, 5)
            take_profit = round(current_price + tp_distance, 5)
        elif signal_action == 'SELL':
            stop_loss = round(current_price + sl_distance, 5)
            take_profit = round(current_price - tp_distance, 5)
        else:
            return None
            
        return {
            'symbol': symbol,
            'action': signal_action,
            'entry_price': current_price,
            'lots': lots,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'sl_distance': round(sl_distance, 5),
            'risk_amount': round(risk_capital, 2),
            'risk_reward_ratio': self.config.risk_reward_ratio,
            'atr': round(atr, 5)
        }

    def record_trade_opened(self, symbol: str):
        """Saves current timestamp to enforce the cooldown rule on this symbol."""
        self.last_trade_times[symbol] = datetime.now(timezone.utc)
