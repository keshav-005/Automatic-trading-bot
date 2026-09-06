"""
Vercel Serverless Function: Advance Simulation Cycles
Author: Computer Science Student Project
Endpoint: /api/step

Advances the trading engine by N cycles across all assets and returns updated telemetry.
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

    def _step_simulation(self):
        try:
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)
            cycles_param = query_params.get("cycles", ["5"])[0]
            try:
                n_cycles = max(1, min(50, int(cycles_param)))
            except ValueError:
                n_cycles = 5

            engine = get_global_engine()
            for _ in range(n_cycles):
                engine.run_cycle_all_assets()

            telemetry = engine.get_telemetry()
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
        self._step_simulation()

    def do_POST(self):
        self._step_simulation()
