"""
ApexQuant - Web Telemetry & Dashboard Server
Zero-dependency HTTP server providing REST API and interactive dashboard.
Uses Python's standard library http.server module.
"""

import json
import os
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

from core.engine import TradingEngine

class DashboardRequestHandler(BaseHTTPRequestHandler):
    engine: Optional[TradingEngine] = None
    html_content: str = ""

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging in terminal
        pass

    def _set_headers(self, content_type: str = "application/json", status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path in ["/", "/index.html"]:
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = "<h1>Trading Bot Dashboard - HTML not found</h1>"
            self._set_headers("text/html; charset=utf-8")
            self.wfile.write(content.encode("utf-8"))
            return

        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if parsed.path == "/api/status":
            if self.engine:
                data = self.engine.get_telemetry()
                self._set_headers("application/json")
                self.wfile.write(json.dumps(data).encode("utf-8"))
            else:
                self._set_headers("application/json", 503)
                self.wfile.write(json.dumps({"error": "Engine not initialized"}).encode("utf-8"))
            return

        self._set_headers("text/plain", 404)
        self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/backtest":
            if self.engine:
                report = self.engine.run_backtest(n_bars=250)
                self._set_headers("application/json")
                self.wfile.write(json.dumps(report).encode("utf-8"))
            else:
                self._set_headers("application/json", 503)
                self.wfile.write(json.dumps({"error": "Engine not ready"}).encode("utf-8"))
            return

        if parsed.path == "/api/step":
            if self.engine:
                # Run 5 cycles
                for _ in range(5):
                    self.engine.run_cycle_all_assets()
                data = self.engine.get_telemetry()
                self._set_headers("application/json")
                self.wfile.write(json.dumps(data).encode("utf-8"))
            else:
                self._set_headers("application/json", 503)
                self.wfile.write(json.dumps({"error": "Engine not ready"}).encode("utf-8"))
            return

        self._set_headers("text/plain", 404)
        self.wfile.write(b"Not Found")

def start_dashboard_server(engine: TradingEngine, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    """Initializes and starts the multithreaded HTTP telemetry dashboard server."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = "<h1>ApexQuant Dashboard - HTML file not found</h1>"

    DashboardRequestHandler.engine = engine
    DashboardRequestHandler.html_content = html_content

    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
