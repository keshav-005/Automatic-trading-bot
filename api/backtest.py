import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Make sure we can import from the project root regardless of where Vercel invokes this from
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import directly — avoids pulling in dashboard.server which triggers unneeded side effects
from core.engine import TradingEngine
from config import default_config


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access log noise

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _run(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            try:
                n_bars = max(30, min(500, int(params.get("bars", ["200"])[0])))
            except (ValueError, IndexError):
                n_bars = 200

            # Spin up a fresh engine for each backtest — Vercel is stateless anyway
            engine = TradingEngine(default_config)
            report = engine.run_backtest(n_bars=n_bars)
            report["ok"] = True

            body = json.dumps(report).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

        except Exception as e:
            # Always return a parseable JSON body so the frontend doesn't get an empty response
            err = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self._cors()
            self.end_headers()
            self.wfile.write(err)
            self.wfile.flush()

    def do_GET(self):
        self._run()

    def do_POST(self):
        self._run()
