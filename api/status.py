"""
Vercel Serverless Function: Telemetry & Live Tick Feed
Author: Computer Science Student Project
Endpoint: /api/status

Handles GET and POST requests for live trading engine state.
Advances simulation ticks automatically when requested to provide
a live, streaming experience even on stateless serverless infrastructure.
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
        # Silence console access logs
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _respond_status(self):
        try:
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)
            engine = get_global_engine()

            # Advance simulation cycle by 1 bar unless explicitly paused via tick=0
            tick = query_params.get("tick", ["1"])[0]
            if tick != "0":
                engine.run_cycle_all_assets()

            telemetry = engine.get_telemetry()
            body = json.dumps(telemetry).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err_body = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(err_body)

    def do_GET(self):
        self._respond_status()

    def do_POST(self):
        self._respond_status()
