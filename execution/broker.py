"""
Abstract broker interface and shared data structures.

Using an abstract base class decouples strategies and risk logic from the
execution layer. Swapping PaperBroker for MT5Broker doesn't touch a single
line of strategy or risk code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional


@dataclass
class Position:
    """An active open trade currently held in the portfolio."""
    id: str
    symbol: str
    action: str           # 'BUY' or 'SELL'
    lots: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    unrealized_pnl: float = 0.0
    open_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    contributing_strategies: List[str] = field(default_factory=list)


@dataclass
class TradeRecord:
    """A completed, closed trade with its realized P&L."""
    id: str
    symbol: str
    action: str
    lots: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percentage: float
    reason: str           # 'TP_HIT', 'SL_HIT', 'MANUAL_CLOSE', or 'BACKTEST_END'
    open_time: datetime
    close_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    contributing_strategies: List[str] = field(default_factory=list)


class BaseBroker(ABC):
    """All broker implementations must conform to this interface."""

    @abstractmethod
    def get_balance(self) -> float:
        """Realized cash balance."""
        pass

    @abstractmethod
    def get_equity(self) -> float:
        """Total equity = cash balance + floating unrealized P&L."""
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Position]:
        pass

    @abstractmethod
    def execute_order(self, order_spec: Dict, contributing_strategies: Optional[List[str]] = None) -> Optional[Position]:
        pass

    @abstractmethod
    def update_positions_with_market_tick(self, symbol: str, current_price: float) -> List[TradeRecord]:
        """Check incoming prices against SL/TP levels and close any that were hit."""
        pass

    @abstractmethod
    def get_closed_trades(self) -> List[TradeRecord]:
        pass
