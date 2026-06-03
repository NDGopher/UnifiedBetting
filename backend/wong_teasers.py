"""
Wong Teaser Scanner — operates on the already-computed Buckeye EV table (no extra scraping).

6-point Standard Wong Rules (since 2003 backtest data):
  Favorites: -7.5 to -8.5  → teased to -1.5/-2.5  (crosses key numbers 3 and 7)
  Underdogs: +1.5 to +2.5  → teased to +7.5/+8.5
  Historical per-leg win rate: ~75.8%

10-point Sweetheart Rules (road teams only, 3-team at -120 ONLY — no 2-team):
  Underdogs: +1.5 / +2 / +2.5  → teased to +11.5–+12.5 (crosses 3, 7, 10)
  Favorites: -9.5 / -10 / -10.5 → teased to ~0 / -0.5  (crosses 3, 7, 10)
  Historical per-leg win rate: ~83%

BetBCK NFL Teaser Odds:
  6pt 2-team: -110   6pt 3-team: +160   6pt 4-team: +300   6pt 5-team: +450
  10pt 3-team: -120, ties lose

EV Calculation (per combo, NVP-adjusted):
  base_historical    = hist_rate + 0.01  if game_total ≤ 49  else hist_rate
  nvp_implied_prob   = _parse_nvp_prob(pin_nvp)  or 0.50
  projected_leg_prob = base_historical + (0.50 - nvp_implied_prob) * 0.30
    • NVP near -105 (≈51%) → tiny penalty (-0.4pp); NVP near -145 (≈59%) → larger penalty (-2.7pp)
    • Underdogs priced at +120 (≈45%) → bonus (+1.5pp); balanced spread (-110) → -0.3pp
  teaser_win_prob    = product of all projected_leg_probs
  EV% = (teaser_win_prob * decimal_payout - 1) * 100

Priority boost: road team AND game total ≤ 49
Deduplication: one leg per game (highest Pinnacle limit = main line).
"""

import re
import itertools
import logging
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ── Configurable defaults ─────────────────────────────────────────────────────
MIN_PINNACLE_LIMIT  = 2000
EV_FLAG_6PT         = 2.5      # blended EV% threshold for flagging combos
EV_FLAG_10PT        = 2.0
WONG_6PT_WIN_RATE   = 0.758    # historical qualifying-leg win rate (6pt)
WONG_10PT_WIN_RATE  = 0.83     # consensus backtest rate (10pt)

TEASER_ODDS_6PT  = {2: -110, 3: 160, 4: 300, 5: 450}   # American
TEASER_ODDS_10PT = {3: -120}                              # 3-team only, ties lose

# 6pt qualifying line ranges
WONG_FAV_MIN, WONG_FAV_MAX = -8.5, -7.5
WONG_DOG_MIN, WONG_DOG_MAX =  1.5,  2.5

# 10pt qualifying lines (exact values)
TEN_PT_DOG_LINES = {1.5, 2.0, 2.5}
TEN_PT_FAV_LINES = {-9.5, -10.0, -10.5}

NFL_KEYWORDS = {'nfl', 'national football league'}

# CFL team keywords — exclude from betbck direct scan (CFL goes through Pinnacle matching)
CFL_KEYWORDS = {
    'alouettes', 'blue bombers', 'stampeders', 'redblacks', 'elks',
    'roughriders', 'argonauts', 'tiger-cats', 'tigers', 'lions',
    'eskimos', 'ticats',
}

# BetBCK default limit for NFL games that aren't yet matched to Pinnacle
NFL_BETBCK_DEFAULT_LIMIT = 10000


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
    m = re.match(r'^(.+?)\s+[+-]?\d+(?:\.\d+)?\s*$', bet.strip())
    return m.group(1).strip() if m else bet.strip()


