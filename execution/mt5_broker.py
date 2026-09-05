"""
MetaTrader 5 Broker Adapter
Author: Computer Science Student Project

This module connects our trading bot to a live or demo MetaTrader 5 terminal.
Key design highlight:
If the user does not have MetaTrader 5 installed on their computer, or is running on Mac/Linux,
this class catches the ImportError or connection failure gracefully and routes all calls
to our internal PaperBroker. The program will NEVER crash due to missing MT5 software!
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
from execution.broker import BaseBroker, Position, TradeRecord
from execution.paper_broker import PaperBroker

class MT5Broker(BaseBroker):
    def __init__(self, account: int = 0, password: str = "", server: str = "MetaQuotes-Demo"):
        self.account = account
        self.password = password
        self.server = server
        self.is_connected = False
        
        # Fallback simulator if MT5 is not running
        self.paper_fallback = PaperBroker(initial_balance=10000.0)
        
        self._try_initialize_mt5()

    def _try_initialize_mt5(self):
        """Attempts to connect to MT5, but gracefully falls back if unavailable."""
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            
            # If credentials are provided, login; otherwise attach to active terminal
            if self.account and self.password:
                connected = self.mt5.initialize(
                    login=self.account, 
                    password=self.password, 
                    server=self.server
                )
            else:
                connected = self.mt5.initialize()
                
            if connected:
                self.is_connected = True
                print(f"[MT5Bridge] Connected successfully to {self.server} (Account: {self.account})")
            else:
                print(f"[MT5Bridge] MT5 terminal not active. Falling back to local PaperBroker simulation.")
        except (ImportError, Exception) as e:
            # Common on Mac, Linux, or systems without MT5 installed
            print(f"[MT5Bridge] MetaTrader 5 library unavailable on this environment. Using PaperBroker.")
            self.is_connected = False

    def get_balance(self) -> float:
        if self.is_connected:
            info = self.mt5.account_info()
            if info:
                return float(info.balance)
        return self.paper_fallback.get_balance()

    def get_equity(self) -> float:
        if self.is_connected:
            info = self.mt5.account_info()
            if info:
                return float(info.equity)
        return self.paper_fallback.get_equity()

    def get_open_positions(self) -> List[Position]:
        if self.is_connected:
            mt5_positions = self.mt5.positions_get()
            if mt5_positions is not None:
                results = []
                for p in mt5_positions:
                    results.append(Position(
                        id=str(p.ticket),
                        symbol=p.symbol,
                        action='BUY' if p.type == 0 else 'SELL',
                        lots=p.volume,
                        entry_price=p.price_open,
                        current_price=p.price_current,
                        stop_loss=p.sl,
                        take_profit=p.tp,
                        unrealized_pnl=p.profit
                    ))
                return results
        return self.paper_fallback.get_open_positions()

    def execute_order(self, order_spec: Dict, contributing_strategies: Optional[List[str]] = None) -> Optional[Position]:
        if self.is_connected:
            symbol = order_spec['symbol']
            action = order_spec['action']
            lots = order_spec['lots']
            sl = order_spec['stop_loss']
            tp = order_spec['take_profit']
            
            tick = self.mt5.symbol_info_tick(symbol)
            price = tick.ask if action == 'BUY' else tick.bid
            order_type = self.mt5.ORDER_TYPE_BUY if action == 'BUY' else self.mt5.ORDER_TYPE_SELL
            
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lots,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 10,
                "magic": 10101,
                "comment": "Trading Bot",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
            result = self.mt5.order_send(request)
            if result.retcode == self.mt5.TRADE_RETCODE_DONE:
                return Position(
                    id=str(result.order),
                    symbol=symbol,
                    action=action,
                    lots=lots,
                    entry_price=price,
                    current_price=price,
                    stop_loss=sl,
                    take_profit=tp,
                    contributing_strategies=contributing_strategies or []
                )
            else:
                print(f"[MT5Bridge] Order failed: {result.comment}")
                return None
                
        return self.paper_fallback.execute_order(order_spec, contributing_strategies)

    def update_positions_with_market_tick(self, symbol: str, current_price: float) -> List[TradeRecord]:
        return self.paper_fallback.update_positions_with_market_tick(symbol, current_price)

    def get_closed_trades(self) -> List[TradeRecord]:
        return self.paper_fallback.get_closed_trades()
