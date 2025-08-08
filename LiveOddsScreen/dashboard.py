import http.server
import json
import socketserver
import threading
from pathlib import Path
from typing import List, Dict, Any

from rich import print
from schema import EventOdds


def build_best_table(events: List[EventOdds]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for e in events:
        best = e.best_side_with_value()
        avg = e.average_odds()
        rows.append({
            "sport": e.sport,
            "market": e.market,
            "home": e.home,
            "away": e.away,
            "best_home": best.get("home"),
            "best_away": best.get("away"),
            "avg_home": avg.get("home"),
            "avg_away": avg.get("away"),
            "books": e.books,
        })
    # Sort rows where either home or away best is "betbck" to surface user's best lines
    rows.sort(key=lambda r: int((r.get("best_home") == "betbck") or (r.get("best_away") == "betbck")), reverse=True)
    return rows


def serve_dashboard(rows: List[Dict[str, Any]], port: int = 8765):
    out = {
        "generated": True,
        "rows": rows,
    }
    out_path = Path("LiveOddsScreen/output.json")
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    def run_server():
        class ThreadingServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
        with ThreadingServer(("127.0.0.1", port), Handler) as httpd:
            print(f"Dashboard at http://127.0.0.1:{port}/LiveOddsScreen/dashboard.html")
            httpd.serve_forever()

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    return t

