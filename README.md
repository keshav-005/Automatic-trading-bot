# Algorithmic Trading Bot & Backtesting Framework

A modular, event-driven trading and backtesting engine written in Python. Built as a Computer Science undergraduate capstone project to explore quantitative finance, risk management, and decoupled systems architecture.

---

## 📌 Project Overview

Most trading bot tutorials online are monolithic scripts hardcoded to a specific broker (like MetaTrader 5). If an evaluator or recruiter tries to run them, the code immediately crashes because they don't have the broker terminal installed or configured.

To solve this, I designed this project using a **decoupled object-oriented architecture**:
- **Simulated Paper Broker by Default:** Models bid/ask spreads, order slippage, and automated Stop-Loss / Take-Profit order handling. Anyone can clone and test the project on **Windows, Mac, or Linux** with zero external dependencies.
- **Pure NumPy/Pandas Indicators:** All indicator formulas (EMA, RSI, MACD, Bollinger Bands, ATR, ADX) are written directly from scratch in vectorized Python, avoiding fragile unmaintained third-party libraries.
- **6-Strategy Ensemble with Dynamic Weights:** Combines trend-following, mean-reversion, and volume anomaly strategies. Strategy weights dynamically adjust using Laplace-smoothed empirical win rates.
- **ATR-Based Risk Management:** Enforces a strict 1% dollar risk per trade and an automated 5% daily loss circuit breaker to prevent portfolio blowup.
- **Interactive Web Dashboard:** A clean, developer-focused dashboard built with standard library HTTP server and HTML5 Canvas (zero node.js or external CDN setup required).

---

## 🏛️ System Architecture

```
                       [ Market Data Feed ]
                 (Brownian Motion / OHLCV Generator)
                                 │
                                 ▼
                     [ Trading Engine Core ]
                      (Event-Driven Cycle)
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   [ Strategy Ensemble ]                    [ Risk Management ]
   ├── EMA 9/21 Cross                       ├── ATR Volatility Sizing (1% Risk)
   ├── Adaptive RSI Reversion               ├── 1:1.8 Risk/Reward Model
   ├── MACD + Volume Filter                 ├── Daily Loss Circuit Breaker (5%)
   ├── Bollinger Squeeze Breakout           └── Symbol Cooldown Timer
   ├── Volume Surge Detection                         │
   └── News Sentiment Scoring                         │
            │                                         │
            ▼                                         │
   [ Dynamic Bayesian Weighting ]                     │
   (Rewards Winning Strategies)                       │
            │                                         │
            └────────────────────┬────────────────────┘
                                 ▼
                     [ Execution Broker ]
                     ├── PaperBroker (Default)
                     └── MT5Broker (Optional live adapter)
                                 │
                                 ▼
                    [ Portfolio & Metrics ]
                    ├── Sharpe & Sortino Ratio
                    ├── Max Drawdown %
                    └── Real-time Web Dashboard
```

---

## 📐 Strategies & Mathematical Formulas

### 1. Exponential Moving Average (EMA 9/21)
Weights recent prices more heavily than older prices to reduce lag:
$$\text{EMA}_t = P_t \times \alpha + \text{EMA}_{t-1} \times (1 - \alpha), \quad \alpha = \frac{2}{\text{span} + 1}$$
*Signal: Fast EMA (9) crossing above Slow EMA (21) indicates bullish momentum.*

### 2. Adaptive RSI Mean Reversion
Uses Wilder's smoothing to calculate Relative Strength. The overbought/oversold bands dynamically adapt based on prevailing market volatility (ATR / Price ratio):
$$\text{Lower Threshold} = \max\left(22, 30 - \frac{\text{ATR}}{\text{Price}} \times 20\right)$$
*Signal: When RSI drops below the lower threshold, price is statistically oversold and due for a bounce.*

### 3. Bollinger Band Squeeze Breakout
Measures the bandwidth between the 20-period upper and lower standard deviation bands:
$$\text{Bandwidth} = \frac{\text{Upper Band} - \text{Lower Band}}{\text{Middle SMA}}$$
*Signal: When bandwidth drops below 0.12 (quiet consolidation), a breakout above the upper band signals an explosive move upward.*

### 4. Dynamic Strategy Weight Rebalancing
Instead of guessing static weights, the bot tracks each strategy's win/loss record and adjusts weights using Laplace smoothing:
$$\text{Weight}_i = \frac{\text{Wins}_i + 1}{\text{Wins}_i + \text{Losses}_i + 2}$$
Winning strategies automatically receive more voting authority on future trade decisions.

