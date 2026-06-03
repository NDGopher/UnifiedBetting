"""
Parlay Generator — builds 2/3/4-leg parlays from Buckeye EV table results.

Designed for account-health / recreational-looking mug bets.

Filtering:
  - Pinnacle limit >= MIN_PIN_LIMIT (default 1000)
  - Individual leg EV >= MIN_LEG_EV_PCT (default -1.0%)
  - BetBCK odds <= MAX_PLUS_ODDS (+150) — no big dogs
  - At most MAX_PLUS_LEGS (3) +money legs per parlay
  - One leg per event_id (no two legs from the same game)

EV Math:
  proj_leg_prob   = _parse_nvp_prob(pinnacle_nvp)   # Pinnacle fair-price implied prob
  parlay_win_prob = product of proj_leg_probs
  decimal_payout  = product of betbck_decimal_odds   (true BetBCK parlay odds)
  EV%             = (parlay_win_prob * decimal_payout - 1) * 100

Two independent pools are returned:
  parlays      — top 30 across all dates (best global EV)
  parlays_24h  — top 30 from legs starting within the next 24 hours only
"""

import itertools
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MIN_PIN_LIMIT  = 1000
MIN_LEG_EV_PCT = -1.0   # Allow down to -1% EV for account-health plays
MAX_PLUS_ODDS  = 150     # Reject legs priced worse than +150 American
MAX_PLUS_LEGS  = 3       # Max +money legs per parlay
MIN_LEGS       = 2
MAX_LEGS       = 4
TOP_PER_SIZE   = 10  # top 10 per leg-count (2L / 3L / 4L) = up to 30 total


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_american(val: Any) -> Optional[int]:
    """Parse American odds string/int to int.  Returns None on failure."""
    if val is None:
        return None
    try:
        s = str(val).strip().replace('+', '').replace(' ', '')
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _american_to_decimal(american: int) -> float:
    if american > 0:
        return american / 100.0 + 1.0
    return 100.0 / abs(american) + 1.0


def _decimal_to_american_str(decimal: float) -> str:
    if decimal >= 2.0:
        return f'+{round((decimal - 1.0) * 100)}'
    return f'-{round(100.0 / (decimal - 1.0))}'


def _parse_nvp_prob(pin_nvp: Any) -> Optional[float]:
    """American odds string → implied probability [0, 1]."""
    val = _parse_american(pin_nvp)
    if val is None:
        return None
    if val < 0:
        return abs(val) / (abs(val) + 100.0)
    if val > 0:
        return 100.0 / (val + 100.0)
    return 0.5


def _parse_ev_pct(ev_val: Any) -> float:
    """Parse EV which may be '2.13%', 2.13, or None."""
    if ev_val is None:
        return 0.0
    try:
        return float(str(ev_val).replace('%', '').strip())
    except (ValueError, TypeError):
        return 0.0


def _is_within_24h(start_time_str: str) -> bool:
    """Return True if start_time (Central Time, 'YYYY-MM-DD HH:MM AM/PM') is within the next 24 hours."""
    if not start_time_str or start_time_str in ('-', 'N/A'):
        return False
    try:
        dt = datetime.strptime(start_time_str, '%Y-%m-%d %I:%M %p')
        try:
            import pytz
            central_tz = pytz.timezone('America/Chicago')
            dt_central = central_tz.localize(dt)
        except ImportError:
            dt_central = dt.replace(tzinfo=timezone(timedelta(hours=-5)))
        now_utc = datetime.now(timezone.utc)
        delta = (dt_central - now_utc.astimezone(dt_central.tzinfo)).total_seconds()
        return 0 <= delta <= 24 * 3600
    except Exception:
        return False


