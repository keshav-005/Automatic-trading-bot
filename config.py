"""
Trading bot configuration.

All tunable parameters live here — risk limits, asset specs, strategy weights.
Keeping config separate from logic means you can tweak behaviour without touching
the actual trading or indicator code.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class AssetConfig:
    """
    Market properties for a single instrument.

    point_size       — minimum price movement (pip size).
    typical_spread_pips — average broker spread baked into the bid/ask.
    """
    symbol: str
    asset_class: str
    point_size: float
    typical_spread_pips: float
    base_currency: str = "USD"


@dataclass
class RiskConfig:
    """
    Capital protection parameters.

    The system risks a fixed dollar amount per trade (1% of equity by default)
    and has a hard daily loss limit that halts trading for the rest of the day.
    """
    # Starting virtual balance for paper trading and backtesting
    account_balance: float = 10000.0

    # Fraction of equity risked on each trade
    risk_per_trade: float = 0.01

    # Daily loss circuit breaker — stops trading when this fraction of equity is lost in one day
    max_daily_loss: float = 0.05

    # Caps simultaneous open positions across all symbols
    max_open_positions: int = 5

    # Minimum seconds between orders on the same symbol
    trade_cooldown_seconds: int = 60

    # Stop-loss distance expressed as a multiple of ATR
    atr_multiplier_sl: float = 1.5

    # Take-profit is this multiple of the stop-loss distance (risk:reward ratio)
    risk_reward_ratio: float = 1.8

    max_lot_size: float = 10.0
    min_lot_size: float = 0.01


@dataclass
class StrategyWeightsConfig:
    """
    Initial voting weights for the six strategy subsystems. Must sum to 1.0.

    These shift over time as the ensemble records each strategy's live win/loss record.
    """
    weights: Dict[str, float] = field(default_factory=lambda: {
        'ema_cross':         0.25,
        'rsi_reversion':     0.20,
        'macd_momentum':     0.18,
        'bollinger_squeeze': 0.15,
        'volume_anomaly':    0.12,
        'market_sentiment':  0.10,
    })

    # Only trade when ADX is above this — filters out flat, ranging markets
    adx_trend_threshold: float = 22.0

    # Minimum weighted ensemble score required to trigger a trade
    signal_confidence_threshold: float = 0.40


@dataclass
class TradingConfig:
    """Top-level config container passed to the TradingEngine."""

    # 'paper' runs the simulated broker; 'mt5' connects to a live MetaTrader 5 account
    execution_mode: str = os.getenv("EXECUTION_MODE", "paper")

    # MT5 credentials — only used when execution_mode='mt5'
    mt5_account: int = int(os.getenv("MT5_ACCOUNT", "0"))
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "MetaQuotes-Demo")

    dashboard_host: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    dashboard_port: int = int(os.getenv("DASHBOARD_PORT", "8080"))

    risk: RiskConfig = field(default_factory=RiskConfig)
    strategies: StrategyWeightsConfig = field(default_factory=StrategyWeightsConfig)

    # Instruments tracked by the engine — Forex, metals, commodities, and indices
    assets: Dict[str, AssetConfig] = field(default_factory=lambda: {
        "EURUSD": AssetConfig("EURUSD", "forex",       0.0001, 1.2),
        "GBPUSD": AssetConfig("GBPUSD", "forex",       0.0001, 1.5),
        "USDJPY": AssetConfig("USDJPY", "forex",       0.01,   1.4),
        "USDCAD": AssetConfig("USDCAD", "forex",       0.0001, 1.8),
        "XAUUSD": AssetConfig("XAUUSD", "metals",      0.01,   2.5),
        "XAGUSD": AssetConfig("XAGUSD", "metals",      0.001,  3.0),
        "USOIL":  AssetConfig("USOIL",  "commodities", 0.01,   3.5),
        "NAS100": AssetConfig("NAS100", "indices",     0.1,    2.0),
    })


default_config = TradingConfig()
