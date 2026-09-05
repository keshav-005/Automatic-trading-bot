"""
Web Dashboard & Serverless API Server
Author: Computer Science Student Project

Provides:
1. Local multithreaded HTTP server (for running locally via python main.py or run_demo.bat)
2. WSGI 'app' and BaseHTTPRequestHandler 'handler' (for cloud serverless deployments like Vercel)
"""

import json
import os
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from typing import Optional

from core.engine import TradingEngine
from config import default_config

# Global singleton engine instance (used across serverless function invocations)
_global_engine: Optional[TradingEngine] = None

def get_global_engine() -> TradingEngine:
    """Returns a shared TradingEngine instance, pre-seeded with initial simulation data."""
    global _global_engine
    if _global_engine is None:
        _global_engine = TradingEngine(default_config)
        # Pre-seed with a few ticks so the dashboard is immediately populated on first load
        for _ in range(8):
            _global_engine.run_cycle_all_assets()
    return _global_engine

def get_dashboard_html() -> str:
    """Finds and reads index.html from multiple possible relative paths."""
    search_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"),
        os.path.join(os.getcwd(), "dashboard", "index.html"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard", "index.html"),
        "dashboard/index.html"
    ]
    for path in search_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return "<h1>Trading Bot Dashboard - index.html not found</h1>"

class DashboardRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler compatible with both local ThreadingHTTPServer
    and Vercel's Serverless Python runtime.
    """
    engine: Optional[TradingEngine] = None

    @property
    def active_engine(self) -> TradingEngine:
        """Returns the configured engine or falls back to the shared global singleton."""
        if self.engine is not None:
            return self.engine
        return get_global_engine()

    def log_message(self, format, *args):
        # Silence standard terminal request logging noise
        pass

    def _set_headers(self, content_type: str = "application/json", status: int = 200, length: Optional[int] = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(status=204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "":
            path = "/"

        # 1. Serve HTML Dashboard
        if path in ["/", "/index.html"]:
            body = get_dashboard_html().encode("utf-8")
            self._set_headers(content_type="text/html; charset=utf-8", length=len(body))
            self.wfile.write(body)
            return

        # 2. Favicon
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 3. Status Telemetry API
        if path == "/api/status":
            data = self.active_engine.get_telemetry()
            body = json.dumps(data).encode("utf-8")
            self._set_headers(content_type="application/json", length=len(body))
            self.wfile.write(body)
            return

        # 4. Fallback 404
        self._set_headers(content_type="text/plain", status=404, length=9)
        self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # 1. Run Historical Backtest
        if path == "/api/backtest":
            report = self.active_engine.run_backtest(n_bars=200)
            body = json.dumps(report).encode("utf-8")
            self._set_headers(content_type="application/json", length=len(body))
            self.wfile.write(body)
            return

        # 2. Step 5 simulation cycles
        if path == "/api/step":
            for _ in range(5):
                self.active_engine.run_cycle_all_assets()
            data = self.active_engine.get_telemetry()
            body = json.dumps(data).encode("utf-8")
            self._set_headers(content_type="application/json", length=len(body))
            self.wfile.write(body)
            return

        self._set_headers(content_type="text/plain", status=404, length=9)
        self.wfile.write(b"Not Found")

def wsgi_app(environ, start_response):
    """
    Standard WSGI callable (PEP 3333) for deployment on WSGI servers,
    Vercel, AWS Lambda, or Gunicorn.
    """
    path = environ.get("PATH_INFO", "/")
    if path.rstrip("/") == "":
        path = "/"
        
    method = environ.get("REQUEST_METHOD", "GET").upper()
    engine = get_global_engine()

    if method == "OPTIONS":
        start_response("204 No Content", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ])
        return [b""]

    if method == "GET":
        if path in ["/", "/index.html"]:
            body = get_dashboard_html().encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Access-Control-Allow-Origin", "*")
            ])
            return [body]
        elif path == "/favicon.ico":
            start_response("204 No Content", [("Content-Length", "0")])
            return [b""]
        elif path == "/api/status":
            data = engine.get_telemetry()
            body = json.dumps(data).encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Access-Control-Allow-Origin", "*")
            ])
            return [body]

    elif method == "POST":
        if path == "/api/step":
            for _ in range(5):
                engine.run_cycle_all_assets()
            data = engine.get_telemetry()
            body = json.dumps(data).encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Access-Control-Allow-Origin", "*")
            ])
            return [body]
        elif path == "/api/backtest":
            report = engine.run_backtest(n_bars=200)
            body = json.dumps(report).encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Access-Control-Allow-Origin", "*")
            ])
            return [body]

    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]

def start_dashboard_server(engine: TradingEngine, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    """Initializes and starts a local multithreaded HTTP server."""
    DashboardRequestHandler.engine = engine
    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
