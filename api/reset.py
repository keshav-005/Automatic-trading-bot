"""
Vercel Serverless Function: Reset Simulation State
Author: Computer Science Student Project
Endpoint: /api/reset

Resets the trading simulation back to clean starting balance and state.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dashboard import server
from core.engine import TradingEngine
from config import default_config

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

    def _reset(self):
        try:
            # Recreate global engine
            server._global_engine = TradingEngine(default_config)
            for _ in range(5):
                server._global_engine.run_cycle_all_assets()
            telemetry = server._global_engine.get_telemetry()
            telemetry["ok"] = True
            body = json.dumps(telemetry).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err_body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(err_body)

    def do_GET(self):
        self._reset()

    def do_POST(self):
        self._reset()
