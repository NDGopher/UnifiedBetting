import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from utils.pod_utils import normalize_team_name_for_matching, analyze_markets_for_ev, analyze_markets_multi_row, clean_pod_team_name_for_search, determine_betbck_search_term

# Use the specialized buckeye logger
logger = logging.getLogger("buckeye")

# Configuration
ARCADIA_BASE_URL = "https://guest.api.arcadia.pinnacle.com/0.1"

# Sports to exclude
EXCLUDED_SPORTS = [
    "Cycling", "Formula 1", "Rugby Union", "Rugby League",
    "Handball", "E Sports", "Darts", "Tennis"
]

BASE_DIR = Path(__file__).resolve().parent

class BuckeyeScraper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.event_ids_file = BASE_DIR / "data" / "buckeye_event_ids.json"
        self.results_file = BASE_DIR / "data" / "buckeye_results.json"
        
        # Ensure data directory exists
        self.event_ids_file.parent.mkdir(parents=True, exist_ok=True)
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("BuckeyeScraper initialized")
    
    def get_date(self):
        """Get today's date"""
        today = datetime.now()
        return today.strftime("%Y-%m-%d")
    
    def fetch_sports(self) -> List[Dict[str, Any]]:
        """Fetch sports list dynamically from /sports"""
        logger.info("Fetching sports list from Arcadia API...")
        url = f"{ARCADIA_BASE_URL}/sports"
        params = {"brandId": "0"}
        try:
            response = requests.get(url, params=params, timeout=10)
            logger.info(f"[ARCADIA] Sports API response status: {response.status_code}")
            
            if response.status_code == 401:
                logger.warning("[ARCADIA] 401 Unauthorized - API access restricted, using fallback")
                raise Exception("401 Unauthorized - API access restricted")
            
            response.raise_for_status()
            sports_data = response.json()
            logger.info(f"[ARCADIA] Raw sports data: {len(sports_data)} sports returned")
            
            # Log all available sports for debugging
            for sport in sports_data[:10]:  # Log first 10 sports
                logger.info(f"[ARCADIA] Sport: {sport.get('name', 'Unknown')} (ID: {sport.get('id', 'Unknown')}, Matchups: {sport.get('matchupCount', 0)})")
            
            # Filter sports with matchups and exclude specified sports
            sports = [
                {
                    "name": sport["name"],
                    "sport_id": sport["id"],
                    "url": sport["name"].lower().replace(" ", "-"),
                    "matchup_count": sport["matchupCount"]
                }
                for sport in sports_data
                if sport["matchupCount"] > 0 and sport["name"] not in EXCLUDED_SPORTS
            ]
            logger.info(f"[ARCADIA] Retrieved {len(sports)} sports with matchups from Arcadia API")
            return sports
        except Exception as e:
            logger.error(f"[ARCADIA] Error fetching sports: {e}. Using fallback list...")
            sports = [
                {"name": "Soccer", "sport_id": 29, "url": "soccer", "matchup_count": 1},  # Force to 1 so it doesn't get skipped
                {"name": "Basketball", "sport_id": 4, "url": "basketball", "matchup_count": 1},
                {"name": "American Football", "sport_id": 15, "url": "american-football", "matchup_count": 1},
                {"name": "Baseball", "sport_id": 3, "url": "baseball", "matchup_count": 1},
                {"name": "Ice Hockey", "sport_id": 19, "url": "hockey", "matchup_count": 1},
            ]
            sports = [sport for sport in sports if sport["name"] not in EXCLUDED_SPORTS]
            logger.info(f"Using {len(sports)} fallback sports")
            return sports
    
    def fetch_arcadia_events(self) -> List[Dict[str, Any]]:
        """Fetch event IDs and teams from Arcadia API"""
        date = self.get_date()
        logger.info(f"Fetching Pinnacle events for {date}...")

        # Fetch sports list
        sports = self.fetch_sports()
        all_events = []
        total_requests = 0
        restricted_sports = []

        for sport in sports:
            sport_name = sport["name"]
            sport_id = sport["sport_id"]
            sport_url = sport["url"]
            matchup_count = sport["matchup_count"]

            # Skip sports with no matchups
            if matchup_count == 0:
                all_events.append({
                    "sport_name": sport_name,
                    "sport_url": sport_url,
                    "sport_id": sport_id,
                    "events": []
                })
                logger.info(f"{sport_name} (ID: {sport_id}): 0 events (skipped)")
                continue

            events = []

            # Special case for American Football: Fetch from known leagues
            if sport_name == "Football":  # American Football (sport_id: 15)
                # Known leagues: CFL (876), UFL (220795)
                league_ids = [876, 220795]
                for league_id in league_ids:
                    url = f"{ARCADIA_BASE_URL}/leagues/{league_id}/matchups"
                    params = {"brandId": "0"}
                    try:
                        response = requests.get(url, params=params)
                        total_requests += 1
                        response.raise_for_status()
                        matchups = response.json()
                        logger.info(f"[ARCADIA] League {league_id}: Got {len(matchups)} matchups")
                        
                        # Log raw response for first few events to debug structure
                        if len(matchups) > 0:
                            logger.info(f"[ARCADIA] Raw response sample for League {league_id}:")
                            for i, matchup in enumerate(matchups[:3]):  # First 3 events
                                logger.info(f"[ARCADIA]   Event {i+1}: {matchup}")
                        
                        for matchup in matchups:
                            event_id = matchup["id"]
                            participants = matchup.get("participants", [])
                            home_team = next((p["name"] for p in participants if p["alignment"] == "home"), "Unknown")
                            away_team = next((p["name"] for p in participants if p["alignment"] == "away"), "Unknown")
                            # Filter out HRE/prop events
                            def is_hre_or_prop_team(name: str) -> bool:
                                name = name.lower()
                                return any(x in name for x in ["hits+runs+errors", "h+r+e", "hre"])
                            if is_hre_or_prop_team(home_team) or is_hre_or_prop_team(away_team):
                                logger.info(f"[SKIP] HRE/prop event: {home_team} vs {away_team}")
                                continue
                            logger.info(f"[ARCADIA] Event {event_id}: '{home_team}' vs '{away_team}'")
                            events.append({
                                "event_id": event_id,
                                "home_team": home_team,
                                "away_team": away_team
                            })
                    except Exception as e:
                        logger.error(f"Exception for {sport_name} (League {league_id}): {e}")
                # Also fetch from /matchups to get NFL games
                url = f"{ARCADIA_BASE_URL}/sports/{sport_id}/matchups"
                params = {"withSpecials": "false", "brandId": "0"}
                try:
                    response = requests.get(url, params=params)
                    total_requests += 1
                    response.raise_for_status()
                    matchups = response.json()
                    logger.info(f"[ARCADIA] Sport {sport_id} /matchups: Got {len(matchups)} matchups")
                    
                    # Log raw response for first few events to debug structure
                    if len(matchups) > 0:
                        logger.info(f"[ARCADIA] Raw response sample for Sport {sport_id} /matchups:")
                        for i, matchup in enumerate(matchups[:3]):  # First 3 events
                            logger.info(f"[ARCADIA]   Event {i+1}: {matchup}")
                    
                    for matchup in matchups:
                        event_id = matchup["id"]
                        participants = matchup.get("participants", [])
                        home_team = next((p["name"] for p in participants if p["alignment"] == "home"), "Unknown")
                        away_team = next((p["name"] for p in participants if p["alignment"] == "away"), "Unknown")
                        # Filter out HRE/prop events
                        def is_hre_or_prop_team(name: str) -> bool:
                            name = name.lower()
                            return any(x in name for x in ["hits+runs+errors", "h+r+e", "hre"])
                        if is_hre_or_prop_team(home_team) or is_hre_or_prop_team(away_team):
                            logger.info(f"[SKIP] HRE/prop event: {home_team} vs {away_team}")
                            continue
                        # Avoid duplicates if already fetched from league endpoints
                        if not any(e["event_id"] == event_id for e in events):
                            logger.info(f"[ARCADIA] Event {event_id}: '{home_team}' vs '{away_team}'")
                            events.append({
                                "event_id": event_id,
                                "home_team": home_team,
                                "away_team": away_team
                            })
                except Exception as e:
                    logger.error(f"Exception for {sport_name} (/matchups): {e}")
            else:
                # Try primary endpoint: /matchups
                url = f"{ARCADIA_BASE_URL}/sports/{sport_id}/matchups"
                params = {"withSpecials": "false", "brandId": "0"}
                try:
                    response = requests.get(url, params=params)
                    total_requests += 1
                    response.raise_for_status()
                    matchups = response.json()
                    logger.info(f"[ARCADIA] Sport {sport_id}: Got {len(matchups)} matchups")
                    
                    # Log raw response for first few events to debug structure
                    if len(matchups) > 0:
                        logger.info(f"[ARCADIA] Raw response sample for Sport {sport_id}:")
                        for i, matchup in enumerate(matchups[:3]):  # First 3 events
                            logger.info(f"[ARCADIA]   Event {i+1}: {matchup}")
                    
                    for matchup in matchups:
                        event_id = matchup["id"]
                        participants = matchup.get("participants", [])
                        home_team = next((p["name"] for p in participants if p["alignment"] == "home"), "Unknown")
                        away_team = next((p["name"] for p in participants if p["alignment"] == "away"), "Unknown")
                        # Filter out HRE/prop events
                        def is_hre_or_prop_team(name: str) -> bool:
                            name = name.lower()
                            return any(x in name for x in ["hits+runs+errors", "h+r+e", "hre"])
                        if is_hre_or_prop_team(home_team) or is_hre_or_prop_team(away_team):
                            logger.info(f"[SKIP] HRE/prop event: {home_team} vs {away_team}")
                            continue
                        logger.info(f"[ARCADIA] Event {event_id}: '{home_team}' vs '{away_team}'")
                        events.append({
                            "event_id": event_id,
                            "home_team": home_team,
                            "away_team": away_team
                        })
                except requests.exceptions.HTTPError as e:
                    if response.status_code == 401:
                        logger.warning(f"401 Unauthorized for {sport_name}. Trying fallback endpoint...")
                        url = f"{ARCADIA_BASE_URL}/sports/{sport_id}/matchups/highlighted"
                        try:
                            response = requests.get(url, params={"brandId": "0"})
                            total_requests += 1
                            response.raise_for_status()
                            matchups = response.json()
                            logger.info(f"[ARCADIA] Fallback for {sport_name}: Got {len(matchups)} matchups")
                            
                            # Log raw response for first few events to debug structure
                            if len(matchups) > 0:
                                logger.info(f"[ARCADIA] Raw response sample for Fallback {sport_name}:")
                                for i, matchup in enumerate(matchups[:3]):  # First 3 events
                                    logger.info(f"[ARCADIA]   Event {i+1}: {matchup}")
                            
                            for matchup in matchups:
                                event_id = matchup["id"]
                                participants = matchup.get("participants", [])
                                home_team = next((p["name"] for p in participants if p["alignment"] == "home"), "Unknown")
                                away_team = next((p["name"] for p in participants if p["alignment"] == "away"), "Unknown")
                                # Filter out HRE/prop events
                                def is_hre_or_prop_team(name: str) -> bool:
                                    name = name.lower()
                                    return any(x in name for x in ["hits+runs+errors", "h+r+e", "hre"])
                                if is_hre_or_prop_team(home_team) or is_hre_or_prop_team(away_team):
                                    logger.info(f"[SKIP] HRE/prop event: {home_team} vs {away_team}")
                                    continue
                                logger.info(f"[ARCADIA] Event {event_id}: '{home_team}' vs '{away_team}'")
                                events.append({
                                    "event_id": event_id,
                                    "home_team": home_team,
                                    "away_team": away_team
                                })
                            logger.info(f"Fallback successful for {sport_name}: {len(events)} events")
                        except requests.exceptions.HTTPError as e2:
                            if response.status_code == 401:
                                logger.warning(f"401 Unauthorized for {sport_name} on fallback endpoint.")
                                restricted_sports.append(sport_name)
                            else:
                                logger.error(f"Exception for {sport_name} on fallback: {e2}")
                    else:
                        logger.error(f"Exception for {sport_name}: {e}")
                except Exception as e:
                    logger.error(f"Exception for {sport_name}: {e}")

            all_events.append({
                "sport_name": sport_name,
                "sport_url": sport_url,
                "sport_id": sport_id,
                "events": events
            })
            logger.info(f"{sport_name} (ID: {sport_id}): {len(events)} events")
            time.sleep(1)  # Avoid rate limiting

        logger.info(f"Total requests: {total_requests}")
        if restricted_sports:
            logger.warning(f"Restricted sports (401 Unauthorized): {restricted_sports}")
        return all_events
    
    def get_todays_event_ids(self) -> List[Dict[str, Any]]:
        """Get all event IDs for today's games from Arcadia API with team names"""
        try:
            logger.info("Fetching today's event IDs from Arcadia...")
            
            # Fetch events using the Arcadia logic
            all_events = self.fetch_arcadia_events()
            
            # Extract event IDs with team names (like the old repo's eventID.py)
            event_dicts = []
            total_events = 0
            events_with_team_names = 0
            events_with_unknown_teams = 0
            
            for sport_data in all_events:
                sport_name = sport_data.get("sport_name", "Unknown")
                sport_events = sport_data.get("events", [])
                logger.info(f"[EVENT-EXTRACT] Sport '{sport_name}': {len(sport_events)} events")
                
                for event in sport_events:
                    total_events += 1
                    event_id = event.get("event_id", "unknown")
                    home_team = event.get("home_team", "")
                    away_team = event.get("away_team", "")
                    
                    # Check if we have proper team names
                    if home_team and home_team != "Unknown" and away_team and away_team != "Unknown":
                        events_with_team_names += 1
                        logger.debug(f"[EVENT-EXTRACT] [OK] Event {event_id}: '{home_team}' vs '{away_team}'")
                    else:
                        events_with_unknown_teams += 1
                        logger.warning(f"[EVENT-EXTRACT] [ERROR] Event {event_id}: Missing team names - home='{home_team}', away='{away_team}'")
                    
                    event_dicts.append({
                        "event_id": event_id,
                        "home_team": home_team if home_team and home_team != "Unknown" else f"Team_{event_id}_Home",
                        "away_team": away_team if away_team and away_team != "Unknown" else f"Team_{event_id}_Away"
                    })
            
            logger.info(f"[EVENT-EXTRACT] SUMMARY:")
            logger.info(f"[EVENT-EXTRACT]   Total events: {total_events}")
            logger.info(f"[EVENT-EXTRACT]   Events with team names: {events_with_team_names}")
            logger.info(f"[EVENT-EXTRACT]   Events with unknown teams: {events_with_unknown_teams}")
            logger.info(f"[EVENT-EXTRACT]   Success rate: {events_with_team_names/total_events*100:.1f}%" if total_events > 0 else "0%")
            
            logger.info(f"Retrieved {len(event_dicts)} event IDs with team names from Arcadia")
            logger.debug(f"First 3 events: {event_dicts[:3]}")
            return event_dicts
            
        except Exception as e:
            logger.error(f"Error fetching event IDs from Arcadia: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def save_event_ids(self, event_ids: List[str]) -> bool:
        """Save event IDs to file with timestamp"""
        try:
            data = {
                "event_ids": event_ids,
                "timestamp": datetime.now().isoformat(),
                "count": len(event_ids)
            }
            
            with open(self.event_ids_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(event_ids)} event IDs to {self.event_ids_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving event IDs: {e}")
            return False
    
    def load_event_ids(self) -> Optional[List[str]]:
        """Load event IDs from file if they exist and are recent"""
        try:
            if not self.event_ids_file.exists():
                return None
            
            with open(self.event_ids_file, 'r') as f:
                data = json.load(f)
            
            # Check if the file is from today
            timestamp = datetime.fromisoformat(data.get("timestamp", ""))
            if timestamp.date() == datetime.now().date():
                logger.info(f"Loaded {len(data.get('event_ids', []))} event IDs from file")
                return data.get("event_ids", [])
            else:
                logger.info("Event IDs file is outdated, need to fetch new ones")
                return None
                
        except Exception as e:
            logger.error(f"Error loading event IDs: {e}")
            return None
    
    def get_pinnacle_event_odds(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get Pinnacle odds for a specific event using Swordfish"""
        try:
            # Use the existing Swordfish logic from odds_processing.py
            from odds_processing import fetch_live_pinnacle_event_odds
            
            odds_data = fetch_live_pinnacle_event_odds(event_id)
            # fetch_live_pinnacle_event_odds returns {"success": True, "data": <swordfish_response>}
            # swordfish_response itself is {"data": {"home":..., "periods":{...}}}
            # We unwrap to the inner event detail {"home":..., "periods":{...}} so
            # get_betbck_odds can read .get("home") and calculate_ev can re-wrap correctly.
            if odds_data and odds_data.get("success") == True:
                swordfish_response = odds_data.get("data", {})
                return swordfish_response.get("data", {})
            
            logger.warning(f"No Pinnacle odds found for event {event_id}")
            return None
                
        except Exception as e:
            logger.error(f"Error getting Pinnacle odds for event {event_id}: {e}")
            return None
    
    def get_betbck_odds(self, pinnacle_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get BetBCK odds using the same search-term logic as the POD pipeline."""
        try:
            raw_home = pinnacle_data.get("home", "")
            raw_away = pinnacle_data.get("away", "")
            clean_home = normalize_team_name_for_matching(raw_home)
            clean_away = normalize_team_name_for_matching(raw_away)
            if not clean_home or not clean_away:
                logger.warning(f"[BETBCK-MATCH] Empty cleaned name: raw='{raw_home}' vs '{raw_away}'")
                return None
            search_term = determine_betbck_search_term(raw_home, raw_away)
            logger.info(f"[BETBCK-MATCH] '{clean_home}' vs '{clean_away}' → search: '{search_term}'")
            from betbck_scraper import scrape_betbck_for_game
            betbck_data = scrape_betbck_for_game(clean_home, clean_away, search_term)
            if betbck_data and betbck_data.get("status") == "success":
                logger.info(f"[BETBCK-MATCH] Match found for '{clean_home}' vs '{clean_away}'")
                return betbck_data
            logger.warning(f"[BETBCK-MATCH] No BetBCK data for '{clean_home}' vs '{clean_away}'")
            return None
        except Exception as e:
            logger.error(f"[BETBCK-MATCH] Error getting BetBCK odds: {e}")
            return None
    
    def calculate_ev(self, pinnacle_data: Dict[str, Any], betbck_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate EV for all markets using robust logic from POD Alerts"""
        try:
            logger.info(f"[EV-CALC] Calculating EV for {pinnacle_data.get('home', '')} vs {pinnacle_data.get('away', '')}")
            # pinnacle_data is the inner event detail {"home":..., "periods":{...}}
            # Wrap it back into {"data": {...}} so process_event_odds_for_display can add NVP,
            # then pass the NVP-enriched structure to analyze_markets_for_ev.
            from utils.pod_utils import process_event_odds_for_display
            wrapped = {"data": pinnacle_data}
            processed = process_event_odds_for_display(wrapped)
            # analyze_markets_multi_row handles row_data dispatch and falls back
            # to analyze_markets_for_ev for the full_game row — correct for all cases.
            ev_results = analyze_markets_multi_row(betbck_data, processed)
            if ev_results:
                logger.info(f"[EV-CALC] Found {len(ev_results)} EV opportunities")
                for result in ev_results:
                    logger.debug(f"[EV-CALC] Market: {result.get('market', 'Unknown')}, EV: {result.get('ev', 'N/A')}")
            else:
                logger.info(f"[EV-CALC] No EV opportunities found")
            return ev_results
        except Exception as e:
            logger.error(f"[EV-CALC] Error calculating EV: {e}")
            return []
    
    def run_main_calculation(self, event_ids: List[str]) -> Dict[str, Any]:
        """Run the main calculation logic on the event IDs and return top 10 EV results"""
        try:
            logger.info(f"[MAIN-CALC] Starting main calculation for {len(event_ids)} events...")
            results = []
            processed_count = 0
            successful_matches = 0
            successful_ev_calcs = 0
            for event_id in event_ids:
                try:
                    logger.info(f"[MAIN-CALC] Processing event {event_id} ({processed_count + 1}/{len(event_ids)})")
                    # Get Pinnacle odds for this event
                    pinnacle_data = self.get_pinnacle_event_odds(event_id)
                    if not pinnacle_data:
                        logger.warning(f"[MAIN-CALC] No Pinnacle data for event {event_id}")
                        continue
                    logger.info(f"[MAIN-CALC] Got Pinnacle data for {pinnacle_data.get('home', '')} vs {pinnacle_data.get('away', '')}")
                    # Skip BetBCK scrape if Pinnacle has no markets (pre-event / expired)
                    _num0 = pinnacle_data.get("periods", {}).get("num_0", {})
                    if not (_num0.get("money_line") or _num0.get("spreads") or _num0.get("totals")):
                        logger.info(f"[MAIN-CALC] Skipping {event_id}: Pinnacle returned 0 markets")
                        processed_count += 1
                        continue
                    # Get BetBCK odds for this event
                    betbck_data = self.get_betbck_odds(pinnacle_data)
                    if not betbck_data:
                        logger.warning(f"[MAIN-CALC] No BetBCK data for event {event_id}")
                        continue
                    successful_matches += 1
                    logger.info(f"[MAIN-CALC] Successfully matched event {event_id}")
                    # Calculate EV for all markets
                    ev_results = self.calculate_ev(pinnacle_data, betbck_data)
                    if ev_results:
                        successful_ev_calcs += 1
                        for result in ev_results:
                            # Flatten for frontend: event, league, bet, bet_type, betbck_odds, pin_nvp, ev, sport
                            results.append({
                                "event": result.get("event", f"{pinnacle_data.get('home', '')} vs {pinnacle_data.get('away', '')}"),
                                "league": result.get("league", pinnacle_data.get("league", "")),
                                "bet": result.get("bet", result.get("market", "")),
                                "bet_type": result.get("bet_type", ""),
                                "betbck_odds": result.get("betbck_odds", ""),
                                "pin_nvp": result.get("pinnacle_nvp", ""),
                                "ev": result.get("ev", 0),
                                "sport": result.get("sport", pinnacle_data.get("sport", "Unknown")),
                                "event_id": event_id
                            })
                        logger.info(f"[MAIN-CALC] Event {event_id} has EV opportunities (count: {len(ev_results)})")
                    else:
                        logger.info(f"[MAIN-CALC] Event {event_id} has no EV opportunities")
                    processed_count += 1
                    if processed_count % 10 == 0:
                        logger.info(f"[MAIN-CALC] Progress: {processed_count}/{len(event_ids)} events processed, {successful_matches} matched, {successful_ev_calcs} with EV")
                    # Removed sleep - if needed for rate limiting, should be handled in the API calls themselves
                except Exception as e:
                    logger.error(f"[MAIN-CALC] Error processing event {event_id}: {e}")
                    continue
            # Sort by EV and return top 10
            results.sort(key=lambda x: x.get("ev", 0), reverse=True)
            top_10 = results[:10]
            self.save_results(top_10)
            logger.info(f"[MAIN-CALC] Main calculation completed:")
            logger.info(f"[MAIN-CALC] - Total events: {len(event_ids)}")
            logger.info(f"[MAIN-CALC] - Processed: {processed_count}")
            logger.info(f"[MAIN-CALC] - Successfully matched: {successful_matches}")
            logger.info(f"[MAIN-CALC] - Events with EV: {successful_ev_calcs}")
            logger.info(f"[MAIN-CALC] - Match rate: {successful_matches/len(event_ids)*100:.1f}%")
            logger.info(f"[MAIN-CALC] - EV rate: {successful_ev_calcs/len(event_ids)*100:.1f}%")
            return {
                "events": top_10,
                "total_processed": processed_count,
                "total_matched": successful_matches,
                "total_with_ev": successful_ev_calcs,
                "match_rate": successful_matches/len(event_ids)*100 if event_ids else 0,
                "ev_rate": successful_ev_calcs/len(event_ids)*100 if event_ids else 0,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"[MAIN-CALC] Error in main calculation: {e}")
            return {"error": str(e)}
    
    def save_results(self, results: List[Dict[str, Any]]) -> bool:
        """Save calculation results to file"""
        try:
            data = {
                "results": results,
                "timestamp": datetime.now().isoformat(),
                "count": len(results)
            }
            
            with open(self.results_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(results)} results to {self.results_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return False
    
    def load_results(self) -> Optional[List[Dict[str, Any]]]:
        """Load calculation results from file"""
        try:
            if not self.results_file.exists():
                return None
            
            with open(self.results_file, 'r') as f:
                data = json.load(f)
            
            return data.get("results", [])
            
        except Exception as e:
            logger.error(f"Error loading results: {e}")
            return None

# Global instance
buckeye_scraper = None

def get_buckeye_scraper(config: Dict[str, Any]) -> BuckeyeScraper:
    """Get or create BuckeyeScraper instance"""
    global buckeye_scraper
    if buckeye_scraper is None:
        buckeye_scraper = BuckeyeScraper(config)
    return buckeye_scraper 