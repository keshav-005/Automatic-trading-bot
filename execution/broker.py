"""
Abstract Broker Interface
Author: Computer Science Student Project

By using an abstract BaseBroker class, we decouple the trading algorithms from the
execution environment. Our bot can run against:
1. PaperBroker (simulated execution for offline backtesting and recruiter evaluation)
2. MT5Broker (live execution on MetaTrader 5 desktop client)
without changing a single line of strategy or risk code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional

@dataclass
class Position:
    """Represents an active open trade currently held in the portfolio."""
    id: str
    symbol: str
    action: str          # 'BUY' or 'SELL'
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
    """Represents a completed, closed trade with realized profit or loss."""
    id: str
    symbol: str
    action: str
    lots: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percentage: float
    reason: str          # 'TP_HIT', 'SL_HIT', 'MANUAL_CLOSE', or 'BACKTEST_END'
    open_time: datetime
    close_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    contributing_strategies: List[str] = field(default_factory=list)

class BaseBroker(ABC):
    """Abstract interface that all broker implementations must conform to."""
    
    @abstractmethod
    def get_balance(self) -> float:
        """Returns cash balance (realized equity)."""
        pass

    @abstractmethod
    def get_equity(self) -> float:
        """Returns total equity = Balance + Floating unrealized PnL."""
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Position]:
        """Returns all open positions."""
        pass

    @abstractmethod
    def execute_order(self, order_spec: Dict, contributing_strategies: Optional[List[str]] = None) -> Optional[Position]:
        """Submits and fills a market order."""
        pass

    @abstractmethod
    def update_positions_with_market_tick(self, symbol: str, current_price: float) -> List[TradeRecord]:
        """Checks incoming market prices against TP and SL levels."""
        pass

    @abstractmethod
    def get_closed_trades(self) -> List[TradeRecord]:
        """Returns complete history of completed trades."""
        pass
