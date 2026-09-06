"""
Vercel Serverless Function: Historical Multi-Asset Backtest
Author: Computer Science Student Project
Endpoint: /api/backtest

Runs a quantitative backtesting simulation across all 8 configured assets
and returns Sharpe ratio, Max Drawdown, Win Rate, and trade history in JSON.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure repository root is in Python module search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dashboard.server import get_global_engine

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _execute_backtest(self):
        try:
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)
            bars_param = query_params.get("bars", ["200"])[0]
            try:
                n_bars = max(30, min(500, int(bars_param)))
            except ValueError:
                n_bars = 200

            engine = get_global_engine()
            report = engine.run_backtest(n_bars=n_bars)
            report["ok"] = True

            body = json.dumps(report).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err_body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(200)  # Return 200 with JSON error so frontend displays human error message
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(err_body)

    def do_GET(self):
        self._execute_backtest()

    def do_POST(self):
        self._execute_backtest()