### 5. ATR Volatility Position Sizing
Ensures the bot risks the exact same dollar amount ($100 on a $10,000 account) regardless of whether trading a quiet currency or volatile Gold:
$$\text{Stop Loss Distance} = 1.5 \times \text{ATR}_{14}$$
$$\text{Lot Size} = \frac{\text{Account Equity} \times 1\%}{\text{SL Distance in Pips} \times \text{Pip Value}}$$

---

## 🚀 How to Run

### Requirements
- Python 3.10 or higher
- `pip install numpy pandas`

### 1. Run Historical Backtest
Runs a full backtest across 8 instruments (EURUSD, GBPUSD, USDJPY, USDCAD, XAUUSD, XAGUSD, USOIL, NAS100) and prints performance metrics:
```bash
python main.py --mode backtest
```

### 2. Run Live Paper Trading & Dashboard
Launches real-time simulation and opens the web dashboard:
```bash
python main.py --mode demo
```
Open **`http://localhost:8080`** in your browser to inspect live equity curves, active open trades, and dynamic strategy weights.

### 3. Run Automated Unit Tests
Verifies indicator math, risk management circuit breakers, and broker order execution:
```bash
python -m unittest discover -s tests -v
```

---

## 📁 Repository Structure

```
├── config.py                 # Tunable risk, asset, and strategy parameters
├── main.py                   # Main CLI entry point
├── autobot.py                # 1-line script runner
├── launch_dashboard.py       # Standalone dashboard launcher
│
├── core/
│   └── engine.py             # Event-driven trading orchestrator
│
├── strategies/
│   ├── indicators.py         # Pure NumPy/Pandas math (EMA, RSI, MACD, BB, ATR, ADX)
│   ├── ensemble.py           # 6-strategy ensemble with dynamic performance weights
│   └── sentiment.py          # Financial lexicon sentiment analysis
│
├── risk/
│   └── manager.py            # ATR position sizing and 5% daily loss circuit breaker
│
├── execution/
│   ├── broker.py             # Abstract BaseBroker interface and data structures
│   ├── paper_broker.py       # High-fidelity simulator (spread, slippage, SL/TP)
│   └── mt5_broker.py         # Optional MetaTrader 5 live adapter
│
├── data/
│   └── feed.py               # Geometric Brownian Motion candle generator
│
├── analytics/
│   └── metrics.py            # Quantitative metrics (Sharpe, Sortino, Drawdown)
│
├── dashboard/
│   ├── server.py             # Multithreaded standard library HTTP server
│   └── index.html            # Clean developer dark-mode dashboard
│
└── tests/
    └── test_engine.py        # Automated unit test suite
```

---

## 💼 Resume Bullet Points (Ready to Copy)

### For Software Engineering (Backend / Systems):
- *Designed an event-driven algorithmic trading and backtesting engine in Python using decoupled OOP principles (Engine, Broker, RiskManager, Strategy Ensemble).*
- *Engineered a standalone paper trading simulator modeling bid/ask spreads, slippage, and automated order execution, allowing 100% offline evaluation across Windows, Mac, and Linux.*
- *Built a lightweight, multithreaded HTTP telemetry dashboard using Python's standard library and HTML5 Canvas to stream real-time portfolio metrics and strategy allocations.*
- *Wrote comprehensive automated unit tests (`unittest`) covering technical indicator calculations, risk circuit breakers, and order fill lifecycles.*

### For Quantitative Development / FinTech:
- *Formulated an institutional-grade risk management framework enforcing ATR-volatility position sizing (1% constant dollar risk) and portfolio circuit breakers (5% daily loss cap).*
- *Developed pure vectorized NumPy/Pandas implementations of 6 technical indicators (EMA, RSI, MACD, Bollinger Bands, ATR, ADX), reducing runtime latency and eliminating third-party C-library dependencies.*
- *Implemented an adaptive Bayesian strategy ensemble with Laplace-smoothed dynamic performance weighting, automatically allocating greater authority to outperforming systems.*
- *Built a quantitative analytics engine computing annualized Sharpe Ratio, Sortino Ratio, Maximum Drawdown, and Profit Factor across multi-asset portfolios.*

---

## 📄 License
MIT License. Built for educational and portfolio demonstration purposes.
