"""
Wong Teaser Scanner — operates on the already-computed Buckeye EV table (no extra scraping).

6-point Standard Wong Rules (since 2003 backtest data):
  Favorites: -7.5 to -8.5  → teased to -1.5/-2.5  (crosses key numbers 3 and 7)
  Underdogs: +1.5 to +2.5  → teased to +7.5/+8.5  (crosses key numbers 3 and 7)
  Historical per-leg win rate: ~75.8%

10-point Sweetheart Rules (strictly road-teams-only):
  Underdogs: +1.5 / +2 / +2.5  → teased to +11.5–+12.5 (crosses 3, 7, 10)
  Favorites: -9.5 / -10 / -10.5 → teased to ~0 / -0.5  (crosses 3, 7, 10)
  Historical per-leg win rate: ~83%

BetBCK NFL Teaser Odds:
  6pt 2-team: -110   6pt 3-team: +160   6pt 4-team: +300   6pt 5-team: +450
  10pt (any): -120, ties lose

Priority boosts: road team + game total ≤ 49
"""

import re
import itertools
import logging
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ── Configurable defaults ─────────────────────────────────────────────────────
MIN_PINNACLE_LIMIT  = 2000     # Both/all legs must meet this limit
EV_FLAG_6PT         = 2.5      # Flag combos above this EV% (6pt)
EV_FLAG_10PT        = 2.0      # Flag combos above this EV% (10pt)
WONG_6PT_WIN_RATE   = 0.758    # Historical qualifying-leg win rate (6pt)
WONG_10PT_WIN_RATE  = 0.83     # Consensus backtest win rate (10pt)

TEASER_ODDS_6PT  = {2: -110, 3: 160, 4: 300, 5: 450}  # American
TEASER_ODDS_10PT = {2: -120, 3: -120}                  # -120 flat, ties lose

# 6pt qualifying line ranges
WONG_FAV_MIN, WONG_FAV_MAX = -8.5, -7.5   # favorite side
WONG_DOG_MIN, WONG_DOG_MAX =  1.5,  2.5   # underdog side

# 10pt qualifying lines (exact values only)
TEN_PT_DOG_LINES = {1.5, 2.0, 2.5}
TEN_PT_FAV_LINES = {-9.5, -10.0, -10.5}

NFL_KEYWORDS = {'nfl', 'national football league'}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _american_to_decimal(american: int) -> float:
    if american < 0:
        return 1.0 + 100.0 / abs(american)
    return 1.0 + american / 100.0


def _is_nfl(row: Dict) -> bool:
    league = (row.get('league') or '').lower()
    return any(kw in league for kw in NFL_KEYWORDS)


def _parse_spread_line(bet: str) -> Optional[float]:
    """Extract trailing numeric line from 'Team Name -7.5' → -7.5"""
    m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*$', bet.strip())
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _parse_team_from_bet(bet: str) -> str:
    """Remove trailing line value to get team name."""
    m = re.match(r'^(.+?)\s+[+-]?\d+(?:\.\d+)?\s*$', bet.strip())
    return m.group(1).strip() if m else bet.strip()


def _is_road_team(bet: str, matchup: str) -> Optional[bool]:
    """
    Pinnacle convention: matchup = 'Home vs Away'.
    Returns True  if team is the AWAY (road) team.
    Returns False if team is the HOME team.
    Returns None  if undetermined.
    """
    if ' vs ' not in matchup:
        return None
    home_raw, away_raw = matchup.split(' vs ', 1)
    home_lc = home_raw.strip().lower()
    away_lc = away_raw.strip().lower()
    team_lc = _parse_team_from_bet(bet).lower()
    # Substring matching to handle abbreviations
    if team_lc == away_lc or away_lc.startswith(team_lc) or team_lc.startswith(away_lc):
        return True
    if team_lc == home_lc or home_lc.startswith(team_lc) or team_lc.startswith(home_lc):
        return False
    return None


def _get_game_total(event_id: str, bets_by_event: Dict[str, List[Dict]]) -> Optional[float]:
    for row in bets_by_event.get(str(event_id), []):
        if row.get('bet_type') == 'Total' and row.get('period', 'FG') in ('FG', '', None):
            m = re.search(r'(\d+(?:\.\d+)?)', row.get('bet', ''))
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
    return None


def _teaser_ev_pct(n_teams: int, win_rate: float, american_odds: int) -> float:
    decimal = _american_to_decimal(american_odds)
    return ((win_rate ** n_teams) * decimal - 1) * 100


