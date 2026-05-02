"""
alert_logger.py — Per-alert structured logging with ring buffer.

Uses a global dict keyed by event_id so any thread can retrieve the logger
for an in-progress alert (e.g. the BetBCK worker thread).

Usage:
    from alert_logger import start_alert_log, get_logger_for_event, finalize_alert_log

    start_alert_log(event_id)
    log = get_logger_for_event(event_id)
    log.log_raw_alert(payload)
    ...
    record = finalize_alert_log(event_id)   # stores in ring buffer, returns dict
"""

import threading
import traceback
from collections import deque
from datetime import datetime
from typing import Optional, Dict, Any, List

# ── Ring buffer (last 50 alerts) ──────────────────────────────────────────────
_RING_BUFFER_SIZE = 50
_ring_buffer: deque = deque(maxlen=_RING_BUFFER_SIZE)
_buffer_lock = threading.Lock()

# ── Active logger registry (event_id → AlertLogger) ───────────────────────────
_active_loggers: Dict[str, "AlertLogger"] = {}
_loggers_lock = threading.Lock()


def get_alert_log_ring_buffer() -> List[Dict]:
    with _buffer_lock:
        return list(_ring_buffer)


def start_alert_log(event_id: str) -> "AlertLogger":
    logger = AlertLogger(str(event_id))
    with _loggers_lock:
        _active_loggers[str(event_id)] = logger
    return logger


def get_logger_for_event(event_id: str) -> Optional["AlertLogger"]:
    with _loggers_lock:
        return _active_loggers.get(str(event_id))


def finalize_alert_log(event_id: str) -> Optional[Dict]:
    with _loggers_lock:
        logger = _active_loggers.pop(str(event_id), None)
    if logger is None:
        return None
    record = logger.finalize()
    with _buffer_lock:
        _ring_buffer.appendleft(record)
    return record


