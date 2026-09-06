"""
Local development HTTP server and Vercel WSGI adapter.

Provides two modes:
1. ThreadingHTTPServer — used when running locally via `python main.py`.
2. wsgi_app / handler — the interface Vercel expects from Python serverless functions.
"""

import json
import os
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

from core.engine import TradingEngine
from config import default_config

# Shared engine instance — persists across requests within a single process.
# On Vercel each invocation is a cold start, so this is effectively per-request.
_global_engine: Optional[TradingEngine] = None


def get_global_engine() -> TradingEngine:
    """Return the shared engine, initializing it on first call with a warm-up run."""
    global _global_engine
    if _global_engine is None:
        _global_engine = TradingEngine(default_config)
        for _ in range(8):
            _global_engine.run_cycle_all_assets()
    return _global_engine


def get_dashboard_html() -> str:
    """Locate and return index.html, searching several candidate paths."""
    search_paths = [
        os.path.join(os.getcwd(), "index.html"),
        os.path.join(os.getcwd(), "public", "index.html"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html"),
    ]
    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                continue
    return "<h1>Trading Dashboard — index.html not found</h1>"


class DashboardRequestHandler(BaseHTTPRequestHandler):
    engine: Optional[TradingEngine] = None

    @property
    def active_engine(self) -> TradingEngine:
        return self.engine if self.engine is not None else get_global_engine()

    def log_message(self, format, *args):
        pass  # suppress default access log noise

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
        path = parsed.path.lower().rstrip("/")
        query = parse_qs(parsed.query)

        if "favicon.ico" in path:
            self.send_response(204)
            self.end_headers()
            return

        if "status" in path:
            tick = query.get("tick", ["1"])[0]
            if tick != "0":
                self.active_engine.run_cycle_all_assets()
            body = json.dumps(self.active_engine.get_telemetry()).encode("utf-8")
            self._set_headers(length=len(body))
            self.wfile.write(body)
            return

        if "backtest" in path:
            try:
                n_bars = max(30, min(500, int(query.get("bars", ["200"])[0])))
            except (ValueError, IndexError):
                n_bars = 200
            report = self.active_engine.run_backtest(n_bars=n_bars)
            report["ok"] = True
            body = json.dumps(report).encode("utf-8")
            self._set_headers(length=len(body))
            self.wfile.write(body)
            return

        if "step" in path:
            for _ in range(5):
                self.active_engine.run_cycle_all_assets()
            data = self.active_engine.get_telemetry()
            data["ok"] = True
            body = json.dumps(data).encode("utf-8")
            self._set_headers(length=len(body))
            self.wfile.write(body)
            return

        # Default: serve the dashboard HTML
        body = get_dashboard_html().encode("utf-8")
        self._set_headers(content_type="text/html; charset=utf-8", length=len(body))
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.lower().rstrip("/")
        query = parse_qs(parsed.query)

        if "backtest" in path:
            try:
                n_bars = max(30, min(500, int(query.get("bars", ["200"])[0])))
            except (ValueError, IndexError):
                n_bars = 200
            report = self.active_engine.run_backtest(n_bars=n_bars)
            report["ok"] = True
            body = json.dumps(report).encode("utf-8")
            self._set_headers(length=len(body))
            self.wfile.write(body)
            return

        if "step" in path:
            for _ in range(5):
                self.active_engine.run_cycle_all_assets()
            data = self.active_engine.get_telemetry()
            data["ok"] = True
            body = json.dumps(data).encode("utf-8")
            self._set_headers(length=len(body))
            self.wfile.write(body)
            return

        if "reset" in path:
            global _global_engine
            _global_engine = TradingEngine(default_config)
            for _ in range(5):
                _global_engine.run_cycle_all_assets()
            data = _global_engine.get_telemetry()
            data["ok"] = True
            body = json.dumps(data).encode("utf-8")
            self._set_headers(length=len(body))
            self.wfile.write(body)
            return

        # Fallback: return current state
        body = json.dumps(self.active_engine.get_telemetry()).encode("utf-8")
        self._set_headers(length=len(body))
        self.wfile.write(body)


def wsgi_app(environ, start_response):
    """WSGI entry point for Vercel, Gunicorn, or any PEP-3333 compatible server."""
    raw_path = environ.get("PATH_INFO", "/").lower()
    method = environ.get("REQUEST_METHOD", "GET").upper()
    query = parse_qs(environ.get("QUERY_STRING", ""))
    engine = get_global_engine()

    cors_headers = [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]

    if method == "OPTIONS":
        start_response("204 No Content", cors_headers)
        return [b""]

    if "favicon.ico" in raw_path:
        start_response("204 No Content", [("Content-Length", "0")])
        return [b""]

    if "status" in raw_path:
        tick = query.get("tick", ["1"])[0]
        if tick != "0":
            engine.run_cycle_all_assets()
        body = json.dumps(engine.get_telemetry()).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))] + cors_headers)
        return [body]

    if "backtest" in raw_path:
        try:
            n_bars = max(30, min(500, int(query.get("bars", ["200"])[0])))
        except (ValueError, IndexError):
            n_bars = 200
        report = engine.run_backtest(n_bars=n_bars)
        report["ok"] = True
        body = json.dumps(report).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))] + cors_headers)
        return [body]

    if "step" in raw_path:
        for _ in range(5):
            engine.run_cycle_all_assets()
        data = engine.get_telemetry()
        data["ok"] = True
        body = json.dumps(data).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))] + cors_headers)
        return [body]

    if "reset" in raw_path:
        global _global_engine
        _global_engine = TradingEngine(default_config)
        for _ in range(5):
            _global_engine.run_cycle_all_assets()
        data = _global_engine.get_telemetry()
        data["ok"] = True
        body = json.dumps(data).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))] + cors_headers)
        return [body]

    if method == "GET":
        body = get_dashboard_html().encode("utf-8")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]

    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


def start_dashboard_server(engine: TradingEngine, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    """Start a local multithreaded HTTP server in a background daemon thread."""
    DashboardRequestHandler.engine = engine
    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
