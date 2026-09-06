"""
Risk management — position sizing, trade filtering, and daily loss circuit breaker.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict
from core.compat import pd

from config import RiskConfig, AssetConfig
from strategies.indicators import calculate_atr


class RiskManager:
    """
    Enforces portfolio-level risk controls on every attempted trade.

    Two main responsibilities:
    1. ATR-based position sizing — risk the same dollar amount regardless of
       whether the instrument is volatile (Gold) or quiet (EURUSD).
    2. Daily loss circuit breaker — halt trading for the session once cumulative
       losses exceed the configured maximum (default: 5% of account equity).
    """

    def __init__(self, config: RiskConfig, assets: Dict[str, AssetConfig]):
        self.config = config
        self.assets = assets

        self.daily_start_balance = config.account_balance
        self.realized_daily_pnl = 0.0
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.last_trade_times: Dict[str, datetime] = {}

    def reset_daily_metrics(self, current_balance: float):
        """Reset the daily accumulator at the start of a new trading session."""
        self.daily_start_balance = current_balance
        self.realized_daily_pnl = 0.0
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""

    def register_trade_closed(self, pnl: float):
        """
        Accumulate realized P&L and trip the circuit breaker if the daily loss
        limit is reached.
        """
        self.realized_daily_pnl += pnl
        max_allowed_loss = self.daily_start_balance * self.config.max_daily_loss

        if self.realized_daily_pnl <= -max_allowed_loss:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = (
                f"Daily drawdown limit reached: lost ${abs(self.realized_daily_pnl):.2f} "
                f"(limit: ${max_allowed_loss:.2f})"
            )

    def can_open_trade(self, symbol: str, open_position_count: int) -> Tuple[bool, str]:
        """
        Returns (True, 'Approved') or (False, rejection_reason).

        Checks three rules in order:
        1. Circuit breaker is not active.
        2. Maximum concurrent positions not exceeded.
        3. Symbol cooldown period has elapsed.
        """
        if self.circuit_breaker_active:
            return False, f"CIRCUIT BREAKER: {self.circuit_breaker_reason}"

        if open_position_count >= self.config.max_open_positions:
            return False, f"Max positions reached ({open_position_count}/{self.config.max_open_positions})"

        if symbol in self.last_trade_times:
            elapsed = (datetime.now(timezone.utc) - self.last_trade_times[symbol]).total_seconds()
            if elapsed < self.config.trade_cooldown_seconds:
                remaining = int(self.config.trade_cooldown_seconds - elapsed)
                return False, f"Cooldown on {symbol}: {remaining}s remaining"

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
        Compute lot size, SL, and TP for a new order.

        Sizing formula:
            risk_capital = equity × risk_per_trade (e.g. 1%)
            sl_distance  = ATR(14) × atr_multiplier (default 1.5)
            tp_distance  = sl_distance × risk_reward_ratio (default 1.8)
            lots         = risk_capital / (sl_pips × pip_value_per_lot)

        Returns None if the data window is too short or ATR is zero.
        """
        if len(df) < 15:
            return None

        atr_series = calculate_atr(df['high'], df['low'], df['close'], period=14)
        atr = float(atr_series.iloc[-1])
        if atr <= 0:
            return None

        asset = self.assets.get(symbol, AssetConfig(symbol, 'forex', 0.0001, 1.5))

        sl_distance = max(atr * self.config.atr_multiplier_sl, asset.point_size * 10)
        tp_distance = sl_distance * self.config.risk_reward_ratio
        risk_capital = current_equity * self.config.risk_per_trade

        if asset.asset_class == 'forex':
            sl_pips = sl_distance / asset.point_size
            pip_value_per_lot = 10.0
            raw_lots = risk_capital / (sl_pips * pip_value_per_lot) if sl_pips > 0 else 0.01
        elif asset.asset_class == 'metals':
            raw_lots = risk_capital / (sl_distance * 100.0) if sl_distance > 0 else 0.01
        else:
            raw_lots = risk_capital / (sl_distance * 10.0) if sl_distance > 0 else 0.01

        lots = round(max(self.config.min_lot_size, min(self.config.max_lot_size, raw_lots)), 2)

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
        """Record the current time for this symbol to enforce the cooldown rule."""
        self.last_trade_times[symbol] = datetime.now(timezone.utc)