# ── AlertLogger ───────────────────────────────────────────────────────────────
class AlertLogger:
    def __init__(self, event_id: str):
        self.event_id = event_id
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.steps: List[Dict] = []
        self.teams: Dict = {}
        self.result: str = "pending"
        self.ev_summary: List[Dict] = []
        self._divider = "=" * 60

    def _step(self, tag: str, message: str, detail: Any = None) -> Dict:
        step = {"tag": tag, "message": message, "detail": detail}
        self.steps.append(step)
        detail_str = f"\n  detail={detail}" if detail and tag in ("ERROR",) else ""
        print(f"[{tag}][{self.event_id}] {message}{detail_str}")
        return step

    # ── Public API ────────────────────────────────────────────────────────────

    def log_raw_alert(self, payload: Dict):
        home = payload.get("homeTeam", "?")
        away = payload.get("awayTeam", "?")
        league = payload.get("leagueName", "?")
        market = payload.get("marketType", payload.get("bet_type", "?"))
        old_odds = payload.get("oldOdds", "?")
        new_odds = payload.get("newOdds", "?")
        self.teams = {"home": home, "away": away, "league": league}
        print(self._divider)
        self._step(
            "ALERT IN",
            f"{away} @ {home} | {league} | market={market} | {old_odds} -> {new_odds}",
            {"home": home, "away": away, "league": league, "market": market,
             "old_odds": old_odds, "new_odds": new_odds},
        )

    def log_prop_skip(self, home: str, away: str, reason: str):
        self.result = "skipped_prop"
        self._step("SKIP", f"Prop/corner bet skipped: {reason}", {"home": home, "away": away})

    def log_search_term(self, search_term: str, raw_home: str, raw_away: str, reason: str):
        self._step(
            "SEARCH TERM",
            f"Using '{search_term}' (from '{raw_home}' / '{raw_away}'): {reason}",
        )

    def log_search(self, term: str, status_code: int, response_size: int, url: str = ""):
        display_url = url or "PlayerGameSelection.php"
        self._step(
            "SEARCH",
            f"POST {display_url}?keyword='{term}' -> HTTP {status_code} ({response_size} bytes)",
            {"url": url, "search_term": term, "status": status_code, "response_bytes": response_size},
        )

    def log_search_error(self, term: str, exc: Exception, context: str = ""):
        self.result = "error"
        msg = f"BetBCK search POST failed for '{term}': {context or exc}"
        import traceback as _tb
        self.steps.append({"tag": "ERROR", "message": msg, "detail": {"traceback": _tb.format_exc()}})
        print(f"[ERROR][{self.event_id}] {msg}")

    def log_match_candidate(
        self,
        bck_home: str, bck_away: str,
        pod_home: str, pod_away: str,
        scores: Dict, passed: bool,
    ):
        result_str = "PASS" if passed else "FAIL"
        score_str = " | ".join(f"{k}={v}" for k, v in scores.items())
        self._step(
            "MATCH",
            f"[{result_str}] BCK '{bck_home}' vs '{bck_away}'  <->  POD '{pod_home}' vs '{pod_away}'  [{score_str}]",
            {"bck_home": bck_home, "bck_away": bck_away,
             "pod_home": pod_home, "pod_away": pod_away,
             "scores": scores, "passed": passed},
        )

    def log_not_found(self, pod_home: str, pod_away: str, league: str):
        self.result = "not_found"
        msg = f"FAILED TO FIND MATCHING GAME on BetBCK for {pod_away} @ {pod_home} ({league})"
        print(f"[NOT FOUND][{self.event_id}] {msg}")
        self.steps.append({"tag": "NOT FOUND", "message": msg, "detail": None})

    def log_found(self, bck_home: str, bck_away: str):
        self.result = "found"
        self._step("FOUND", f"Matched BetBCK: '{bck_home}' vs '{bck_away}'")

    def log_odds(self, odds_dict: Dict):
        parts = []
        for k, v in odds_dict.items():
            if v is not None and v != [] and v != {}:
                parts.append(f"{k}={v}")
        self._step("ODDS", " | ".join(parts) if parts else "No odds extracted", odds_dict)

    def log_ev(self, market: str, selection: str, bck_dec: float, pin_nvp_dec: float, ev_pct: float):
        sign = "+" if ev_pct >= 0 else ""
        msg = (
            f"{market} {selection}: "
            f"BCK {bck_dec:.4f} / PIN_NVP {pin_nvp_dec:.4f} - 1 = {sign}{ev_pct * 100:.2f}%"
        )
        self._step("EV", msg, {
            "market": market, "selection": selection,
            "bck_decimal": round(bck_dec, 4),
            "pin_nvp_decimal": round(pin_nvp_dec, 4),
            "ev_pct": round(ev_pct * 100, 2),
        })
        self.ev_summary.append({
            "market": market, "selection": selection,
            "ev_pct": round(ev_pct * 100, 2),
        })

    def log_error(self, exc: Exception, context: str = ""):
        self.result = "error"
        tb = traceback.format_exc()
        msg = f"{context}: {exc}" if context else str(exc)
        self._step("ERROR", msg, {"traceback": tb})
        print(f"[ERROR][{self.event_id}] Full traceback:\n{tb}")

    def log_info(self, message: str, detail: Any = None):
        self._step("INFO", message, detail)

    def set_result(self, result: str):
        self.result = result

    def finalize(self) -> Dict:
        if self.result == "pending":
            self.result = "completed"
        positive_ev = [e for e in self.ev_summary if e["ev_pct"] > 0]
        if positive_ev and self.result not in ("error", "not_found", "skipped_prop"):
            self.result = "ev_found"
        record = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "teams": self.teams,
            "steps": self.steps,
            "result": self.result,
            "ev_summary": self.ev_summary,
        }
        print(f"[ALERT DONE][{self.event_id}] result={self.result} | EV markets={len(self.ev_summary)} | positive_ev={len(positive_ev)}")
        print(self._divider)
        return record
