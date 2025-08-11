import json
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.pod_utils import analyze_markets_for_ev, process_event_odds_for_display, american_to_decimal, decimal_to_american
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure logger outputs to console and file for diagnostics
if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    fh = logging.FileHandler('ev_pipeline.log')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

# Swordfish API configuration
SWORDFISH_API_BASE_URL = "https://swordfish-production.up.railway.app/events/"

def get_swordfish_odds(event_id: str) -> dict:
    """Fetch odds for an event from Swordfish API. If fails, log error and return None."""
    try:
        url = f"{SWORDFISH_API_BASE_URL}{event_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to get Swordfish odds for event {event_id}: {response.status_code}.")
            return None
    except Exception as e:
        logger.warning(f"Error getting Swordfish odds for event {event_id}: {e}.")
        return None

def calculate_ev(betbck_odds: str, pinnacle_odds: str) -> float:
    """Calculate Expected Value"""
    try:
        betbck_decimal = american_to_decimal(betbck_odds)
        pinnacle_decimal = american_to_decimal(pinnacle_odds)
        
        if betbck_decimal == 0 or pinnacle_decimal == 0:
            return 0.0
        
        # EV = (BetBCK odds * probability) - 1
        # where probability = 1 / Pinnacle odds
        probability = 1 / pinnacle_decimal
        ev = (betbck_decimal * probability) - 1
        
        return ev * 100  # Convert to percentage
    except Exception as e:
        logger.error(f"Error calculating EV: {e}")
        return 0.0