def _break_even_rate(n_teams: int, american_odds: int) -> float:
    decimal = _american_to_decimal(american_odds)
    return (1.0 / decimal) ** (1.0 / n_teams)


def _fmt_odds(american: int) -> str:
    return f"+{american}" if american > 0 else str(american)


# ── Combo generator ───────────────────────────────────────────────────────────

def _generate_combos(
    legs: List[Dict],
    odds_table: Dict[int, int],
    win_rate: float,
    ev_flag: float,
    teaser_type: str,
    min_teams: int,
    max_teams: int,
) -> List[Dict]:
    combos: List[Dict] = []
    for n in range(min_teams, max_teams + 1):
        if n not in odds_table:
            continue
        american = odds_table[n]
        ev_pct = _teaser_ev_pct(n, win_rate, american)
        be_rate = _break_even_rate(n, american)

        for combo_legs in itertools.combinations(legs, n):
            # Each leg must be from a different game
            event_ids = [l['event_id'] for l in combo_legs]
            if len(set(event_ids)) != n:
                continue

            min_limit = min(l['pin_limit'] for l in combo_legs)
            n_priority = sum(1 for l in combo_legs if l.get('priority'))

            combos.append({
                'teaser_type': teaser_type,
                'n_teams': n,
                'book_odds': _fmt_odds(american),
                'win_rate_pct': round(win_rate * 100, 1),
                'combined_prob_pct': round((win_rate ** n) * 100, 1),
                'ev_pct': round(ev_pct, 2),
                'break_even_pct': round(be_rate * 100, 1),
                'flagged': ev_pct >= ev_flag,
                'min_pin_limit': min_limit,
                'priority_score': n_priority,
                'legs': [
                    {
                        'matchup': l['matchup'],
                        'bet': l['bet'],
                        'spread_line': l['spread_line'],
                        'teased_line': l['teased_line'],
                        'pin_nvp': l['pin_nvp'],
                        'pin_limit': l['pin_limit'],
                        'is_road': l['is_road'],
                        'game_total': l['game_total'],
                        'low_total': l['low_total'],
                        'start_time': l['start_time'],
                        'league': l['league'],
                    }
                    for l in combo_legs
                ],
            })
    return combos


# ── Main entry point ──────────────────────────────────────────────────────────

