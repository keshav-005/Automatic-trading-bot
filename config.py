"""
Trading Bot Configuration File
Author: Computer Science Student Project

This file holds all the tunable parameters for our trading bot.
Keeping configuration separate from strategy logic is good software engineering practice:
we can tweak risk limits, symbols, or timeframes without touching the core algorithms.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class AssetConfig:
    """
    Holds market properties for an individual financial instrument.
    
    symbol: ticker name (e.g., 'EURUSD')
    asset_class: 'forex', 'metals', 'commodities', or 'indices'
    point_size: the minimum price change (0.0001 for most forex, 0.01 for JPY/Gold)
    typical_spread_pips: average broker fee baked into the spread
    """
    symbol: str
    asset_class: str
    point_size: float
    typical_spread_pips: float
    base_currency: str = "USD"

@dataclass
class RiskConfig:
    """
    Institutional risk controls to protect capital.
    
    Key interview talking point:
    "We don't use arbitrary lot sizes. We use ATR-based position sizing,
    risking strictly 1% of total account balance per trade, and we have
    a hard daily stop loss circuit breaker at 5% to prevent blowups."
    """
    # Starting virtual cash balance for backtesting and paper trading
    account_balance: float = 10000.0

    # Risk 1% of total equity on any single trade ($100 on a $10,000 account)
    risk_per_trade: float = 0.01

    # Daily circuit breaker: if we lose 5% ($500) in a single day, stop trading today
    max_daily_loss: float = 0.05

    # Don't open more than 5 positions simultaneously to avoid portfolio overexposure
    max_open_positions: int = 5

    # Don't trade the same symbol twice within 60 seconds (prevents order spam)
    trade_cooldown_seconds: int = 60

    # Stop Loss distance = 1.5 * ATR (volatility adjusted)
    atr_multiplier_sl: float = 1.5

    # Take Profit = 1.8 * Stop Loss distance (positive risk-to-reward ratio 1:1.8)
    risk_reward_ratio: float = 1.8

    # Safety limits on lot sizes (0.01 micro-lot to 10 standard lots)
    max_lot_size: float = 10.0
    min_lot_size: float = 0.01

@dataclass
class StrategyWeightsConfig:
    """
    Initial weight distribution for our 6 strategy systems.
    Total weights must sum to 1.0 (100%).
    
    As the bot trades, the ensemble dynamically updates these weights based on
    which strategies are winning and losing.
    """
    weights: Dict[str, float] = field(default_factory=lambda: {
        'ema_cross': 0.25,        # 25% weight to trend-following EMA
        'rsi_reversion': 0.20,    # 20% weight to mean-reversion RSI
        'macd_momentum': 0.18,    # 18% weight to MACD momentum
        'bollinger_squeeze': 0.15,# 15% weight to volatility breakout
        'volume_anomaly': 0.12,   # 12% weight to unusual volume surges
        'market_sentiment': 0.10  # 10% weight to news sentiment scoring
    })

    # ADX threshold: only trade if ADX is above 22 (means market is actually trending)
    adx_trend_threshold: float = 22.0

    # The weighted ensemble score must be > 0.40 (40%) to trigger a trade
    signal_confidence_threshold: float = 0.40

@dataclass
class TradingConfig:
    """Main global configuration container."""
    
    # Mode can be 'paper' (simulated, zero setup required) or 'mt5' (live broker)
    execution_mode: str = os.getenv("EXECUTION_MODE", "paper")
    
    # MT5 credentials (only used if execution_mode is set to 'mt5')
    mt5_account: int = int(os.getenv("MT5_ACCOUNT", "0"))
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "MetaQuotes-Demo")
    
    # Web dashboard host and port
    dashboard_host: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    dashboard_port: int = int(os.getenv("DASHBOARD_PORT", "8080"))
    
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategies: StrategyWeightsConfig = field(default_factory=StrategyWeightsConfig)
    
    # The 8 instruments we track and simulate across Forex, Metals, Commodities, and Indices
    assets: Dict[str, AssetConfig] = field(default_factory=lambda: {
        "EURUSD": AssetConfig(symbol="EURUSD", asset_class="forex", point_size=0.0001, typical_spread_pips=1.2),
        "GBPUSD": AssetConfig(symbol="GBPUSD", asset_class="forex", point_size=0.0001, typical_spread_pips=1.5),
        "USDJPY": AssetConfig(symbol="USDJPY", asset_class="forex", point_size=0.01,   typical_spread_pips=1.4),
        "USDCAD": AssetConfig(symbol="USDCAD", asset_class="forex", point_size=0.0001, typical_spread_pips=1.8),
        "XAUUSD": AssetConfig(symbol="XAUUSD", asset_class="metals", point_size=0.01,   typical_spread_pips=2.5),
        "XAGUSD": AssetConfig(symbol="XAGUSD", asset_class="metals", point_size=0.001,  typical_spread_pips=3.0),
        "USOIL":  AssetConfig(symbol="USOIL",  asset_class="commodities", point_size=0.01, typical_spread_pips=3.5),
        "NAS100": AssetConfig(symbol="NAS100", asset_class="indices", point_size=0.1,  typical_spread_pips=2.0)
    })

# Default shared configuration instance
default_config = TradingConfig()
