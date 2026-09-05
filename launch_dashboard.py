"""
Dedicated Dashboard Launcher
Author: Computer Science Student Project

Run this script to start the web dashboard and let the simulation run in the background:
    python launch_dashboard.py
Then visit http://localhost:8080 in your browser.
"""

import time
import webbrowser
from config import default_config
from core.engine import TradingEngine
from dashboard.server import start_dashboard_server

def main():
    print("[*] Starting Trading Bot Dashboard...")
    engine = TradingEngine(default_config)
    
    # Warm up with a few cycles so tables and metrics have initial data
    for _ in range(10):
        engine.run_cycle_all_assets()

    port = 8080
    server = start_dashboard_server(engine, host="0.0.0.0", port=port)
    print(f"[OK] Dashboard live at:")
    print(f"     -> http://localhost:{port}")
    print(f"     -> http://127.0.0.1:{port}")
    
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass
    
    print("\n[INFO] Simulating live market ticks in background. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1.5)
            engine.run_cycle_all_assets()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")

if __name__ == "__main__":
    main()
