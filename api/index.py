import json
import os
import sys
from http.server import BaseHTTPRequestHandler

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        body = json.dumps({
            "service": "AlgoTrader API",
            "status": "online",
            "endpoints": {
                "/api/status": "Live telemetry + simulation tick (GET/POST)",
                "/api/step":   "Advance simulation by N cycles (POST)",
                "/api/backtest": "Run historical backtest (POST)",
                "/api/reset":  "Reset simulation to starting balance (POST)"
            }
        }, indent=2).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_POST(self):
        self.do_GET()
