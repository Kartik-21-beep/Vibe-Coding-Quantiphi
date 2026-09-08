import json
import os
import random
import sqlite3
from builtins import KeyError, OSError, ValueError, bool, dict, int, len, print, round, sorted, str
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
DB_PATH = ROOT / "currency_converter.db"
API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")
DEMO_RATES = {
    "USD": 1.0, "EUR": 0.92, "GBP": 0.78, "INR": 83.1, "JPY": 149.2,
    "AUD": 1.52, "CAD": 1.36, "CHF": 0.9, "CNY": 7.24, "SGD": 1.34,
}


def host_api_key():
    return (
        os.getenv("EXCHANGERATE_HOST_ACCESS_KEY")
        or os.getenv("EXCHANGERATE_HOST_API_KEY")
        or os.getenv("EXCHANGE_RATE_HOST_API_KEY")
        or ""
    ).strip()


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE IF NOT EXISTS conversions "
        "(id INTEGER PRIMARY KEY, source TEXT, target TEXT, amount REAL, result REAL, created_at TEXT)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS favorites "
        "(source TEXT NOT NULL, target TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "PRIMARY KEY (source, target))"
    )
    connection.commit()
    return connection


def live_rates(base):
    if API_KEY:
        url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{base}"
        try:
            with urlopen(Request(url, headers={"User-Agent": "CurrencyCanvas/1.0"}), timeout=8) as response:
                payload = json.loads(response.read())
                if payload.get("result") == "success":
                    return payload["conversion_rates"], "live"
        except (OSError, ValueError):
            pass
    access_key = host_api_key()
    if access_key:
        try:
            params = urlencode({"access_key": access_key, "source": base})
            with urlopen(
                Request(
                    f"https://api.exchangerate.host/live?{params}",
                    headers={"User-Agent": "CurrencyCanvas/1.0"},
                ),
                timeout=8,
            ) as response:
                payload = json.loads(response.read())
                if payload.get("success") and payload.get("quotes"):
                    prefix = f"{base}"
                    rates = {
                        code.replace(prefix, ""): value
                        for code, value in payload["quotes"].items()
                        if code.startswith(prefix)
                    }
                    rates[base] = 1
                    return rates, "live"
        except (OSError, ValueError):
            pass
    try:
        with urlopen(
            Request(
                f"https://api.frankfurter.app/latest?from={base}",
                headers={"User-Agent": "CurrencyCanvas/1.0"},
            ),
            timeout=8,
        ) as response:
            payload = json.loads(response.read())
            if payload.get("rates"):
                return {base: 1, **payload["rates"]}, "live"
    except (OSError, ValueError):
        pass
    base_rate = DEMO_RATES.get(base, 1)
    return {currency: round(rate / base_rate, 6) for currency, rate in DEMO_RATES.items()}, "demo"


def demo_historical_rates(source, target):
    source_rate = DEMO_RATES.get(source, 1)
    target_rate = DEMO_RATES.get(target, 1)
    current_rate = target_rate / source_rate
    points = []
    for index in range(30):
        current_rate *= 1 + random.uniform(-0.012, 0.012)
        points.append(
            {
                "date": (date.today() - timedelta(days=29 - index)).isoformat(),
                "rate": round(current_rate, 6),
            }
        )
    return points


def historical_rates(source, target):
    access_key = host_api_key()
    if not access_key:
        return demo_historical_rates(source, target)

    end = date.today()
    start = end - timedelta(days=29)
    params = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "source": source,
        "currencies": target,
    }
    params["access_key"] = access_key
    url = f"https://api.exchangerate.host/timeseries?{urlencode(params)}"
    with urlopen(Request(url, headers={"User-Agent": "CurrencyCanvas/1.0"}), timeout=8) as response:
        payload = json.loads(response.read())
    if payload.get("success") is False:
        return demo_historical_rates(source, target)
    points = [
        {"date": day, "rate": values[target]}
        for day, values in sorted(payload.get("rates", {}).items())
        if target in values
    ]
    if not points:
        return demo_historical_rates(source, target)
    return points


class Handler(BaseHTTPRequestHandler):
    def json_response(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/rates":
            base = query.get("base", ["USD"])[0].upper()
            rates, source = live_rates(base)
            self.json_response({"base": base, "rates": rates, "source": source})
        elif parsed.path == "/api/history":
            source = query.get("source", ["USD"])[0].upper()
            target = query.get("target", ["EUR"])[0].upper()
            try:
                points = historical_rates(source, target) if source != target else [
                    {"date": date.today().isoformat(), "rate": 1}
                ]
                self.json_response(
                    {
                        "source": source,
                        "target": target,
                        "points": points,
                        "source_type": "demo" if not host_api_key() else "live",
                    }
                )
            except (OSError, ValueError, KeyError):
                self.json_response(
                    {
                        "source": source,
                        "target": target,
                        "points": demo_historical_rates(source, target),
                        "source_type": "demo",
                    },
                )
        elif parsed.path == "/api/favorites":
            with db() as connection:
                rows = connection.execute("SELECT source, target FROM favorites ORDER BY created_at DESC").fetchall()
            self.json_response({"favorites": [dict(row) for row in rows]})
        else:
            self.serve_file(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or "{}")
        except ValueError:
            self.json_response({"error": "Invalid JSON"}, 400)
            return
        source, target = payload.get("source", "").upper(), payload.get("target", "").upper()
        if parsed.path == "/api/conversions":
            with db() as connection:
                connection.execute(
                    "INSERT INTO conversions(source,target,amount,result,created_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",
                    (source, target, payload.get("amount", 0), payload.get("result", 0)),
                )
            self.json_response({"saved": True}, 201)
        elif parsed.path == "/api/favorites" and source and target:
            with db() as connection:
                connection.execute("INSERT OR IGNORE INTO favorites(source,target) VALUES(?,?)", (source, target))
            self.json_response({"saved": True}, 201)
        else:
            self.json_response({"error": "Unsupported request"}, 400)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/favorites":
            with db() as connection:
                connection.execute(
                    "DELETE FROM favorites WHERE source=? AND target=?",
                    (query.get("source", [""])[0].upper(), query.get("target", [""])[0].upper()),
                )
            self.json_response({"deleted": True})
        else:
            self.json_response({"error": "Unsupported request"}, 404)

    def serve_file(self, path):
        requested = ROOT / ("index.html" if path in ("/", "") else path.lstrip("/"))
        if not requested.is_file() or ROOT not in requested.resolve().parents and requested.resolve() != ROOT:
            self.send_error(404)
            return
        content_type = "text/html" if requested.suffix == ".html" else "text/css" if requested.suffix == ".css" else "application/javascript"
        body = requested.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    db().close()
    print("Currency Canvas running at http://localhost:8000")
    ThreadingHTTPServer(("localhost", 8000), Handler).serve_forever()
