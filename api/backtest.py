import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Make sure we can import from the project root regardless of where Vercel invokes this from
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.engine import TradingEngine
from config import default_config, RiskConfig


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
            payload = {}
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                try:
                    raw_body = self.rfile.read(content_length)
                    payload = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    payload = {}

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            # Bar count: from payload or query params
            bars_val = payload.get("bars") or params.get("bars", ["200"])[0]
            try:
                n_bars = max(30, min(500, int(bars_val)))
            except (ValueError, TypeError):
                n_bars = 200

            # Custom Risk rules
            custom_risk = None
            if payload:
                init_bal = float(payload.get("initial_balance", 10000.0))
                risk_pct = float(payload.get("risk_per_trade", 1.0))
                # If entered as e.g. 1.0 (meaning 1%), convert to 0.01
                if risk_pct > 0.5:
                    risk_pct = risk_pct / 100.0
                risk_pct = max(0.001, min(0.10, risk_pct))

                rr_ratio = max(0.5, min(10.0, float(payload.get("risk_reward_ratio", 1.8))))
                atr_sl = max(0.5, min(5.0, float(payload.get("atr_multiplier_sl", 1.5))))
                max_pos = max(1, min(15, int(payload.get("max_open_positions", 5))))

                custom_risk = RiskConfig(
                    account_balance=max(100.0, init_bal),
                    risk_per_trade=risk_pct,
                    risk_reward_ratio=rr_ratio,
                    atr_multiplier_sl=atr_sl,
                    max_open_positions=max_pos
                )

            # Custom Strategy conditions
            custom_strategies = None
            if payload:
                custom_strategies = {
                    "enabled_strategies": payload.get("enabled_strategies"),
                    "strategy_params": payload.get("strategy_params", {}),
                    "strategy_weights": payload.get("strategy_weights"),
                    "adx_threshold": float(payload.get("adx_threshold", 22.0)),
                    "confidence_threshold": float(payload.get("confidence_threshold", 0.40))
                }

            # Selected assets
            selected_assets = payload.get("assets") if payload else None
            if not selected_assets and "assets" in params:
                selected_assets = [a.strip().upper() for a in params["assets"][0].split(",") if a.strip()]

            # Spin up a fresh engine for each backtest — isolated and safe
            engine = TradingEngine(default_config)
            report = engine.run_backtest(
                n_bars=n_bars,
                custom_risk=custom_risk,
                custom_strategies=custom_strategies,
                selected_assets=selected_assets
            )
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
