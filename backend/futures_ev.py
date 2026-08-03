"""Calculate EV and detect arbitrage for season win totals.

Key design choices driven by real-book observations:
  • BetBCK shows Over X.5 and Under Y.5 as INDEPENDENT bets — the over line
    and the under line can differ for the same team.  We parse each side as a
    standalone record instead of requiring a matched pair.
  • FanDuel carries one standard line per team; DraftKings carries alternates
    at many lines.  A BetBCK bet at line X may only have a DK alternate at X
    (FD may have a different line entirely) — that's fine, we use whatever
    reference is available.
  • EV is computed per individual bet: find the same (team, line, direction)
    in FD/DK, devig that book's OVER+UNDER pair at that line to get fair
    probability, then EV% = (fair_prob × betbck_decimal − 1) × 100.
  • Arbitrage: for each BetBCK Over X.5 bet, check whether any reference
    book's Under X.5 makes the combined implied probability < 1.  And vice
    versa for BetBCK Unders.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Odds utilities
# ---------------------------------------------------------------------------

def american_to_decimal(american: int) -> float:
    if american > 0:
        return 1.0 + american / 100.0
    return 1.0 + 100.0 / abs(american)


def decimal_to_american(decimal: float) -> int:
    if decimal >= 2.0:
        return int(round((decimal - 1.0) * 100))
    return int(round(-100.0 / (decimal - 1.0)))


def devig_pair(over_dec: float, under_dec: float) -> tuple[float, float]:
    """Remove vig from an Over/Under pair; return (p_over, p_under)."""
    p_over  = 1.0 / over_dec
    p_under = 1.0 / under_dec
    total   = p_over + p_under
    return p_over / total, p_under / total


def ev_pct(fair_prob: float, betbck_decimal: float) -> float:
    """EV% relative to a 1-unit stake."""
    return (fair_prob * betbck_decimal - 1.0) * 100.0


def fmt_american(amer: Optional[int]) -> str:
    if amer is None:
        return "N/A"
    return f"+{amer}" if amer > 0 else str(amer)

# ---------------------------------------------------------------------------
# BetBCK win-total parsing
# ---------------------------------------------------------------------------

# BetBCK encodes each bet in the team-name field:
#   "Missouri Over 6.5"      → over 6.5
#   "Missouri Under 3.5 Wins" → under 3.5
#   "Iowa State Over 5.5 Wins" → over 5.5
# The over and under entries for the same team CAN be at different lines.
_BETBCK_BET_RE = re.compile(
    r"^(?P<team>.+?)\s+(?P<dir>Over|Under)\s+(?P<line>[\d.]+)",
    re.IGNORECASE,
)

# Spread-column format: [{line: float, odds: int}, ...]
# Sometimes BetBCK encodes the line only in the spreads column (no direction in name).
_DIRECTION_IN_SPREAD_RE = re.compile(r"[ou]", re.IGNORECASE)


def _extract_bet_from_name(name: str) -> Optional[tuple[str, str, float]]:
    """Return (team, 'over'|'under', line) if the name encodes a win-total bet."""
    m = _BETBCK_BET_RE.match(name)
    if m:
        return m.group("team").strip(), m.group("dir").lower(), float(m.group("line"))
    return None


def parse_betbck_win_totals(betbck_games: list[dict]) -> list[dict]:
    """Convert raw BetBCK game dicts to a flat list of individual win-total bets.

    BetBCK can show Over X.5 and Under Y.5 for the same team as separate rows,
    potentially at DIFFERENT lines (X ≠ Y).  We therefore parse EACH side as an
    independent record rather than requiring a matched pair.

    Each output record:
        {team, sport, line, direction ('over'|'under'), american_odds, book, _raw}
    """
    records: list[dict] = []

    for game in betbck_games:
        home: str = game.get("betbck_site_home_team", "")
        away: str = game.get("betbck_site_away_team", "")
        odds: dict = game.get("betbck_site_odds", {})
        sport: str = game.get("sport", "")

        top_ml  = odds.get("site_top_team_moneyline_american")
        bot_ml  = odds.get("site_bottom_team_moneyline_american")

        # ── Try to extract direction + line from each name independently ──────
        top_bet = _extract_bet_from_name(home)
        bot_bet = _extract_bet_from_name(away)

        if top_bet and top_ml is not None:
            t_team, t_dir, t_line = top_bet
            records.append({
                "team":          t_team,
                "sport":         sport,
                "line":          t_line,
                "direction":     t_dir,
                "american_odds": int(top_ml),
                "book":          "BetBCK",
                "_raw":          home,
            })

        if bot_bet and bot_ml is not None:
            b_team, b_dir, b_line = bot_bet
            records.append({
                "team":          b_team,
                "sport":         sport,
                "line":          b_line,
                "direction":     b_dir,
                "american_odds": int(bot_ml),
                "book":          "BetBCK",
                "_raw":          away,
            })

        if top_bet or bot_bet:
            continue  # handled above

        # ── Fallback: direction not in name → infer from spreads column ───────
        # top row = over, bottom row = under; get line from spreads
        top_spreads = odds.get("site_top_team_spreads", [])
        line: Optional[float] = None
        if top_spreads:
            raw_line = (top_spreads[0].get("line") or top_spreads[0].get("spread"))
            if raw_line is not None:
                try:
                    line = abs(float(raw_line))
                except (TypeError, ValueError):
                    pass

        if line is None:
            logger.debug("[BETBCK] No line found for: %s / %s", home, away)
            continue

        # Determine team name: use whichever name doesn't contain "Wins"/"Season"
        team = home
        if any(w in home.lower() for w in ("wins", "season")):
            team = away
        elif any(w in away.lower() for w in ("wins", "season")):
            team = home

        if top_ml is not None:
            records.append({
                "team": team, "sport": sport, "line": line,
                "direction": "over", "american_odds": int(top_ml),
                "book": "BetBCK", "_raw": home,
            })
        if bot_ml is not None:
            records.append({
                "team": team, "sport": sport, "line": line,
                "direction": "under", "american_odds": int(bot_ml),
                "book": "BetBCK", "_raw": away,
            })

    # Deduplicate (same team/line/direction may appear from overlapping checkboxes)
    seen: set = set()
    deduped: list[dict] = []
    for r in records:
        key = (_canonical(r["team"]), r["line"], r["direction"])
        if key not in seen:
            deduped.append(r)
            seen.add(key)

    logger.info("[BETBCK] Parsed %d individual win-total bets", len(deduped))
    return deduped

# ---------------------------------------------------------------------------
# Team-name normalisation
# ---------------------------------------------------------------------------

_STRIP_RE  = re.compile(r"[^a-z0-9 ]")
_SPACES_RE = re.compile(r"\s+")

_ALIASES: dict[str, str] = {
    "washington football team":    "washington commanders",
    "washington redskins":         "washington commanders",
    "oakland raiders":             "las vegas raiders",
    "st louis rams":               "los angeles rams",
    "san diego chargers":          "los angeles chargers",
    "n illinois":                  "northern illinois",
    "n. illinois":                 "northern illinois",
    "northern ill":                "northern illinois",
    "new mexico st":               "new mexico state",
    "new mexico st.":              "new mexico state",
    "iowa st":                     "iowa state",
    "iowa st.":                    "iowa state",
    "n carolina st":               "nc state",
    "north carolina st":           "nc state",
    "north carolina state":        "nc state",
}


def _norm(name: str) -> str:
    n = _STRIP_RE.sub("", name.lower())
    return _SPACES_RE.sub(" ", n).strip()


def _canonical(name: str) -> str:
    n = _norm(name)
    return _ALIASES.get(n, n)

# ---------------------------------------------------------------------------
# Reference book index
# ---------------------------------------------------------------------------

def build_book_index(
    lines: list[dict],
) -> dict[tuple[str, float], dict[str, dict[str, int]]]:
    """Return {(canonical_team, line) → {book → {direction → american_odds}}}.

    DraftKings returns alternates (many lines per team); FanDuel returns one
    standard line.  The same structure works for both.
    """
    idx: dict = defaultdict(lambda: defaultdict(dict))
    for entry in lines:
        key   = (_canonical(entry["team"]), float(entry["line"]))
        book  = entry["book"]
        dirn  = entry["direction"]   # 'over' | 'under'
        amer  = entry["american_odds"]
        idx[key][book][dirn] = amer
    return dict(idx)

# ---------------------------------------------------------------------------
# Consensus fair-odds lookup
# ---------------------------------------------------------------------------

def _get_fair_prob(
    canon_team: str,
    line: float,
    direction: str,
    fd_idx:  dict,
    dk_idx:  dict,
) -> tuple[Optional[float], list[str], dict[str, Optional[int]]]:
    """Return (fair_probability, sharp_books_used, {fd_amer, dk_amer}).

    We devig each sharp book's OVER+UNDER pair at exactly this line, then
    average across available books to get a consensus fair probability.
    """
    fd_key   = (canon_team, line)
    fd_entry = fd_idx.get(fd_key, {})
    dk_entry = dk_idx.get(fd_key, {})

    fair_probs: list[float] = []
    sharp_books: list[str]  = []

    fd_over  = fd_entry.get("FanDuel", {}).get("over")
    fd_under = fd_entry.get("FanDuel", {}).get("under")

    dk_over = dk_under = None
    for book_sides in dk_entry.values():
        if book_sides.get("over") and book_sides.get("under"):
            dk_over  = book_sides["over"]
            dk_under = book_sides["under"]
            break

    if fd_over and fd_under:
        p_over, p_under = devig_pair(
            american_to_decimal(fd_over), american_to_decimal(fd_under)
        )
        fair_probs.append(p_over if direction == "over" else p_under)
        sharp_books.append("FD")

    if dk_over and dk_under:
        p_over, p_under = devig_pair(
            american_to_decimal(dk_over), american_to_decimal(dk_under)
        )
        fair_probs.append(p_over if direction == "over" else p_under)
        sharp_books.append("DK")

    if not fair_probs:
        return None, [], {"fd_amer": None, "dk_amer": None}

    consensus = sum(fair_probs) / len(fair_probs)
    ref_odds = {
        "fd_amer":  fd_over  if direction == "over" else fd_under,
        "dk_amer":  dk_over  if direction == "over" else dk_under,
    }
    return consensus, sharp_books, ref_odds

# ---------------------------------------------------------------------------
# Arbitrage check
# ---------------------------------------------------------------------------

def _check_arb(
    betbck_amer: int,
    opposite_direction: str,
    canon_team: str,
    line: float,
    fd_idx: dict,
    dk_idx: dict,
) -> tuple[bool, Optional[int], str]:
    """Check whether BetBCK + reference book opposite side = arb.

    Returns (is_arb, best_opposite_amer, book_name).
    Arb condition: 1/decimal(betbck) + 1/decimal(ref_opposite) < 1.0
    """
    fd_key   = (canon_team, line)
    fd_entry = fd_idx.get(fd_key, {})
    dk_entry = dk_idx.get(fd_key, {})

    candidates: list[tuple[int, str]] = []  # (amer, book_label)

    opp = opposite_direction  # 'over' or 'under'

    fd_opp = fd_entry.get("FanDuel", {}).get(opp)
    if fd_opp is not None:
        candidates.append((fd_opp, "FD"))

    for book_sides in dk_entry.values():
        dk_opp = book_sides.get(opp)
        if dk_opp is not None:
            candidates.append((dk_opp, "DK"))
            break

    if not candidates:
        return False, None, ""

    # Find the best (highest payout) opposite-side odds
    best_opp_amer, best_book = max(candidates, key=lambda x: american_to_decimal(x[0]))

    betbck_dec  = american_to_decimal(betbck_amer)
    opp_dec     = american_to_decimal(best_opp_amer)
    total_impl  = 1.0 / betbck_dec + 1.0 / opp_dec

    if total_impl < 1.0:
        return True, best_opp_amer, best_book

    return False, best_opp_amer, best_book

# ---------------------------------------------------------------------------
# Main EV + arb calculation
# ---------------------------------------------------------------------------

def calculate_futures_ev(
    betbck_lines: list[dict],
    fd_lines: list[dict],
    dk_lines: list[dict],
) -> list[dict]:
    """For each individual BetBCK win-total bet:

      1. Find the same (team, line, direction) in FD/DK.
      2. Devig FD and/or DK to get consensus fair probability.
      3. EV% = (fair_prob × betbck_decimal − 1) × 100.
      4. Check for arbitrage vs the opposite side on FD/DK.

    BetBCK's over and under for the same team may be at different lines —
    each bet is evaluated independently.

    Returns list of result dicts sorted by EV descending (positive first).
    """
    fd_idx = build_book_index(fd_lines)
    dk_idx = build_book_index(dk_lines)

    results: list[dict] = []

    for bet in betbck_lines:
        team       = bet["team"]
        line       = float(bet["line"])
        direction  = bet["direction"]       # 'over' | 'under'
        betbck_amer = bet["american_odds"]
        canon      = _canonical(team)

        fair_prob, sharp_books, ref_odds = _get_fair_prob(
            canon, line, direction, fd_idx, dk_idx
        )

        if fair_prob is None:
            # No sharp-book reference at this exact line — skip
            logger.debug(
                "[EV] No reference for %s %s %.1f (line not in FD/DK alternates)",
                team, direction, line,
            )
            continue

        betbck_dec  = american_to_decimal(betbck_amer)
        ev_val      = ev_pct(fair_prob, betbck_dec)
        fair_amer   = decimal_to_american(1.0 / fair_prob)

        # ── Arb check: BetBCK this side + reference book opposite side ──────
        opp = "under" if direction == "over" else "over"
        is_arb, best_opp_amer, arb_book = _check_arb(
            betbck_amer, opp, canon, line, fd_idx, dk_idx
        )

        arb_roi: Optional[float] = None
        if is_arb and best_opp_amer is not None:
            # Roy: if we bet 1 unit on BetBCK and stake X on the opposite side
            # so both pay the same: minimal guaranteed profit
            betbck_dec_v = american_to_decimal(betbck_amer)
            opp_dec_v    = american_to_decimal(best_opp_amer)
            total_impl   = 1.0 / betbck_dec_v + 1.0 / opp_dec_v
            arb_roi      = round((1.0 / total_impl - 1.0) * 100, 2)  # guaranteed % return

        results.append(
            {
                "team":           team,
                "line":           line,
                "direction":      direction.capitalize(),
                "betbck_odds":    fmt_american(betbck_amer),
                "fd_odds":        fmt_american(ref_odds.get("fd_amer")),
                "dk_odds":        fmt_american(ref_odds.get("dk_amer")),
                "consensus_fair": fmt_american(fair_amer),
                "ev":             f"{ev_val:.1f}%",
                "ev_float":       round(ev_val, 2),
                "sharp_books":    "+".join(sharp_books),
                "is_arb":         is_arb,
                "arb_book":       arb_book if is_arb else "",
                "arb_opp_odds":   fmt_american(best_opp_amer) if is_arb else "",
                "arb_roi":        arb_roi,
            }
        )

    # Sort: arbs first, then positive EV descending, then all others
    results.sort(
        key=lambda x: (not x["is_arb"], -x["ev_float"])
    )

    pos_ev  = sum(1 for r in results if r["ev_float"] > 0)
    arbs    = sum(1 for r in results if r["is_arb"])
    logger.info(
        "[EV] Results: %d total | %d +EV | %d arb",
        len(results), pos_ev, arbs,
    )
    return results