def calculate_wong_teasers(
    all_bets: List[Dict],
    min_pin_limit: int = MIN_PINNACLE_LIMIT,
    ev_flag_6pt: float = EV_FLAG_6PT,
    ev_flag_10pt: float = EV_FLAG_10PT,
) -> Dict[str, Any]:
    """
    Scan the Buckeye EV table for +EV Wong teaser combinations.
    Input: flat list of bet dicts from calculate_ev_table_async (no extra scraping).
    Output: dict with qualifying legs, combo lists, break-even analysis.
    """
    # Index all rows by event_id for fast game-total lookup
    bets_by_event: Dict[str, List[Dict]] = {}
    for row in all_bets:
        eid = str(row.get('event_id', ''))
        bets_by_event.setdefault(eid, []).append(row)

    legs_6pt: List[Dict] = []
    legs_10pt: List[Dict] = []

    for row in all_bets:
        if row.get('bet_type') != 'Spread':
            continue
        if row.get('period', 'FG') not in ('FG', '', None):
            continue  # Full-game spreads only
        if not _is_nfl(row):
            continue

        pin_limit = row.get('pinnacle_limit') or 0
        try:
            pin_limit = float(pin_limit)
        except (TypeError, ValueError):
            pin_limit = 0

        if pin_limit < min_pin_limit:
            continue

        spread_line = _parse_spread_line(row.get('bet', ''))
        if spread_line is None:
            continue

        matchup = row.get('matchup', '')
        is_road = _is_road_team(row.get('bet', ''), matchup)
        game_total = _get_game_total(row.get('event_id', ''), bets_by_event)
        low_total = game_total is not None and game_total <= 49.0

        leg_base = {
            'matchup': matchup,
            'bet': row.get('bet', ''),
            'spread_line': spread_line,
            'pin_nvp': row.get('pinnacle_nvp', ''),
            'pin_limit': int(pin_limit),
            'is_road': is_road,
            'game_total': game_total,
            'low_total': low_total,
            'start_time': row.get('start_time', ''),
            'event_id': str(row.get('event_id', '')),
            'league': row.get('league', ''),
        }

        # ── 6pt qualification ──────────────────────────────────────────────
        is_fav_6pt = WONG_FAV_MIN <= spread_line <= WONG_FAV_MAX
        is_dog_6pt = WONG_DOG_MIN <= spread_line <= WONG_DOG_MAX
        if is_fav_6pt or is_dog_6pt:
            # 6pt tease always adds 6 to the spread (more points for both sides)
            teased = round(spread_line + 6.0, 1)   # -8 → -2 (fav); +2 → +8 (dog)
            role = 'favorite' if spread_line < 0 else 'underdog'
            priority = bool(is_road) and low_total
            legs_6pt.append({**leg_base, 'teased_line': teased, 'role': role, 'priority': priority})

        # ── 10pt qualification ────────────────────────────────────────────
        is_dog_10pt = spread_line in TEN_PT_DOG_LINES
        is_fav_10pt = spread_line in TEN_PT_FAV_LINES
        if (is_dog_10pt or is_fav_10pt) and is_road is True:
            if spread_line < 0:
                teased = round(spread_line + 10.0, 1)
                role = 'favorite'
            else:
                teased = round(spread_line + 10.0, 1)
                role = 'underdog'
            priority = low_total
            legs_10pt.append({**leg_base, 'teased_line': teased, 'role': role, 'priority': priority})

    logger.info(f"[WONG] {len(legs_6pt)} qualifying 6pt legs, {len(legs_10pt)} qualifying 10pt legs (NFL, pin_limit≥{min_pin_limit})")

    combos_6pt = _generate_combos(
        legs_6pt, TEASER_ODDS_6PT, WONG_6PT_WIN_RATE, ev_flag_6pt,
        teaser_type='6pt', min_teams=2, max_teams=5,
    )
    combos_10pt = _generate_combos(
        legs_10pt, TEASER_ODDS_10PT, WONG_10PT_WIN_RATE, ev_flag_10pt,
        teaser_type='10pt', min_teams=3, max_teams=3,
    )

    # Sort: priority first, then EV desc
    combos_6pt.sort(key=lambda x: (-x['priority_score'], -x['ev_pct']))
    combos_10pt.sort(key=lambda x: (-x['priority_score'], -x['ev_pct']))

    # ── Break-even analysis table ──────────────────────────────────────────
    breakeven = []
    for n, odds in TEASER_ODDS_6PT.items():
        be = _break_even_rate(n, odds)
        ev = _teaser_ev_pct(n, WONG_6PT_WIN_RATE, odds)
        breakeven.append({
            'type': '6pt', 'teams': n,
            'book_odds': _fmt_odds(odds),
            'break_even_pct': round(be * 100, 2),
            'historical_rate_pct': round(WONG_6PT_WIN_RATE * 100, 1),
            'ev_at_historical_pct': round(ev, 2),
            'profitable': ev > 0,
        })
    for n, odds in sorted(set(TEASER_ODDS_10PT.items())):
        be = _break_even_rate(n, odds)
        ev = _teaser_ev_pct(n, WONG_10PT_WIN_RATE, odds)
        breakeven.append({
            'type': '10pt', 'teams': n,
            'book_odds': _fmt_odds(odds),
            'break_even_pct': round(be * 100, 2),
            'historical_rate_pct': round(WONG_10PT_WIN_RATE * 100, 1),
            'ev_at_historical_pct': round(ev, 2),
            'profitable': ev > 0,
        })

    return {
        'qualifying_legs_6pt': len(legs_6pt),
        'qualifying_legs_10pt': len(legs_10pt),
        'legs_6pt': [
            {k: v for k, v in l.items() if k != 'priority'}
            for l in legs_6pt
        ],
        'legs_10pt': [
            {k: v for k, v in l.items() if k != 'priority'}
            for l in legs_10pt
        ],
        'combos_6pt': combos_6pt[:60],
        'combos_10pt': combos_10pt[:20],
        'breakeven': breakeven,
        'config': {
            'win_rate_6pt_pct': round(WONG_6PT_WIN_RATE * 100, 1),
            'win_rate_10pt_pct': round(WONG_10PT_WIN_RATE * 100, 1),
            'min_pin_limit': min_pin_limit,
            'ev_flag_6pt': ev_flag_6pt,
            'ev_flag_10pt': ev_flag_10pt,
            'teaser_type': 'sides only, no totals (NFL full-game spreads)',
        },
    }
