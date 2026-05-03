import json
import os
from datetime import datetime, timezone

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs", "bets")


def _ensure_dir():
    os.makedirs(LOGS_DIR, exist_ok=True)


def _write(path: str, record: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_bet_placed(
    event_id: str,
    market: str,
    selection: str,
    line: str,
    odds_at_placement,
    pinnacle_nvp_at_placement,
    ev_pct_at_placement,
    kelly_fraction,
    stake,
    home_team: str = "",
    away_team: str = "",
    extra: dict = None,
):
    _ensure_dir()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "market": market,
        "selection": selection,
        "line": line,
        "odds_at_placement": odds_at_placement,
        "pinnacle_nvp_at_placement": pinnacle_nvp_at_placement,
        "ev_pct_at_placement": ev_pct_at_placement,
        "kelly_fraction": kelly_fraction,
        "stake": stake,
        "result": "placed",
    }
    if extra:
        record.update(extra)
    _write(os.path.join(LOGS_DIR, "bets_placed.jsonl"), record)


def log_bet_failed(
    event_id: str,
    market: str,
    selection: str,
    line: str,
    odds_at_placement,
    pinnacle_nvp_at_placement,
    ev_pct_at_placement,
    kelly_fraction,
    stake,
    failure_reason: str = "",
    home_team: str = "",
    away_team: str = "",
    extra: dict = None,
):
    _ensure_dir()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "market": market,
        "selection": selection,
        "line": line,
        "odds_at_placement": odds_at_placement,
        "pinnacle_nvp_at_placement": pinnacle_nvp_at_placement,
        "ev_pct_at_placement": ev_pct_at_placement,
        "kelly_fraction": kelly_fraction,
        "stake": stake,
        "result": "failed",
        "failure_reason": failure_reason,
    }
    if extra:
        record.update(extra)
    _write(os.path.join(LOGS_DIR, "bets_failed.jsonl"), record)