def process_market_ev(betbck_line: Dict[str, Any], pinnacle_odds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process EV calculation for a specific market"""
    try:
        betbck_odds = betbck_line.get("odds", "0")
        market_type = betbck_line.get("market_type", "")
        selection = betbck_line.get("selection", "")
        line = betbck_line.get("line", "")
        
        # Find corresponding Pinnacle odds
        pinnacle_odds_value = "0"
        if market_type in pinnacle_odds:
            pinnacle_market = pinnacle_odds[market_type]
            if selection in pinnacle_market:
                pinnacle_odds_value = pinnacle_market[selection]
        
        ev = calculate_ev(betbck_odds, pinnacle_odds_value)
        logger.info(f"[EV] Calculated EV for {market_type} {selection} {line}: {ev:.2f}% (BetBCK: {betbck_odds}, Pinnacle: {pinnacle_odds_value})")
        # Return all opportunities, even if negative
        return {
            "market_type": market_type,
            "selection": selection,
            "line": line,
            "betbck_odds": betbck_odds,
            "pinnacle_odds": pinnacle_odds_value,
            "ev": f"{ev:.2f}%",
            "ev_value": ev
        }
    except Exception as e:
        logger.error(f"Error processing market EV: {e}")
        return None

def calculate_ev_for_event(matched_event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Calculate EV for all markets in a matched event"""
    try:
        event_id = matched_event.get("pinnacle_event_id")
        betbck_game = matched_event.get("betbck_game", {})
        betbck_odds = betbck_game.get("betbck_site_odds", {})
        
        # Get Pinnacle odds
        pinnacle_odds = get_swordfish_odds(event_id)
        if not pinnacle_odds:
            logger.warning(f"[EV] No Pinnacle odds found for event {event_id}")
            return []
        logger.info(f"[EV] Fetched Pinnacle odds for event {event_id}: keys={list(pinnacle_odds.keys())}")
        
        ev_opportunities = []
        
        # Process moneyline odds
        top_ml = betbck_odds.get("site_top_team_moneyline_american")
        bottom_ml = betbck_odds.get("site_bottom_team_moneyline_american")
        
        if top_ml and bottom_ml:
            # Try to find corresponding Pinnacle moneyline odds
            # This is a simplified approach - you might need to adjust based on actual Pinnacle data structure
            ev_top = calculate_ev(top_ml, "+100")  # Placeholder - need actual Pinnacle odds
            ev_bottom = calculate_ev(bottom_ml, "+100")  # Placeholder - need actual Pinnacle odds
            
            if ev_top > 0:
                ev_opportunities.append({
                    "market_type": "moneyline",
                    "selection": "top_team",
                    "line": "",
                    "betbck_odds": top_ml,
                    "pinnacle_odds": "+100",  # Placeholder
                    "ev": f"{ev_top:.2f}%",
                    "ev_value": ev_top
                })
            
            if ev_bottom > 0:
                ev_opportunities.append({
                    "market_type": "moneyline", 
                    "selection": "bottom_team",
                    "line": "",
                    "betbck_odds": bottom_ml,
                    "pinnacle_odds": "+100",  # Placeholder
                    "ev": f"{ev_bottom:.2f}%",
                    "ev_value": ev_bottom
                })
        
        logger.info(f"[EV] For event {event_id}: {len(ev_opportunities)} EVs found.")
        return ev_opportunities
    except Exception as e:
        logger.error(f"Error calculating EV for event {matched_event.get('pinnacle_event_id')}: {e}")
        return []

def calculate_ev_table(matched_games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import math
    from utils.pod_utils import american_to_decimal, decimal_to_american
    from datetime import datetime
    logger.info(f"[EV-PIPELINE] Starting EV calculation for {len(matched_games)} matched games.")
    if not matched_games:
        logger.warning("[EV-PIPELINE] No matched games provided for EV calculation.")
        return []
    all_bets_with_ev = []
    for idx, matched_event in enumerate(matched_games):
        try:
            event_id = matched_event.get('pinnacle_event_id')
            home_team = matched_event.get('pinnacle_home_team', matched_event.get('betbck_site_home_team', 'Unknown'))
            away_team = matched_event.get('pinnacle_away_team', matched_event.get('betbck_site_away_team', 'Unknown'))
            sport = matched_event.get('betbck_sport') or matched_event.get('pinnacle_sport_name') or 'Unknown'
            betbck_game = matched_event.get('betbck_game', {})
            betbck_odds = betbck_game.get('betbck_site_odds', {})
            betbck_odds_data = betbck_odds
            swordfish_odds = get_swordfish_odds(event_id)
            if not swordfish_odds or not swordfish_odds.get('data'):
                continue
            swordfish_odds = process_event_odds_for_display(swordfish_odds)
            swordfish_data = swordfish_odds.get('data', {})
            periods = swordfish_data.get('periods', {})
            period_0_data = periods.get('num_0') or periods.get('0')
            if not period_0_data or not isinstance(period_0_data, dict):
                continue
            # Start time extraction
            start_time = matched_event.get('start_time') or swordfish_data.get('starts') or '-'
            if isinstance(start_time, (int, float)) or (isinstance(start_time, str) and str(start_time).isdigit()):
                start_time_fmt = datetime.utcfromtimestamp(int(start_time) / 1000).strftime('%Y-%m-%d %I:%M %p')
            else:
                start_time_fmt = str(start_time)
            # League extraction
            league = swordfish_data.get('league_name') or swordfish_data.get('league') or swordfish_data.get('sport_name') or sport
            event_name = f"{home_team} vs {away_team}" if home_team and away_team else home_team or away_team or "-"
            game_id = str(event_id)
            # --- Moneyline ---
            ml = period_0_data.get('money_line', {})
            meta_limits = (period_0_data.get('meta') or {}) if isinstance(period_0_data.get('meta'), dict) else {}
            pin_ml_home_dec = ml.get('nvp_home')
            pin_ml_away_dec = ml.get('nvp_away')
            pin_ml_draw_dec = ml.get('nvp_draw')
            # Use explicitly mapped odds from matching step
            bck_ml_home_am = matched_event.get('betbck_home_odds')
            bck_ml_away_am = matched_event.get('betbck_away_odds')
            bck_ml_draw_am = betbck_odds_data.get('draw_moneyline_american')
            logger.info(f"[MAPPING-EV] Event: {home_team} vs {away_team} | BetBCK home odds: {bck_ml_home_am}, away odds: {bck_ml_away_am}")
            bck_ml_home_dec = american_to_decimal(bck_ml_home_am)
            bck_ml_away_dec = american_to_decimal(bck_ml_away_am)
            bck_ml_draw_dec = american_to_decimal(bck_ml_draw_am)
            ev_ml_home = (bck_ml_home_dec / pin_ml_home_dec - 1.0) if bck_ml_home_dec and pin_ml_home_dec and pin_ml_home_dec > 1.0001 else None
            ev_ml_away = (bck_ml_away_dec / pin_ml_away_dec - 1.0) if bck_ml_away_dec and pin_ml_away_dec and pin_ml_away_dec > 1.0001 else None
            ev_ml_draw = (bck_ml_draw_dec / pin_ml_draw_dec - 1.0) if bck_ml_draw_dec and pin_ml_draw_dec and pin_ml_draw_dec > 1.0001 else None
            if ev_ml_home is not None:
                all_bets_with_ev.append({
                    'sport': sport,
                    'event': event_name,
                    'bet': f"ML - {home_team}",
                    'bet_type': 'Moneyline',
                    'betbck_odds': bck_ml_home_am,
                    'pin_nvp': decimal_to_american(pin_ml_home_dec),
                    'ev': f"{ev_ml_home*100:.2f}%",
                    'ev_val': ev_ml_home,
                    'start_time': start_time_fmt,
                    'league': league,
                    'max_bet': ml.get('max_money_line') or meta_limits.get('max_money_line') or meta_limits.get('max_spread') or meta_limits.get('max_total'),
                    'event_id': event_id
                })
            if ev_ml_away is not None:
                all_bets_with_ev.append({
                    'sport': sport,
                    'event': event_name,
                    'bet': f"ML - {away_team}",
                    'bet_type': 'Moneyline',
                    'betbck_odds': bck_ml_away_am,
                    'pin_nvp': decimal_to_american(pin_ml_away_dec),
                    'ev': f"{ev_ml_away*100:.2f}%",
                    'ev_val': ev_ml_away,
                    'start_time': start_time_fmt,
                    'league': league,
                    'max_bet': ml.get('max_money_line') or meta_limits.get('max_money_line') or meta_limits.get('max_spread') or meta_limits.get('max_total'),
                    'event_id': event_id
                })
            if ev_ml_draw is not None:
                all_bets_with_ev.append({
                    'sport': sport,
                    'event': event_name,
                    'bet': 'ML - Draw',
                    'bet_type': 'Moneyline',
                    'betbck_odds': bck_ml_draw_am,
                    'pin_nvp': decimal_to_american(pin_ml_draw_dec),
                    'ev': f"{ev_ml_draw*100:.2f}%",
                    'ev_val': ev_ml_draw,
                    'start_time': start_time_fmt,
                    'league': league,
                    'max_bet': ml.get('max_money_line') or meta_limits.get('max_money_line') or meta_limits.get('max_spread') or meta_limits.get('max_total'),
                    'event_id': event_id
                })
            # --- Spreads ---
            pin_spreads = period_0_data.get('spreads', {})
            if isinstance(pin_spreads, dict):
                # Robust mapping for spreads
                for bck_spread_info in betbck_odds_data.get('site_top_team_spreads', []):
                    bck_line = bck_spread_info.get('line')
                    bck_odds_am = bck_spread_info.get('odds')
                    bck_team_raw = bck_spread_info.get('team') or matched_event.get('betbck_home_team')
                    bck_team_norm = matched_event.get('normalized_betbck_home')
                    # Map to event home/away
                    mapped_team = None
                    nvp_pin_spread = None
                    pin_spread_key = str(bck_line)
                    if pin_spread_key == "0": pin_spread_key = "0.0"
                    pin_spread_market = pin_spreads.get(pin_spread_key) or pin_spreads.get(f"{pin_spread_key}.0")
                    # Try negative and float conversion if not found
                    if not pin_spread_market:
                        try:
                            neg_key = str(-float(bck_line))
                            pin_spread_market = pin_spreads.get(neg_key) or pin_spreads.get(f"{neg_key}.0")
                        except Exception:
                            pass
                    if not pin_spread_market and "." in pin_spread_key:
                        try:
                            float_key = str(float(pin_spread_key))
                            pin_spread_market = pin_spreads.get(float_key)
                        except Exception:
                            pass
                    if bck_team_norm == matched_event.get('normalized_pinnacle_home'):
                        mapped_team = home_team
                        if pin_spread_market and isinstance(pin_spread_market, dict):
                            nvp_pin_spread = pin_spread_market.get('nvp_home')
                    elif bck_team_norm == matched_event.get('normalized_pinnacle_away'):
                        mapped_team = away_team
                        if pin_spread_market and isinstance(pin_spread_market, dict):
                            nvp_pin_spread = pin_spread_market.get('nvp_away')
                    if mapped_team and nvp_pin_spread and isinstance(nvp_pin_spread, (int, float)) and nvp_pin_spread > 1.0001:
                        ev = (american_to_decimal(bck_odds_am) / nvp_pin_spread - 1.0) if bck_odds_am else None
                        if ev is not None:
                            all_bets_with_ev.append({
                                'sport': sport,
                                'event': event_name,
                                'bet': f"{mapped_team} {bck_line}",
                                'bet_type': 'Spread',
                                'betbck_odds': bck_odds_am,
                                'pin_nvp': decimal_to_american(nvp_pin_spread),
                                'ev': f"{ev*100:.2f}%",
                                'ev_val': ev,
                                'start_time': start_time_fmt,
                                'league': league,
                                'max_bet': (pin_spread_market.get('max') if pin_spread_market else None) or meta_limits.get('max_spread'),
                                'event_id': event_id
                            })
                    else:
                        logger.warning(f"[MAPPING-SPREAD] Skipping: Could not confidently map or missing/invalid NVP for BetBCK spread team '{bck_team_raw}' (norm: '{bck_team_norm}') line '{bck_line}' to event home/away: home='{matched_event.get('normalized_pinnacle_home')}', away='{matched_event.get('normalized_pinnacle_away')}', NVP={nvp_pin_spread}")
                for bck_spread_info in betbck_odds_data.get('site_bottom_team_spreads', []):
                    bck_line = bck_spread_info.get('line')
                    bck_odds_am = bck_spread_info.get('odds')
                    bck_team_raw = bck_spread_info.get('team') or matched_event.get('betbck_away_team')
                    bck_team_norm = matched_event.get('normalized_betbck_away')
                    mapped_team = None
                    nvp_pin_spread = None
                    pin_spread_key = str(bck_line)
                    if pin_spread_key == "0": pin_spread_key = "0.0"
                    pin_spread_market = pin_spreads.get(pin_spread_key) or pin_spreads.get(f"{pin_spread_key}.0")
                    if not pin_spread_market:
                        try:
                            neg_key = str(-float(bck_line))
                            pin_spread_market = pin_spreads.get(neg_key) or pin_spreads.get(f"{neg_key}.0")
                        except Exception:
                            pass
                    if not pin_spread_market and "." in pin_spread_key:
                        try:
                            float_key = str(float(pin_spread_key))
                            pin_spread_market = pin_spreads.get(float_key)
                        except Exception:
                            pass
                    if bck_team_norm == matched_event.get('normalized_pinnacle_home'):
                        mapped_team = home_team
                        if pin_spread_market and isinstance(pin_spread_market, dict):
                            nvp_pin_spread = pin_spread_market.get('nvp_home')
                    elif bck_team_norm == matched_event.get('normalized_pinnacle_away'):
                        mapped_team = away_team
                        if pin_spread_market and isinstance(pin_spread_market, dict):
                            nvp_pin_spread = pin_spread_market.get('nvp_away')
                    if mapped_team and nvp_pin_spread and isinstance(nvp_pin_spread, (int, float)) and nvp_pin_spread > 1.0001:
                        ev = (american_to_decimal(bck_odds_am) / nvp_pin_spread - 1.0) if bck_odds_am else None
                        if ev is not None:
                            all_bets_with_ev.append({
                                'sport': sport,
                                'event': event_name,
                                'bet': f"{mapped_team} {bck_line}",
                                'bet_type': 'Spread',
                                'betbck_odds': bck_odds_am,
                                'pin_nvp': decimal_to_american(nvp_pin_spread),
                                'ev': f"{ev*100:.2f}%",
                                'ev_val': ev,
                                'start_time': start_time_fmt,
                                'league': league,
                                'max_bet': (pin_spread_market.get('max') if pin_spread_market else None) or meta_limits.get('max_spread'),
                                'event_id': event_id
                            })
                    else:
                        logger.warning(f"[MAPPING-SPREAD] Skipping: Could not confidently map or missing/invalid NVP for BetBCK spread team '{bck_team_raw}' (norm: '{bck_team_norm}') line '{bck_line}' to event home/away: home='{matched_event.get('normalized_pinnacle_home')}', away='{matched_event.get('normalized_pinnacle_away')}', NVP={nvp_pin_spread}")
            # --- Totals ---
            pin_totals = period_0_data.get('totals', {})
            if isinstance(pin_totals, dict):
                for pin_total_key, pin_total_market in pin_totals.items():
                    if not isinstance(pin_total_market, dict): continue
                    nvp_totals = [pin_total_market.get('nvp_over'), pin_total_market.get('nvp_under')]
                    nvp_pin_over = nvp_totals[0] if nvp_totals and len(nvp_totals) > 0 else None
                    nvp_pin_under = nvp_totals[1] if nvp_totals and len(nvp_totals) > 1 else None
                    # Try to find matching BetBCK odds for this total line
                    bck_over_am = None
                    bck_under_am = None
                    for key in [pin_total_key, str(float(pin_total_key))]:
                        if betbck_odds_data.get('game_total_line') == key:
                            bck_over_am = betbck_odds_data.get('game_total_over_odds')
                            bck_under_am = betbck_odds_data.get('game_total_under_odds')
                            break
                    try:
                        bck_line = float(betbck_odds_data.get('game_total_line', 'nan'))
                        pin_line = float(pin_total_key)
                        if abs(bck_line - pin_line) < 0.01:
                            bck_over_am = betbck_odds_data.get('game_total_over_odds')
                            bck_under_am = betbck_odds_data.get('game_total_under_odds')
                    except Exception:
                        pass
                    if bck_over_am is not None and nvp_pin_over is not None:
                        bck_over_dec = american_to_decimal(bck_over_am)
                        ev_over = (bck_over_dec / nvp_pin_over - 1.0) if bck_over_dec and nvp_pin_over and nvp_pin_over > 1.0001 else None
                        if ev_over is not None:
                            all_bets_with_ev.append({
                                'sport': sport,
                                'event': event_name,
                                'bet': f"Over {pin_total_key}",
                                'bet_type': 'Total',
                                'betbck_odds': bck_over_am,
                                'pin_nvp': decimal_to_american(nvp_pin_over),
                                'ev': f"{ev_over*100:.2f}%",
                                'ev_val': ev_over,
                                'start_time': start_time_fmt,
                                'league': league,
                                'max_bet': pin_total_market.get('max') or meta_limits.get('max_total'),
                                'event_id': event_id
                            })
                    if bck_under_am is not None and nvp_pin_under is not None:
                        bck_under_dec = american_to_decimal(bck_under_am)
                        ev_under = (bck_under_dec / nvp_pin_under - 1.0) if bck_under_dec and nvp_pin_under and nvp_pin_under > 1.0001 else None
                        if ev_under is not None:
                            all_bets_with_ev.append({
                                'sport': sport,
                                'event': event_name,
                                'bet': f"Under {pin_total_key}",
                                'bet_type': 'Total',
                                'betbck_odds': bck_under_am,
                                'pin_nvp': decimal_to_american(nvp_pin_under),
                                'ev': f"{ev_under*100:.2f}%",
                                'ev_val': ev_under,
                                'start_time': start_time_fmt,
                                'league': league,
                                'max_bet': pin_total_market.get('max') or meta_limits.get('max_total'),
                                'event_id': event_id
                            })
        except Exception as e:
            logger.error(f"[EV-PIPELINE] Error processing event {matched_event.get('pinnacle_event_id')}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    # Filter out any bet with ev_val > 0.15 (15%)
    all_bets_with_ev = [bet for bet in all_bets_with_ev if abs(bet.get('ev_val', 0)) <= 0.15]
    # Sort by EV descending
    all_bets_with_ev.sort(key=lambda x: x.get('ev_val', 0), reverse=True)
    return all_bets_with_ev

def save_ev_table(ev_table: List[Dict[str, Any]], filename: str = None) -> bool:
    """Save EV table to file (flat list of bets/markets)"""
    try:
        if filename is None:
            filename = DATA_DIR / "ev_table.json"
        else:
            filename = DATA_DIR / Path(filename).name
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        data = {
            "ev_table": ev_table,
            "total_bets": len(ev_table),
            "timestamp": datetime.now().isoformat()
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved EV table with {len(ev_table)} bets to {filename}")
        return True
    except Exception as e:
        logger.error(f"Error saving EV table: {e}")
        return False

def load_ev_table(filename: str = "data/ev_table.json") -> Optional[List[Dict[str, Any]]]:
    """Load EV table from file"""
    try:
        import os
        if not os.path.exists(filename):
            logger.warning(f"EV table file not found: {filename}")
            return None
        
        with open(filename, 'r') as f:
            data = json.load(f)
        
        ev_table = data.get("ev_table", [])
        logger.info(f"Loaded EV table with {len(ev_table)} events from {filename}")
        return ev_table
    except Exception as e:
        logger.error(f"Error loading EV table: {e}")
        return None

def format_ev_table_for_display(ev_table: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format EV table for frontend display (flat list of bets/markets)"""
    # Optionally, filter or sort here if needed for frontend
    return ev_table

if __name__ == "__main__":
    # Test the EV calculation
    matched_games = [
        {
            "pinnacle_event_id": "123",
            "pinnacle_home_team": "Lakers",
            "pinnacle_away_team": "Warriors",
            "betbck_game": {
                "lines": [
                    {"market_type": "spread", "selection": "Lakers", "line": "-5.5", "odds": "+110"},
                    {"market_type": "spread", "selection": "Warriors", "line": "+5.5", "odds": "-110"}
                ]
            }
        }
    ]
    
    ev_table = calculate_ev_table(matched_games)
    print(f"Calculated EV for {len(ev_table)} events")
    print(json.dumps(ev_table, indent=2))

"""
calculate_ev_table.py

Unified robust EV calculation pipeline for UnifiedBetting2 backend.

- Outputs a flat list of bets/markets (not per-event), with all fields required for the frontend dashboard table:
  sport, event, bet, bet_type, betbck_odds, pin_nvp, ev, start_time, league, max_bet, event_id.
- Includes all sports and all market types (moneyline, spreads, totals, etc.).
- Uses NVP odds for EV calculation, matching the original evtest logic.
- Defensive to missing/malformed data, with diagnostics and logging.
- Output is designed for a frontend table: one row per bet/market, all columns populated.
""" 