"""
EV calculation for N-way outright winner markets (EPL, La Liga, NBA champ, etc.)

How it works:
  1. For each reference book (FD/DK/MGM), devig the N-way field by normalising
     implied probabilities across ALL competitors in the market so they sum to 1.
  2. Consensus fair probability = average of devigged probs across available books.
  3. EV% = (fair_prob × betbck_decimal − 1) × 100
  4. Sort by EV%, descending.

No arb detection: true arb on N-way outright requires betting all sides; we leave
that as a manual check for the user.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)


# ── Shared odds utilities (mirrors futures_ev.py to avoid circular imports) ──

def _american_to_decimal(american: int) -> float:
    if american > 0:
        return 1.0 + american / 100.0
    return 1.0 + 100.0 / abs(american)


def _decimal_to_american(decimal: float) -> int:
    if decimal >= 2.0:
        return int(round((decimal - 1.0) * 100))
    return int(round(-100.0 / (decimal - 1.0)))


def _fmt_american(amer: Optional[int]) -> str:
    if amer is None:
        return "N/A"
    return f"+{amer}" if amer > 0 else str(amer)


# ── Canonical team name (reuse the same logic as futures_ev.py) ─────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


# Shared alias table — keep in sync with futures_ev._ALIASES
_ALIASES: dict[str, str] = {
    # EPL
    "man city": "manchester city",
    "man utd": "manchester united",
    "man united": "manchester united",
    "brighton": "brighton & hove albion",
    "brighton and hove albion": "brighton & hove albion",
    "brighton hove albion": "brighton & hove albion",
    "afc bournemouth": "bournemouth",
    "brentford fc": "brentford",
    "everton fc": "everton",
    "nottm forest": "nottingham forest",
    "nott'm forest": "nottingham forest",
    "nottm. forest": "nottingham forest",
    "spurs": "tottenham hotspur",
    "tottenham": "tottenham hotspur",
    "wolves": "wolverhampton wanderers",
    "wolverhampton": "wolverhampton wanderers",
    "west ham": "west ham united",
    "newcastle": "newcastle united",
    "crystal palace fc": "crystal palace",
    "leicester": "leicester city",
    "luton": "luton town",
    "sheffield utd": "sheffield united",
    "sheff utd": "sheffield united",
    "ipswich": "ipswich town",
    "hull": "hull city",
    "hull city afc": "hull city",
    # La Liga
    "atletico": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "real madrid cf": "real madrid",
    "fc barcelona": "barcelona",
    "real sociedad": "real sociedad",
    "real betis": "real betis",
    # Serie A
    "inter milan": "inter",
    "internazionale": "inter",
    "ac milan": "milan",
    "as roma": "roma",
    "ss lazio": "lazio",
    "ssc napoli": "napoli",
    "atalanta bc": "atalanta",
    # Bundesliga
    "fc bayern": "bayern munich",
    "fc bayern munich": "bayern munich",
    "borussia dortmund": "dortmund",
    "rb leipzig": "leipzig",
    "bayer leverkusen": "leverkusen",
    # Ligue 1
    "paris saint-germain": "psg",
    "paris saint germain": "psg",
    "paris sg": "psg",
    # MLS / other
    "nycfc": "new york city fc",
    "nyrb": "new york red bulls",
}


def _canonical(name: str) -> str:
    # Remove parenthetical suffixes e.g. "(FL)" → "FL"
    name = re.sub(r"\s*\(([^)]*)\)\s*$", r" \1", name)
    n = _norm(name)
    return _ALIASES.get(n, n)


# ── BetBCK outright parsing ──────────────────────────────────────────────────

# Markers that identify an outright-winner row in BetBCK
_OUTRIGHT_AWAY_RE = re.compile(
    r"(outright|win\s+outright|to\s+win|winner|league\s+winner|champion)",
    re.IGNORECASE,
)


def parse_betbck_outright_winners(
    betbck_games: list[dict],
    market_id: str,
    sport: str,
) -> list[dict]:
    """Convert raw BetBCK game dicts to a flat list of outright winner bets.

    BetBCK outright format (confirmed from live inspection):
      home_team = "Arsenal"
      away_team = "TO WIN OUTRIGHT"   ← varies; matched by _OUTRIGHT_AWAY_RE
      odds.site_top_team_moneyline_american = "+150"

    Each output record:
      {team, sport, direction='winner', line=0, american_odds, book='Buckeye'}
    """
    records: list[dict] = []
    seen: set[str] = set()

    for game in betbck_games:
        home: str = game.get("betbck_site_home_team", "")
        away: str = game.get("betbck_site_away_team", "")
        odds: dict = game.get("betbck_site_odds", {})

        if not _OUTRIGHT_AWAY_RE.search(away):
            continue

        team = home.strip()
        if not team:
            continue

        raw_ml = odds.get("site_top_team_moneyline_american")
        if raw_ml is None:
            logger.debug("[BETBCK-OUT] No moneyline for %r — skipping", team)
            continue

        try:
            ml = int(str(raw_ml).replace("+", "").strip())
        except (TypeError, ValueError):
            continue

        key = _canonical(team)
        if key in seen:
            continue
        seen.add(key)

        records.append({
            "team":          team,
            "sport":         sport,
            "market_id":     market_id,
            "direction":     "winner",
            "line":          0.0,
            "american_odds": ml,
            "book":          "Buckeye",
        })

    logger.info("[BETBCK-OUT] %s: %d outright records parsed", market_id, len(records))
    return records


# ── FanDuel outright parsing ─────────────────────────────────────────────────

def parse_fd_outright_page(
    data: dict,
    sport: str,
    market_id: str,
    market_type_kw: str = "WINNER",
) -> list[dict]:
    """Parse a FD content-managed-page for outright winner markets.

    Unlike win totals, outright runners have plain team names (no "Over X Wins" pattern).
    We match any market whose marketType contains market_type_kw (default: "WINNER").
    """
    markets = data.get("attachments", {}).get("markets", {})
    results: list[dict] = []

    for mid, m in markets.items():
        mt: str = m.get("marketType", "")
        if market_type_kw.upper() not in mt.upper():
            continue
        # Exclude win-total-style markets that also contain "WINNER" in the type
        if "SEASON_WINS" in mt.upper() or "WIN_TOTAL" in mt.upper():
            continue

        for runner in m.get("runners", []):
            team: str = runner.get("runnerName", "").strip()
            if not team:
                continue
            amer = (
                runner.get("winRunnerOdds", {})
                .get("americanDisplayOdds", {})
                .get("americanOdds")
            )
            if amer is None:
                continue
            results.append({
                "team":          team,
                "sport":         sport,
                "market_id":     market_id,
                "direction":     "winner",
                "line":          0.0,
                "american_odds": int(amer),
                "market_type":   mt,
                "book":          "FanDuel",
            })

    # Deduplicate by canonical team name (keep first = lowest overround)
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in results:
        k = _canonical(r["team"])
        if k not in seen:
            deduped.append(r)
            seen.add(k)

    logger.info("[FD-OUT] %s: %d outright records", market_id, len(deduped))
    return deduped


# ── DraftKings outright parsing ──────────────────────────────────────────────

def parse_dk_outright_response(data: dict | list, sport: str, market_id: str, market_kw: str = "Winner") -> list[dict]:
    """Parse a DK nash/eventgroup JSON response for outright winner markets."""
    results: list[dict] = []

    def _walk(obj):
        if isinstance(obj, dict):
            # Look for offer groups or market names
            name = obj.get("name", "") or obj.get("label", "") or obj.get("marketName", "")
            if market_kw.lower() in name.lower():
                # Try to extract outcomes
                for key in ("outcomes", "runners", "selections", "offerOutcomes"):
                    outs = obj.get(key, [])
                    if outs:
                        for out in outs:
                            if isinstance(out, dict):
                                label = out.get("label") or out.get("name") or out.get("participant", {}).get("name", "")
                                odds_val = out.get("oddsAmerican") or out.get("americanOdds") or out.get("odds")
                                if label and odds_val is not None:
                                    try:
                                        results.append({
                                            "team":          str(label).strip(),
                                            "sport":         sport,
                                            "market_id":     market_id,
                                            "direction":     "winner",
                                            "line":          0.0,
                                            "american_odds": int(str(odds_val).replace("+", "")),
                                            "book":          "DraftKings",
                                        })
                                    except (ValueError, TypeError):
                                        pass
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)

    # Deduplicate
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in results:
        k = _canonical(r["team"])
        if k not in seen:
            deduped.append(r)
            seen.add(k)

    logger.info("[DK-OUT] %s: %d outright records", market_id, len(deduped))
    return deduped


# ── BetMGM outright parsing ───────────────────────────────────────────────────

def parse_mgm_outright_response(data: dict | list, sport: str, market_id: str, game_kw: str = "outright") -> list[dict]:
    """Parse BetMGM CDS fixture-view for outright winner markets.

    Game name format: "Arsenal: To win outright" / "League winner: Arsenal"
    Results have a single outcome per team (no Over/Under).
    """
    results: list[dict] = []

    def _get_games(obj):
        if isinstance(obj, dict):
            games = obj.get("games", [])
            if games:
                return games
            fixture = obj.get("fixture", {})
            if isinstance(fixture, dict):
                return fixture.get("games", [])
        return []

    games = _get_games(data)
    if not games and isinstance(data, list):
        games = data

    for game in games:
        if not isinstance(game, dict):
            continue
        game_name = (game.get("name") or {}).get("value", "")
        if game_kw.lower() not in game_name.lower():
            continue

        for result in game.get("results", []):
            if not isinstance(result, dict):
                continue
            r_name = (result.get("name") or {}).get("value", "")
            amer = result.get("americanOdds")
            if amer is None:
                continue
            try:
                amer_int = int(amer)
            except (TypeError, ValueError):
                continue

            # Team name: prefer result name, fall back to game name before ":"
            team = r_name.strip() if r_name else game_name.split(":")[0].strip()
            if not team:
                continue

            results.append({
                "team":          team,
                "sport":         sport,
                "market_id":     market_id,
                "direction":     "winner",
                "line":          0.0,
                "american_odds": amer_int,
                "book":          "BetMGM",
            })

    # Deduplicate
    seen: set[str] = set()
    deduped: list[dict] = []
    for r in results:
        k = _canonical(r["team"])
        if k not in seen:
            deduped.append(r)
            seen.add(k)

    logger.info("[MGM-OUT] %s: %d outright records", market_id, len(deduped))
    return deduped


# ── EV calculation ────────────────────────────────────────────────────────────

def _build_book_index(lines: list[dict]) -> dict[str, int]:
    """Build {canonical_team → american_odds} for one book's outright lines."""
    idx: dict[str, int] = {}
    for rec in lines:
        key = _canonical(rec["team"])
        if key not in idx:
            idx[key] = rec["american_odds"]
    return idx


