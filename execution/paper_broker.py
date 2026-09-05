"""
Paper Trading Simulated Broker
Author: Computer Science Student Project

Why PaperBroker is important:
In real quantitative finance software engineering, you never test new code directly on a live account.
This paper broker accurately simulates realistic market mechanics:
1. Bid/Ask Spreads: buyers pay the Ask (higher price), sellers get the Bid (lower price).
2. Slippage: orders don't always fill at the exact mid price; small network delays cause slight price differences.
3. Automated TP/SL Execution: when incoming ticks touch the Stop Loss or Take Profit levels, the trade closes automatically.
"""

import uuid
import random
from datetime import datetime, timezone
from typing import List, Dict, Optional

from execution.broker import BaseBroker, Position, TradeRecord
from config import AssetConfig

class PaperBroker(BaseBroker):
    def __init__(self, initial_balance: float = 10000.0, assets: Optional[Dict[str, AssetConfig]] = None):
        self.initial_balance = initial_balance
        self.cash_balance = initial_balance
        self.assets = assets or {}
        
        # In-memory storage for positions and trades
        self.open_positions: Dict[str, Position] = {}
        self.closed_trades: List[TradeRecord] = []
        self.equity_history: List[Dict] = []
        
        # Save starting equity point ($10,000)
        self.record_equity_snapshot()

    def record_equity_snapshot(self):
        """Records an equity snapshot timestamp for charting."""
        self.equity_history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'equity': round(self.get_equity(), 2),
            'balance': round(self.cash_balance, 2),
            'open_positions': len(self.open_positions)
        })

    def get_contract_multiplier(self, symbol: str) -> float:
        """
        Returns contract size multiplier:
        - 1 standard Forex lot = 100,000 units
        - 1 Gold lot (XAUUSD) = 100 oz
        - 1 Silver lot (XAGUSD) = 5,000 oz
        """
        asset = self.assets.get(symbol)
        if asset:
            if asset.asset_class == 'forex':
                return 100000.0
            elif asset.asset_class == 'metals' and 'XAU' in symbol:
                return 100.0
            elif asset.asset_class == 'metals' and 'XAG' in symbol:
                return 5000.0
        return 100.0

    def _apply_spread_and_slippage(self, symbol: str, action: str, raw_price: float) -> float:
        """
        Applies realistic market friction:
        - Spread: Half-spread added to buy price (Ask) or subtracted from sell price (Bid).
        - Slippage: A small micro-fluctuation simulating order latency.
        """
        asset = self.assets.get(symbol)
        point = asset.point_size if asset else 0.0001
        spread_pips = asset.typical_spread_pips if asset else 1.5
        
        half_spread = (spread_pips * point) / 2.0
        slippage = random.uniform(-0.1, 0.3) * point  # Slight execution slippage
        
        if action == 'BUY':
            return raw_price + half_spread + slippage
        else:
            return raw_price - half_spread - slippage

    def get_balance(self) -> float:
        """Returns cash balance."""
        return self.cash_balance

    def get_equity(self) -> float:
        """Total equity = cash balance + unrealized profit/loss of all open positions."""
        unrealized = sum(pos.unrealized_pnl for pos in self.open_positions.values())
        return self.cash_balance + unrealized

    def get_open_positions(self) -> List[Position]:
        """Returns currently active open positions."""
        return list(self.open_positions.values())

    def get_closed_trades(self) -> List[TradeRecord]:
        """Returns full list of completed trades."""
        return self.closed_trades

    def execute_order(self, order_spec: Dict, contributing_strategies: Optional[List[str]] = None) -> Optional[Position]:
        """Fills a simulated market order."""
        symbol = order_spec['symbol']
        action = order_spec['action']
        raw_price = order_spec['entry_price']
        lots = order_spec['lots']
        
        # Calculate realistic fill price
        fill_price = round(self._apply_spread_and_slippage(symbol, action, raw_price), 5)
        
        # Maintain distance to Stop Loss and Take Profit from actual fill price
        sl_dist = order_spec.get('sl_distance', 0.002)
        rr = order_spec.get('risk_reward_ratio', 1.8)
        
        if action == 'BUY':
            stop_loss = round(fill_price - sl_dist, 5)
            take_profit = round(fill_price + (sl_dist * rr), 5)
        else:
            stop_loss = round(fill_price + sl_dist, 5)
            take_profit = round(fill_price - (sl_dist * rr), 5)
            
        pos_id = f"pos_{uuid.uuid4().hex[:8]}"
        position = Position(
            id=pos_id,
            symbol=symbol,
            action=action,
            lots=lots,
            entry_price=fill_price,
            current_price=fill_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            unrealized_pnl=0.0,
            open_time=datetime.now(timezone.utc),
            contributing_strategies=contributing_strategies or []
        )
        
        self.open_positions[pos_id] = position
        self.record_equity_snapshot()
        return position

    def update_positions_with_market_tick(self, symbol: str, current_price: float) -> List[TradeRecord]:
        """
        Called on every price tick:
        1. Updates floating unrealized PnL.
        2. Checks if current price touched the Take Profit or Stop Loss level.
        3. If hit, automatically closes the trade.
        """
        closed_trades: List[TradeRecord] = []
        multiplier = self.get_contract_multiplier(symbol)
        
        for pos_id, pos in list(self.open_positions.items()):
            if pos.symbol != symbol:
                continue
                
            pos.current_price = current_price
            
            # For a BUY position: price going up is profit, down is loss
            if pos.action == 'BUY':
                diff = current_price - pos.entry_price
                pos.unrealized_pnl = round(diff * multiplier * pos.lots, 2)
                
                if current_price >= pos.take_profit:
                    trade = self._close_position_internal(pos_id, pos.take_profit, 'TP_HIT')
                    closed_trades.append(trade)
                elif current_price <= pos.stop_loss:
                    trade = self._close_position_internal(pos_id, pos.stop_loss, 'SL_HIT')
                    closed_trades.append(trade)
                    
            # For a SELL position: price going down is profit, up is loss
            elif pos.action == 'SELL':
                diff = pos.entry_price - current_price
                pos.unrealized_pnl = round(diff * multiplier * pos.lots, 2)
                
                if current_price <= pos.take_profit:
                    trade = self._close_position_internal(pos_id, pos.take_profit, 'TP_HIT')
                    closed_trades.append(trade)
                elif current_price >= pos.stop_loss:
                    trade = self._close_position_internal(pos_id, pos.stop_loss, 'SL_HIT')
                    closed_trades.append(trade)
                    
        return closed_trades

    def _close_position_internal(self, pos_id: str, exit_price: float, reason: str) -> TradeRecord:
        """Removes an open position, realizes the PnL into cash balance, and creates a TradeRecord."""
        pos = self.open_positions.pop(pos_id)
        multiplier = self.get_contract_multiplier(pos.symbol)
        
        if pos.action == 'BUY':
            pnl = (exit_price - pos.entry_price) * multiplier * pos.lots
        else:
            pnl = (pos.entry_price - exit_price) * multiplier * pos.lots
            
        pnl = round(pnl, 2)
        pnl_pct = round((pnl / self.cash_balance) * 100.0, 3)
        
        # Realize cash
        self.cash_balance += pnl
        
        record = TradeRecord(
            id=pos.id,
            symbol=pos.symbol,
            action=pos.action,
            lots=pos.lots,
            entry_price=pos.entry_price,
            exit_price=round(exit_price, 5),
            pnl=pnl,
            pnl_percentage=pnl_pct,
            reason=reason,
            open_time=pos.open_time,
            close_time=datetime.now(timezone.utc),
            contributing_strategies=pos.contributing_strategies
        )
        self.closed_trades.append(record)
        self.record_equity_snapshot()
        return record

    def close_all_positions(self, current_prices: Dict[str, float], reason: str = "MANUAL_CLOSE"):
        """Emergency close all active trades (e.g. at end of backtest)."""
        for pos_id, pos in list(self.open_positions.items()):
            price = current_prices.get(pos.symbol, pos.current_price)
            self._close_position_internal(pos_id, price, reason)