def _proj_leg_prob(leg: Dict, historical_rate: float) -> float:
    """
    Per-leg projected win probability (NVP-adjusted).

    base = historical_rate + 0.01 if low total (≤49), else historical_rate
    nvp_p = implied probability of the qualifying spread (from pin_nvp odds)
    result = base + (0.50 - nvp_p) * 0.30

    Rationale: a spread priced near even money (-110 → 52.4%) reflects balanced
    uncertainty — the teaser math works at its historical rate.  A spread priced
    heavily toward one side (e.g. -145 → 59.2%) implies the line has a lot of
    market juice; the teaser is crossing fewer truly uncertain key numbers, so we
    discount slightly.  Conversely, an underdog priced at +120 (implied 45.5%)
    gets a small boost since the market already favours the other side.
    """
    base = (historical_rate + 0.01) if leg.get('low_total') else historical_rate
    nvp_p = _parse_nvp_prob(leg.get('pin_nvp') or '') or 0.50
    return base + (0.50 - nvp_p) * 0.30


def _parse_nvp_prob(pin_nvp: str) -> Optional[float]:
    """
    Convert American odds string (e.g. '-114', '+108') to implied probability [0, 1].
    -114 → 114 / (114+100) = 0.533
    +108 → 100 / (108+100) = 0.481
    """
    if not pin_nvp:
        return None
    try:
        s = str(pin_nvp).strip().replace('+', '')
        val = float(s)
    except (ValueError, TypeError):
        return None
    if val < 0:
        return abs(val) / (abs(val) + 100.0)
    elif val > 0:
        return 100.0 / (val + 100.0)
    return 0.5   # even money


def _is_road_team(bet: str, matchup: str) -> Optional[bool]:
    """Pinnacle convention: matchup = 'Home vs Away'. Returns True if away (road)."""
    if ' vs ' not in matchup:
        return None
    home_raw, away_raw = matchup.split(' vs ', 1)
    home_lc = home_raw.strip().lower()
    away_lc = away_raw.strip().lower()
    team_lc = _parse_team_from_bet(bet).lower()
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


def _teaser_ev_hist(n_teams: int, win_rate: float, american_odds: int) -> float:
    """EV% using flat historical win rate (for the break-even reference table)."""
    decimal = _american_to_decimal(american_odds)
    return ((win_rate ** n_teams) * decimal - 1) * 100


def _combo_ev_blended(
    proj_probs: List[float],
    american_odds: int,
) -> Tuple[float, float]:
    """
    Per-combo EV given pre-computed per-leg projected probabilities.
      teaser_win_prob = product of proj_probs
      EV% = (teaser_win_prob * decimal - 1) * 100
    Returns (ev_pct, teaser_win_prob_pct).
    """
    teaser_win_prob = 1.0
    for p in proj_probs:
        teaser_win_prob *= p
    decimal = _american_to_decimal(american_odds)
    ev_pct = (teaser_win_prob * decimal - 1.0) * 100.0
    return ev_pct, teaser_win_prob * 100.0


def _break_even_rate(n_teams: int, american_odds: int) -> float:
    decimal = _american_to_decimal(american_odds)
    return (1.0 / decimal) ** (1.0 / n_teams)


def _fmt_odds(american: int) -> str:
    return f"+{american}" if american > 0 else str(american)


def _deduplicate_legs(legs: List[Dict]) -> List[Dict]:
    """
    One entry per (event_id, role).
    Among duplicates (alt lines for the same game+side), keep the one with
    the highest Pinnacle limit — that is typically the main line.
    """
    best: Dict[tuple, Dict] = {}
    for leg in legs:
        key = (leg['event_id'], leg['role'])
        if key not in best or leg['pin_limit'] > best[key]['pin_limit']:
            best[key] = leg
    return list(best.values())


def _is_cfl_team(team_name: str) -> bool:
    """Return True if the team name matches a known CFL franchise."""
    tl = team_name.lower()
    return any(kw in tl for kw in CFL_KEYWORDS)


