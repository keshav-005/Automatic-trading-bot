"""
Trading Bot Main CLI Runner
Author: Computer Science Student Project

Unified command-line interface for running:
1. Historical Backtests (--mode backtest)
2. Interactive Paper Trading & Web Dashboard (--mode demo)
3. Automated Unit Tests
"""

import argparse
import sys
import time
import webbrowser
from config import TradingConfig, default_config
from core.engine import TradingEngine
from dashboard.server import start_dashboard_server, DashboardRequestHandler, wsgi_app

# =======================================================================
# Vercel Cloud Serverless Entrypoints
# When deploying to Vercel, the Python runtime looks for:
# 1. 'handler' (inheriting from BaseHTTPRequestHandler)
# 2. 'app' or 'application' (WSGI callable)
# By exporting both, Vercel will immediately recognize and deploy the project!
# =======================================================================
handler = DashboardRequestHandler
app = wsgi_app
application = wsgi_app

def print_header(mode: str):
    print("\n" + "=" * 60)
    print(" TRADING BOT & BACKTESTING ENGINE (CSE PROJECT)")
    print(f" Mode: {mode.upper()} | Broker: Paper Trading (Local Simulation)")
    print("=" * 60)

def run_cli():
    parser = argparse.ArgumentParser(description="Algorithmic Trading Bot & Backtester")
    parser.add_argument(
        "--mode", 
        choices=["demo", "backtest", "dashboard", "live"], 
        default="demo",
        help="Run mode: 'demo' (stream paper trades + dashboard), 'backtest' (historical simulation), 'dashboard' (web only)"
    )
    parser.add_argument("--ticks", type=int, default=30, help="Number of simulated ticks in demo mode (default: 30)")
    parser.add_argument("--bars", type=int, default=200, help="Number of historical bars for backtesting (default: 200)")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard port (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    args = parser.parse_args()

    print_header(args.mode)

    # Configure engine
    config = default_config
    if args.mode == "live":
        config.execution_mode = "mt5"
    else:
        config.execution_mode = "paper"

    engine = TradingEngine(config)

    # 1. Backtest Mode
    if args.mode == "backtest":
        print(f"\n[1/2] Simulating historical execution across {len(config.assets)} symbols ({args.bars} bars each)...")
        start_time = time.time()
        report = engine.run_backtest(n_bars=args.bars)
        elapsed = time.time() - start_time

        print("\n" + "-" * 60)
        print("                BACKTEST PERFORMANCE REPORT")
        print("-" * 60)
        print(f" Total Trades Executed   : {report['total_trades']}")
        print(f" Winning Trades          : {report['winning_trades']} ({report['win_rate_pct']}%)")
        print(f" Losing Trades           : {report['losing_trades']}")
        print(f" Profit Factor           : {report['profit_factor']}")
        print(f" Initial Balance         : ${config.risk.account_balance:,.2f}")
        print(f" Final Equity            : ${report['current_equity']:,.2f}")
        print(f" Net Realized PnL        : ${report['net_pnl']:+,.2f} ({report['roi_pct']:+.2f}%)")
        print(f" Max Drawdown            : {report['max_drawdown_pct']}% (${report['max_drawdown_dollars']:,.2f})")
        print(f" Sharpe Ratio (Annual)   : {report['sharpe_ratio']}")
        print(f" Sortino Ratio           : {report['sortino_ratio']}")
        print(f" Avg Win / Loss          : ${report['avg_win']:.2f} / ${report['avg_loss']:.2f} (Payoff: {report['payoff_ratio']})")
        print(f" Backtest Run Time       : {elapsed:.2f}s")
        print("-" * 60)
        print("\nFinal Strategy Weights (Adaptive Allocation):")
        for strat, weight in report.get('strategy_weights', {}).items():
            print(f" - {strat:<20}: {weight*100:.1f}%")
        print("\n[OK] Backtest completed successfully.\n")
        return

    # 2. Start Web Dashboard
    print(f"\n[*] Starting web dashboard server on port {args.port}...")
    server = start_dashboard_server(engine, host="0.0.0.0", port=args.port)
    print(f"[OK] Dashboard live at:")
    print(f"     -> http://localhost:{args.port}")
    print(f"     -> http://127.0.0.1:{args.port}")

    if not args.no_browser:
        try:
            webbrowser.open(f"http://localhost:{args.port}")
        except Exception:
            pass

    # 3. Stream Demo Simulation
    if args.mode in ["demo", "live"]:
        print(f"\n[*] Running {args.ticks} paper trading simulation cycles...")
        print("    Press Ctrl+C to stop at any time.\n")
        try:
            for i in range(1, args.ticks + 1):
                engine.run_cycle_all_assets()
                time.sleep(0.4)
            print(f"\n[OK] Finished {args.ticks} simulation cycles.")
            print(f"    Dashboard remains active at http://localhost:{args.port}")
            print("    Press Ctrl+C to exit.\n")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped by user.")
    elif args.mode == "dashboard":
        print(f"\n[OK] Dashboard active at http://localhost:{args.port}. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped by user.")

if __name__ == "__main__":
    run_cli()
