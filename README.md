# AlgoTrader — Multi-Strategy Algorithmic Trading Engine

A modular, event-driven trading system written in Python with a real-time web dashboard. Runs a six-strategy ensemble with dynamic Bayesian weight rebalancing across eight financial instruments, with full backtest capability and a risk management layer that enforces ATR-based position sizing and a daily loss circuit breaker.

Zero external broker dependencies — works out of the box via the built-in paper trading simulator.

**Live Demo:** [Deploy on Vercel](#deployment)

---

## Features

- **6-Strategy Ensemble** — EMA crossover, adaptive RSI mean reversion, MACD momentum, Bollinger squeeze breakout, volume anomaly detection, and news sentiment scoring
- **Dynamic Bayesian Weights** — strategy weights shift automatically based on live win/loss records using Laplace-smoothed empirical rates
- **ATR Position Sizing** — risks a fixed 1% of equity per trade regardless of instrument volatility
- **5% Daily Circuit Breaker** — halts all trading if the daily loss limit is hit
- **Paper Broker** — simulates spread, slippage, and automated TP/SL execution without any live account
- **Real-time Dashboard** — live equity curve, open positions, trade history, strategy weights, and system logs
- **Historical Backtester** — bar-by-bar simulation across all 8 instruments with no lookahead bias
- **Pure Python indicators** — EMA, RSI, MACD, Bollinger Bands, ATR, ADX implemented with NumPy/Pandas directly (no TA-Lib)
- **MT5 Adapter** — optional live execution via MetaTrader 5 (Windows)

---

## Architecture

```
Market Data Feed (GBM Simulator)
          │
    Trading Engine
          │
  ┌───────┴────────┐
  │                │
Strategy        Risk Manager
Ensemble        ├── ATR Position Sizing
├── EMA Cross    ├── 1:1.8 Risk/Reward
├── RSI Revert   ├── Daily Loss Limit
├── MACD         └── Symbol Cooldown
├── BB Squeeze
├── Volume Surge
└── Sentiment
  │
  └──── Bayesian Weight Rebalancer
          │
     Execution Broker
     ├── PaperBroker (default)
     └── MT5Broker (optional)
          │
     Analytics + Dashboard
```

---

## Quick Start

**Requirements:** Python 3.10+

```bash
pip install numpy pandas
```

### Run the web dashboard (paper trading)
```bash
python main.py --mode demo
```
Open [http://localhost:8080](http://localhost:8080)

### Run a historical backtest
```bash
python main.py --mode backtest
```

### Run unit tests
```bash
python -m unittest discover -s tests -v
```

---

## Repository Structure

```
├── index.html              # Dashboard UI
├── main.py                 # CLI entry point
├── config.py               # Risk, asset, and strategy parameters
│
├── api/                    # Vercel serverless function handlers
│   ├── status.py           # Live tick + telemetry
│   ├── step.py             # Advance simulation by N cycles
│   ├── backtest.py         # Run historical backtest
│   ├── reset.py            # Reset simulation to starting balance
│   └── index.py            # API health check
│
├── core/
│   ├── engine.py           # Event-driven trading orchestrator
│   └── compat.py           # NumPy/Pandas with pure-Python fallback
│
├── strategies/
│   ├── ensemble.py         # 6-strategy ensemble with dynamic weights
│   ├── indicators.py       # EMA, RSI, MACD, BB, ATR, ADX
│   └── sentiment.py        # Financial keyword sentiment analyzer
│
├── risk/
│   └── manager.py          # ATR sizing and daily loss circuit breaker
│
├── execution/
│   ├── broker.py           # Abstract BaseBroker interface
│   ├── paper_broker.py     # Spread/slippage/SL-TP simulator
│   └── mt5_broker.py       # MetaTrader 5 live adapter (optional)
│
├── data/
│   └── feed.py             # GBM OHLCV candle generator
│
├── analytics/
│   └── metrics.py          # Sharpe, Sortino, drawdown, win rate
│
├── dashboard/
│   └── server.py           # Local HTTP server + Vercel WSGI adapter
│
└── tests/
    └── test_engine.py      # Unit test suite
```

---

## Instruments

| Symbol | Class | Description |
|--------|-------|-------------|
| EURUSD | Forex | Euro / US Dollar |
| GBPUSD | Forex | British Pound / US Dollar |
| USDJPY | Forex | US Dollar / Japanese Yen |
| USDCAD | Forex | US Dollar / Canadian Dollar |
| XAUUSD | Metals | Gold spot |
| XAGUSD | Metals | Silver spot |
| USOIL  | Commodities | WTI Crude Oil |
| NAS100 | Indices | Nasdaq 100 |

---

## Strategy Math

**EMA Crossover** — Fast (9) crosses above Slow (21) with price above slow EMA → BUY signal.

**Adaptive RSI** — Wilder-smoothed RSI with volatility-adjusted thresholds:
```
lower = max(22, 30 - ATR/Price × 20)
upper = min(78, 70 + ATR/Price × 20)
```

**Bollinger Squeeze** — bandwidth = (upper - lower) / middle. When bandwidth < 0.12 and price breaks the band → breakout signal.

**ATR Position Sizing:**
```
sl_distance = ATR(14) × 1.5
tp_distance = sl_distance × 1.8
lots = (equity × 1%) / (sl_pips × pip_value_per_lot)
```

**Bayesian Weight Update** (Laplace smoothed):
```
weight_i = (wins + 1) / (wins + losses + 2)
```

---

## Deployment

### Vercel (recommended)
1. Fork this repo
2. Connect to [vercel.com](https://vercel.com)
3. Deploy with default settings — the `vercel.json` config handles routing

### Local Docker (optional)
```bash
docker build -t algotrader .
docker run -p 8080:8080 algotrader
```

---

## Configuration

All parameters are in [`config.py`](config.py):

| Parameter | Default | Description |
|---|---|---|
| `risk_per_trade` | 1% | Dollar risk per trade |
| `max_daily_loss` | 5% | Daily loss circuit breaker |
| `max_open_positions` | 5 | Max simultaneous positions |
| `atr_multiplier_sl` | 1.5 | Stop-loss in ATR multiples |
| `risk_reward_ratio` | 1.8 | TP:SL ratio |
| `trade_cooldown_seconds` | 60 | Per-symbol cooldown |

---

## License

MIT — free to use for learning, research, and portfolio projects.
