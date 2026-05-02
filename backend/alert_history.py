"""
alert_history.py - Persistent JSON alert history log.

Every finalized alert is appended to backend/data/alert_history.json.
The file is a plain JSON array — delete or clear it at any time to reset.

Each record contains:
  logged_at        UTC timestamp when written
  event_id         Pinnacle/Swordfish event ID
  timestamp        When the alert first arrived
  teams            {home, away, league}
  result           found / not_found / ev_found / error / skipped_prop
  ev_summary       [{market, selection, ev_pct}] for every market checked
  steps            Full step-by-step processing trace (ALERT IN, SEARCH, MATCH, EV ...)
"""

import json
import os
import threading
from datetime import datetime
from typing import Dict

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "alert_history.json")
_write_lock = threading.Lock()


def append_alert_to_history(record: Dict) -> None:
    """Append a finalized alert record to the JSON history file (non-blocking)."""
    def _write():
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with _write_lock:
                if os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > 2:
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        try:
                            history = json.load(f)
                            if not isinstance(history, list):
                                history = []
                        except (json.JSONDecodeError, ValueError):
                            history = []
                else:
                    history = []

                entry = {
                    "logged_at": datetime.utcnow().isoformat() + "Z",
                    **record,
                }
                history.append(entry)

                tmp = HISTORY_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2, default=str)
                os.replace(tmp, HISTORY_FILE)

        except Exception as exc:
            print(f"[AlertHistory] Write failed: {exc}")

    threading.Thread(target=_write, daemon=True).start()


def get_history() -> list:
    """Return all records from the history file (for API endpoints)."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def clear_history() -> None:
    """Wipe the history file (creates an empty array)."""
    with _write_lock:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