def _devig_book(book_idx: dict[str, int]) -> dict[str, float]:
    """Normalise implied probs across all teams to remove overround.

    Returns {canonical_team → fair_probability}.
    """
    impl: dict[str, float] = {}
    for team, amer in book_idx.items():
        try:
            dec = _american_to_decimal(amer)
            impl[team] = 1.0 / dec
        except (ZeroDivisionError, ValueError):
            pass

    total = sum(impl.values())
    if total <= 0:
        return {}
    return {t: p / total for t, p in impl.items()}


def calculate_outright_ev(
    betbck_lines: list[dict],
    fd_lines:     list[dict],
    dk_lines:     list[dict],
    mgm_lines:    list[dict],
    market_id:    str,
    sport:        str,
) -> list[dict]:
    """Calculate EV for each BetBCK outright winner bet vs FD/DK/MGM consensus.

    Returns a list of dicts ready for the frontend.
    """
    # Build indices
    bck_idx = _build_book_index(betbck_lines)
    fd_idx  = _build_book_index(fd_lines)
    dk_idx  = _build_book_index(dk_lines)
    mgm_idx = _build_book_index(mgm_lines)

    # Devig each book across its full field
    fd_fair  = _devig_book(fd_idx)  if fd_idx  else {}
    dk_fair  = _devig_book(dk_idx)  if dk_idx  else {}
    mgm_fair = _devig_book(mgm_idx) if mgm_idx else {}

    results: list[dict] = []

    for team_raw, bck_amer in bck_idx.items():
        canon = team_raw  # already canonical from index
        bck_dec = _american_to_decimal(bck_amer)

        # Collect per-book EV and fair probs
        book_evs: dict[str, float] = {}
        book_probs: dict[str, float] = {}

        for book_label, fair_dict in [("FD", fd_fair), ("DK", dk_fair), ("MGM", mgm_fair)]:
            if canon in fair_dict:
                p = fair_dict[canon]
                book_probs[book_label] = p
                book_evs[book_label] = (p * bck_dec - 1.0) * 100.0

        if not book_probs:
            logger.debug("[EV-OUT] No reference for %r", canon)
            continue

        # Consensus fair probability = equal-weight average across available books
        consensus_p = sum(book_probs.values()) / len(book_probs)
        consensus_ev = (consensus_p * bck_dec - 1.0) * 100.0
        consensus_fair_amer = _decimal_to_american(1.0 / consensus_p) if consensus_p > 0 else None

        signal_count = len(book_probs)

        fd_amer  = fd_idx.get(canon)
        dk_amer  = dk_idx.get(canon)
        mgm_amer = mgm_idx.get(canon)

        results.append({
            "team":          team_raw,
            "sport":         sport,
            "market_id":     market_id,
            "direction":     "winner",
            "line":          None,
            "betbck_odds":   _fmt_american(bck_amer),
            "fd_odds":       _fmt_american(fd_amer),
            "dk_odds":       _fmt_american(dk_amer),
            "mgm_odds":      _fmt_american(mgm_amer),
            "consensus_fair": _fmt_american(consensus_fair_amer),
            "ev":            f"{consensus_ev:.1f}%",
            "ev_float":      round(consensus_ev, 2),
            "signal_count":  signal_count,
            "per_book_ev":   {b: round(v, 2) for b, v in book_evs.items()},
            "sharp_books":   "+".join(book_probs.keys()),
            "is_arb":        False,  # Not applicable for outrights
            "all_book_odds": {
                "Buckeye": {"winner": _fmt_american(bck_amer)},
                "FD":      {"winner": _fmt_american(fd_amer)},
                "DK":      {"winner": _fmt_american(dk_amer)},
                "MGM":     {"winner": _fmt_american(mgm_amer)},
            },
        })

    results.sort(key=lambda r: r["ev_float"], reverse=True)

    pos_ev = sum(1 for r in results if r["ev_float"] > 0)
    logger.info(
        "[EV-OUT] %s: %d total | %d +EV",
        market_id, len(results), pos_ev,
    )
    return results