def _build_top_parlays(eligible: List[Dict], top_per_size: int = TOP_PER_SIZE) -> Dict[str, Any]:
    """
    Generate combos from the given eligible-leg pool and return the top
    top_per_size parlays per leg-count (2/3/4), sorted by EV descending.
    Returns a dict with keys: parlays, total_combos, counts_by_size.
    """
    raw: List[Dict] = []

    for n in range(MIN_LEGS, MAX_LEGS + 1):
        for combo in itertools.combinations(eligible, n):
            # Unique games only
            event_ids = [l['event_id'] for l in combo]
            if len(set(event_ids)) != n:
                continue

            # Max +money legs
            n_plus = sum(1 for l in combo if l['is_plus'])
            if n_plus > MAX_PLUS_LEGS:
                continue

            # EV math: parlay_EV = ∏(1 + ev_i/100) - 1
            combined_ev_factor = 1.0
            win_prob           = 1.0
            decimal_payout     = 1.0
            for l in combo:
                factor          = 1.0 + l['ev_pct'] / 100.0
                combined_ev_factor *= factor
                win_prob           *= factor / l['betbck_decimal']
                decimal_payout     *= l['betbck_decimal']

            ev_pct     = (combined_ev_factor - 1.0) * 100.0
            leagues    = [l['league'] for l in combo]
            same_sport = len(set(leagues)) == 1

            raw.append({
                'n_legs':         n,
                'parlay_odds':    _decimal_to_american_str(decimal_payout),
                'win_prob_pct':   round(win_prob * 100.0, 2),
                'ev_blended_pct': round(ev_pct, 2),
                'same_sport':     same_sport,
                'n_plus_legs':    n_plus,
                'legs': [
                    {
                        'bet':           l['bet'],
                        'matchup':       l['matchup'],
                        'league':        l['league'],
                        'pin_nvp':       l['pin_nvp'],
                        'betbck_odds':   l['betbck_odds'],
                        'pin_limit':     l['pin_limit'],
                        'ev_pct':        round(l['ev_pct'], 2),
                        'proj_prob_pct': round(l['proj_prob'] * 100.0, 2),
                        'start_time':    l['start_time'],
                    }
                    for l in combo
                ],
            })

    # Sort by EV descending, bucket top N per size
    raw.sort(key=lambda x: -x['ev_blended_pct'])

    by_size: Dict[int, list] = {2: [], 3: [], 4: []}
    for p in raw:
        n = p['n_legs']
        if n in by_size and len(by_size[n]) < top_per_size:
            by_size[n].append(p)

    top: List[Dict] = []
    for n in [2, 3, 4]:
        top.extend(by_size[n])
    top.sort(key=lambda x: -x['ev_blended_pct'])

    counts = {n: len(by_size[n]) for n in [2, 3, 4]}
    return {
        'parlays':        top,
        'total_combos':   len(raw),
        'counts_by_size': counts,
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def calculate_parlays(
    all_bets: List[Dict],
    min_pin_limit: int = MIN_PIN_LIMIT,
) -> Dict[str, Any]:
    """
    Generate two independent parlay pools from the Buckeye EV table:

      parlays      — top 30 across all dates, ranked by EV
      parlays_24h  — top 30 where every leg starts within the next 24 hours

    Parameters
    ----------
    all_bets       : flat list of bet dicts from the streaming pipeline
    min_pin_limit  : minimum Pinnacle limit per leg (default 1000)
    """
    # ── 1. Build eligible leg pool (all dates) ────────────────────────────────
    eligible: List[Dict] = []

    for row in all_bets:
        try:
            pin_limit = float(row.get('pinnacle_limit') or 0)
        except (TypeError, ValueError):
            pin_limit = 0.0
        if pin_limit < min_pin_limit:
            continue

        betbck_american = _parse_american(row.get('betbck_odds'))
        if betbck_american is None:
            continue

        if betbck_american > MAX_PLUS_ODDS:
            continue

        ev_pct = _parse_ev_pct(row.get('ev') or row.get('ev_pct'))
        if ev_pct < MIN_LEG_EV_PCT:
            continue

        betbck_decimal = _american_to_decimal(betbck_american)
        proj_prob      = (1.0 + ev_pct / 100.0) / betbck_decimal
        league         = (row.get('league') or '').strip()
        start_time     = row.get('start_time', '')

        eligible.append({
            'bet':             row.get('bet', ''),
            'matchup':         row.get('matchup', ''),
            'league':          league,
            'start_time':      start_time,
            'event_id':        str(row.get('event_id', id(row))),
            'pin_nvp':         row.get('pinnacle_nvp', ''),
            'pin_limit':       int(pin_limit),
            'betbck_odds':     str(row.get('betbck_odds', '')),
            'betbck_american': betbck_american,
            'betbck_decimal':  betbck_decimal,
            'ev_pct':          ev_pct,
            'proj_prob':       proj_prob,
            'is_plus':         betbck_american > 0,
        })

    # ── 2. Separate 24h leg pool ──────────────────────────────────────────────
    eligible_24h = [l for l in eligible if _is_within_24h(l['start_time'])]

    logger.info(
        f"[PARLAYS] Eligible legs: {len(eligible)} total, {len(eligible_24h)} within 24h "
        f"(pin≥{min_pin_limit}, EV≥{MIN_LEG_EV_PCT}%, odds≤+{MAX_PLUS_ODDS})"
    )

    # ── 3. Generate both pools ────────────────────────────────────────────────
    if len(eligible) >= MIN_LEGS:
        main = _build_top_parlays(eligible)
    else:
        main = {'parlays': [], 'total_combos': 0, 'counts_by_size': {2: 0, 3: 0, 4: 0}}

    if len(eligible_24h) >= MIN_LEGS:
        pool_24h = _build_top_parlays(eligible_24h)
    else:
        pool_24h = {'parlays': [], 'total_combos': 0, 'counts_by_size': {2: 0, 3: 0, 4: 0}}

    logger.info(
        f"[PARLAYS] All-dates: {main['total_combos']} combos → "
        f"2L:{main['counts_by_size'][2]}  3L:{main['counts_by_size'][3]}  4L:{main['counts_by_size'][4]}  "
        f"total:{len(main['parlays'])}"
    )
    logger.info(
        f"[PARLAYS] 24h pool: {pool_24h['total_combos']} combos → "
        f"2L:{pool_24h['counts_by_size'][2]}  3L:{pool_24h['counts_by_size'][3]}  4L:{pool_24h['counts_by_size'][4]}  "
        f"total:{len(pool_24h['parlays'])}"
    )

    return {
        'parlays':           main['parlays'],
        'parlays_24h':       pool_24h['parlays'],
        'total_combos':      main['total_combos'],
        'total_combos_24h':  pool_24h['total_combos'],
        'eligible_legs':     len(eligible),
        'eligible_legs_24h': len(eligible_24h),
        'counts_by_size':    main['counts_by_size'],
        'counts_by_size_24h': pool_24h['counts_by_size'],
        'config':            _config(min_pin_limit),
    }


def _config(min_pin_limit: int) -> Dict:
    return {
        'min_pin_limit':  min_pin_limit,
        'min_leg_ev_pct': MIN_LEG_EV_PCT,
        'max_plus_odds':  f'+{MAX_PLUS_ODDS}',
        'max_plus_legs':  MAX_PLUS_LEGS,
    }