def _scan_betbck_for_nfl(
    betbck_games: List[Dict],
    seen_matchups: set,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Scan raw BetBCK football games directly for Wong qualifying spreads.
    Used when NFL future lines haven't yet been matched to Pinnacle.

    Rules:
    - sport == 'football' only
    - Exclude CFL teams
    - site_top_team_spreads  → away (road) team
    - site_bottom_team_spreads → home team
    - Take the FIRST qualifying spread per team/side (the main line)
    - NVP proxy = BetBCK spread odds; pin_limit = NFL_BETBCK_DEFAULT_LIMIT

    seen_matchups: normalised matchup strings already found via the EV table
                   (avoids adding the same game twice from different sources).
    """
    legs_6pt:  List[Dict] = []
    legs_10pt: List[Dict] = []

    for game in betbck_games:
        if (game.get('sport') or '').lower() != 'football':
            continue

        home_team = (game.get('betbck_site_home_team') or '').strip()
        away_team = (game.get('betbck_site_away_team') or '').strip()
        if not home_team or not away_team:
            continue

        # Skip CFL franchises (they come through Pinnacle matching separately)
        if _is_cfl_team(home_team) or _is_cfl_team(away_team):
            continue

        matchup = f"{home_team} vs {away_team}"
        matchup_norm = matchup.lower()
        if matchup_norm in seen_matchups:
            continue   # already covered by the EV-table scan

        game_id   = str(game.get('betbck_game_id', id(game)))
        start_dt  = str(game.get('event_datetime', ''))
        odds_data = game.get('betbck_site_odds') or {}

        # away team = road = site_top; home team = site_bottom
        team_sides = [
            (away_team, odds_data.get('site_top_team_spreads') or [],    True),
            (home_team, odds_data.get('site_bottom_team_spreads') or [], False),
        ]

        for team, spreads, is_road in team_sides:
            found_6pt  = False
            found_10pt = False

            for entry in spreads:
                try:
                    line     = float(entry['line'])
                    odds_str = str(entry.get('odds', ''))
                except (KeyError, TypeError, ValueError):
                    continue

                line_sign = '+' if line > 0 else ''
                bet_str   = f"{team} {line_sign}{line:g}"

                try:
                    game_total = float(odds_data.get('game_total_line') or 0) or None
                except (TypeError, ValueError):
                    game_total = None
                low_total = game_total is not None and game_total <= 49.0

                leg_base = {
                    'matchup':          matchup,
                    'bet':              bet_str,
                    'spread_line':      line,
                    'pin_nvp':          odds_str,   # BetBCK odds (display only)
                    'pin_limit':        NFL_BETBCK_DEFAULT_LIMIT,
                    'is_road':          is_road,
                    'game_total':       game_total,
                    'low_total':        low_total,
                    'start_time':       start_dt,
                    'event_id':         game_id,
                    'league':           'NFL',
                    'main_line_ev_pct': 0.0,        # no Pinnacle match → baseline
                }

                # 6pt qualification — take first qualifying spread (main line)
                if not found_6pt:
                    is_fav_6pt = WONG_FAV_MIN <= line <= WONG_FAV_MAX
                    is_dog_6pt = WONG_DOG_MIN <= line <= WONG_DOG_MAX
                    if is_fav_6pt or is_dog_6pt:
                        teased   = round(line + 6.0, 1)
                        role     = 'favorite' if line < 0 else 'underdog'
                        priority = bool(is_road) and low_total
                        legs_6pt.append({**leg_base, 'teased_line': teased, 'role': role, 'priority': priority})
                        found_6pt = True

                # 10pt qualification — road teams only, first qualifying spread
                if not found_10pt and is_road:
                    if line in TEN_PT_DOG_LINES or line in TEN_PT_FAV_LINES:
                        teased   = round(line + 10.0, 1)
                        role     = 'favorite' if line < 0 else 'underdog'
                        legs_10pt.append({**leg_base, 'teased_line': teased, 'role': role, 'priority': False})
                        found_10pt = True

                if found_6pt and found_10pt:
                    break

    return legs_6pt, legs_10pt


# ── Combo generator ───────────────────────────────────────────────────────────

def _generate_combos(
    legs: List[Dict],
    odds_table: Dict[int, int],
    historical_rate: float,
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
        be_rate  = _break_even_rate(n, american)
        hist_ev  = _teaser_ev_hist(n, historical_rate, american)

        for combo_legs in itertools.combinations(legs, n):
            # Each leg must be from a different game
            event_ids = [l['event_id'] for l in combo_legs]
            if len(set(event_ids)) != n:
                continue

            min_limit   = min(l['pin_limit'] for l in combo_legs)
            n_priority  = sum(1 for l in combo_legs if l.get('priority'))

            # Per-leg projected probabilities — _proj_leg_prob() applies:
            #   base = hist_rate + 0.01 if low_total, then +/- (0.50 - NVP_p)*0.30
            legs_out = []
            proj_probs = []
            for l in combo_legs:
                proj_p = _proj_leg_prob(l, historical_rate)
                proj_probs.append(proj_p)
                legs_out.append({
                    'matchup':            l['matchup'],
                    'bet':                l['bet'],
                    'spread_line':        l['spread_line'],
                    'teased_line':        l['teased_line'],
                    'pin_nvp':            l['pin_nvp'],
                    'main_line_ev_pct':   l.get('main_line_ev_pct', 0.0),
                    'projected_prob_pct': round(proj_p * 100.0, 2),
                    'pin_limit':          l['pin_limit'],
                    'is_road':            l['is_road'],
                    'game_total':         l['game_total'],
                    'low_total':          l['low_total'],
                    'start_time':         l['start_time'],
                    'league':             l['league'],
                })

            blended_ev, win_prob_blended = _combo_ev_blended(proj_probs, american)
            all_low_total = all(l.get('low_total') for l in combo_legs)

            combos.append({
                'teaser_type':               teaser_type,
                'n_teams':                   n,
                'book_odds':                 _fmt_odds(american),
                'win_rate_hist_pct':         round(historical_rate * 100.0, 1),
                'combined_prob_hist_pct':    round((historical_rate ** n) * 100.0, 1),
                'combined_prob_blended_pct': round(win_prob_blended, 1),
                'ev_hist_pct':               round(hist_ev, 2),
                'ev_blended_pct':            round(blended_ev, 2),
                'ev_pct':                    round(blended_ev, 2),
                'break_even_pct':            round(be_rate * 100.0, 1),
                'flagged':                   blended_ev >= ev_flag,
                'all_low_total':             all_low_total,
                'min_pin_limit':             min_limit,
                'priority_score':            n_priority,
                'legs':                      legs_out,
            })

    # Sort: all-low-total combos first, then by blended EV desc (true per-combo)
    combos.sort(key=lambda x: (not x['all_low_total'], -x['priority_score'], -x['ev_blended_pct']))
    return combos


def _balanced_combos(combos: List[Dict], per_size: int = 15) -> List[Dict]:
    """
    Return up to `per_size` combos per n_teams group, preserving each group's
    internal sort order (all_low_total → priority_score → ev_blended_pct).
    This guarantees 2-team combos are always included even when 5-team combos
    have higher raw EV and would crowd them out of a flat slice.
    """
    from collections import defaultdict
    buckets: dict = defaultdict(list)
    for c in combos:
        buckets[c['n_teams']].append(c)
    result = []
    for n in sorted(buckets):
        result.extend(buckets[n][:per_size])
    return result


# ── Main entry point ──────────────────────────────────────────────────────────

def calculate_wong_teasers(
    all_bets: List[Dict],
    min_pin_limit: int = MIN_PINNACLE_LIMIT,
    ev_flag_6pt: float = EV_FLAG_6PT,
    ev_flag_10pt: float = EV_FLAG_10PT,
    betbck_games: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Scan the Buckeye EV table for +EV Wong teaser combinations.
    Input : flat list of bet dicts from calculate_ev_table_async.
            betbck_games: raw BetBCK game list for scanning unmatched NFL futures.
    Output: dict with qualifying legs, combo lists, break-even analysis.
    """
    # Index all rows by event_id for fast game-total lookup
    bets_by_event: Dict[str, List[Dict]] = {}
    for row in all_bets:
        eid = str(row.get('event_id', ''))
        bets_by_event.setdefault(eid, []).append(row)

    legs_6pt_raw:  List[Dict] = []
    legs_10pt_raw: List[Dict] = []

    for row in all_bets:
        if row.get('bet_type') != 'Spread':
            continue
        if row.get('period', 'FG') not in ('FG', '', None):
            continue
        if not _is_nfl(row):
            continue

        try:
            pin_limit = float(row.get('pinnacle_limit') or 0)
        except (TypeError, ValueError):
            pin_limit = 0.0

        if pin_limit < min_pin_limit:
            continue

        spread_line = _parse_spread_line(row.get('bet', ''))
        if spread_line is None:
            continue

        matchup    = row.get('matchup', '')
        is_road    = _is_road_team(row.get('bet', ''), matchup)
        game_total = _get_game_total(row.get('event_id', ''), bets_by_event)
        low_total  = game_total is not None and game_total <= 49.0

        leg_base = {
            'matchup':         matchup,
            'bet':             row.get('bet', ''),
            'spread_line':     spread_line,
            'pin_nvp':         row.get('pinnacle_nvp', ''),
            'pin_limit':       int(pin_limit),
            'is_road':         is_road,
            'game_total':      game_total,
            'low_total':       low_total,
            'start_time':      row.get('start_time', ''),
            'event_id':        str(row.get('event_id', '')),
            'league':          row.get('league', ''),
            'main_line_ev_pct': float(row.get('ev_pct') or 0.0),
        }

        # ── 6pt qualification ──────────────────────────────────────────────
        is_fav_6pt = WONG_FAV_MIN <= spread_line <= WONG_FAV_MAX
        is_dog_6pt = WONG_DOG_MIN <= spread_line <= WONG_DOG_MAX
        if is_fav_6pt or is_dog_6pt:
            teased   = round(spread_line + 6.0, 1)
            role     = 'favorite' if spread_line < 0 else 'underdog'
            priority = bool(is_road) and low_total
            legs_6pt_raw.append({**leg_base, 'teased_line': teased, 'role': role, 'priority': priority})

        # ── 10pt qualification (road teams only) ──────────────────────────
        is_dog_10pt = spread_line in TEN_PT_DOG_LINES
        is_fav_10pt = spread_line in TEN_PT_FAV_LINES
        if (is_dog_10pt or is_fav_10pt) and is_road is True:
            teased   = round(spread_line + 10.0, 1)
            role     = 'favorite' if spread_line < 0 else 'underdog'
            priority = low_total
            legs_10pt_raw.append({**leg_base, 'teased_line': teased, 'role': role, 'priority': priority})

    # Deduplicate EV-table legs: one per (event_id, role) — highest limit = main line
    legs_6pt  = _deduplicate_legs(legs_6pt_raw)
    legs_10pt = _deduplicate_legs(legs_10pt_raw)

    # ── Direct BetBCK scan for unmatched NFL lines ────────────────────────────
    # Collects NFL futures/early-week lines that aren't yet matched to Pinnacle.
    if betbck_games:
        seen_matchups = {l['matchup'].lower() for l in legs_6pt + legs_10pt}
        b6, b10 = _scan_betbck_for_nfl(betbck_games, seen_matchups)
        if b6:
            logger.info(f"[WONG] +{len(b6)} betbck-direct 6pt legs (unmatched NFL)")
        if b10:
            logger.info(f"[WONG] +{len(b10)} betbck-direct 10pt legs (unmatched NFL)")
        # Merge and re-deduplicate (betbck legs have unique game_ids so no conflicts)
        legs_6pt  = legs_6pt  + _deduplicate_legs(b6)
        legs_10pt = legs_10pt + _deduplicate_legs(b10)

    logger.info(
        f"[WONG] {len(legs_6pt)} qualifying 6pt legs "
        f"({len(legs_6pt_raw)} ev-table raw), "
        f"{len(legs_10pt)} qualifying 10pt legs "
        f"(NFL, pin_limit≥{min_pin_limit})"
    )

    combos_6pt  = _generate_combos(
        legs_6pt, TEASER_ODDS_6PT, WONG_6PT_WIN_RATE, ev_flag_6pt,
        teaser_type='6pt', min_teams=2, max_teams=5,
    )
    combos_10pt = _generate_combos(
        legs_10pt, TEASER_ODDS_10PT, WONG_10PT_WIN_RATE, ev_flag_10pt,
        teaser_type='10pt', min_teams=3, max_teams=3,
    )

    # ── Break-even analysis table (reference, using historical rates) ───────
    breakeven = []
    for n, odds in sorted(TEASER_ODDS_6PT.items()):
        be  = _break_even_rate(n, odds)
        ev  = _teaser_ev_hist(n, WONG_6PT_WIN_RATE, odds)
        breakeven.append({
            'type':                '6pt',
            'teams':               n,
            'book_odds':           _fmt_odds(odds),
            'break_even_pct':      round(be * 100.0, 2),
            'historical_rate_pct': round(WONG_6PT_WIN_RATE * 100.0, 1),
            'ev_at_historical_pct': round(ev, 2),
            'profitable':          ev > 0,
        })
    # 10pt: only 3-team at -120
    odds_10 = TEASER_ODDS_10PT[3]
    be_10   = _break_even_rate(3, odds_10)
    ev_10   = _teaser_ev_hist(3, WONG_10PT_WIN_RATE, odds_10)
    breakeven.append({
        'type':                '10pt',
        'teams':               3,
        'book_odds':           _fmt_odds(odds_10),
        'break_even_pct':      round(be_10 * 100.0, 2),
        'historical_rate_pct': round(WONG_10PT_WIN_RATE * 100.0, 1),
        'ev_at_historical_pct': round(ev_10, 2),
        'profitable':          ev_10 > 0,
    })

    return {
        'qualifying_legs_6pt':  len(legs_6pt),
        'qualifying_legs_10pt': len(legs_10pt),
        'legs_6pt': [
            {
                **{k: v for k, v in l.items() if k != 'priority'},
                'projected_prob_pct': round(_proj_leg_prob(l, WONG_6PT_WIN_RATE) * 100.0, 2),
            }
            for l in legs_6pt
        ],
        'legs_10pt': [
            {
                **{k: v for k, v in l.items() if k != 'priority'},
                'projected_prob_pct': round(_proj_leg_prob(l, WONG_10PT_WIN_RATE) * 100.0, 2),
            }
            for l in legs_10pt
        ],
        'combos_6pt':  combos_6pt,
        'combos_10pt': combos_10pt[:20],
        'breakeven':   breakeven,
        'config': {
            'win_rate_6pt_pct':   round(WONG_6PT_WIN_RATE * 100.0, 1),
            'win_rate_10pt_pct':  round(WONG_10PT_WIN_RATE * 100.0, 1),
            'min_pin_limit':      min_pin_limit,
            'ev_flag_6pt':        ev_flag_6pt,
            'ev_flag_10pt':       ev_flag_10pt,
            'teaser_type':        'sides only, no totals (NFL full-game spreads)',
            'ev_method':          '(hist_rate + 0.01*low_total) + (0.50 - NVP_implied_prob)*0.30 per leg',
        },
    }
