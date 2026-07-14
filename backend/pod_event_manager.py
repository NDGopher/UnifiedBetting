import time
import threading
import logging
import copy
import random
from typing import Dict, Set, Any
from pinnacle_fetcher import fetch_live_pinnacle_event_odds
from utils import process_event_odds_for_display
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)

class PodEventManager:
    def __init__(self):
        self._active_events_lock = threading.Lock()
        self._dismissed_events_lock = threading.Lock()
        self._active_events: Dict[str, Dict[str, Any]] = {}
        self._dismissed_event_ids: Set[str] = set()
        self.EVENT_DATA_EXPIRY_SECONDS = 300
        self.BACKGROUND_REFRESH_INTERVAL_SECONDS = 5  # Set to 5 seconds for faster updates
        self._event_locks = defaultdict(threading.Lock)
        # Add async lock for async operations
        self._async_lock = asyncio.Lock()
        # Per-event backoff state to avoid blocking and reduce API pressure
        # Structure: { event_id: { 'attempts': int, 'next_ts': float } }
        self._event_backoff_state: Dict[str, Dict[str, float]] = {}
        self.BETBCK_REFRESH_INTERVAL_SECONDS = 90
        self._betbck_last_refresh: Dict[str, float] = {}
        self._betbck_refresh_in_progress: Set[str] = set()

    def get_event_lock(self, event_id: str):
        return self._event_locks[event_id]

    def get_active_events(self) -> Dict[str, Dict[str, Any]]:
        with self._active_events_lock:
            # Use shallow copy for better performance - deep copy only when needed
            return dict(self._active_events)

    def add_active_event(self, event_id: str, event_data: Dict[str, Any]) -> None:
        with self._active_events_lock:
            self._active_events[event_id] = event_data
        broadcast_all_active_events()

    def remove_active_event(self, event_id: str, broadcast_function=None) -> None:
        with self._active_events_lock:
            if event_id in self._active_events:
                logger.info(f"[PodEventManager] Removing active event: {event_id}")
                self._active_events.pop(event_id, None)
                
                # Send removal notification to frontend if broadcast function is available
                if broadcast_function:
                    try:
                        # Send a removal message to the frontend
                        broadcast_function(event_id, {"removed": True})
                        print(f"[PodEventManager] Sent removal notification for event {event_id}")
                    except Exception as e:
                        print(f"[PodEventManager] Error sending removal notification for event {event_id}: {e}")
            else:
                logger.debug(f"[PodEventManager] Event {event_id} not found in active events")

    def is_event_dismissed(self, event_id: str) -> bool:
        with self._dismissed_events_lock:
            return event_id in self._dismissed_event_ids

    def add_dismissed_event(self, event_id: str) -> None:
        with self._dismissed_events_lock:
            self._dismissed_event_ids.add(event_id)

    def remove_dismissed_event(self, event_id: str) -> None:
        with self._dismissed_events_lock:
            self._dismissed_event_ids.discard(event_id)

    def update_event_data(self, event_id: str, update_data: Dict[str, Any]) -> None:
        with self._active_events_lock:
            if event_id in self._active_events:
                self._active_events[event_id].update(update_data)
        broadcast_all_active_events()

    async def _async_refresh_betbck(self, event_id: str, cleaned_home: str, cleaned_away: str,
                                       pinnacle_snapshot: dict, broadcast_function):
        """Non-blocking BetBCK re-scrape every BETBCK_REFRESH_INTERVAL_SECONDS seconds per event."""
        try:
            from betbck_request_manager import scrape_betbck_for_game_queued
            from utils.pod_utils import analyze_markets_for_ev
            from main_logic import determine_betbck_search_term

            search_result = determine_betbck_search_term(cleaned_home, cleaned_away)
            search_term = search_result[0] if isinstance(search_result, tuple) else search_result
            if not search_term:
                print(f"[BetBCKRefresh] Could not determine search term for event {event_id}, skipping")
                return

            print(f"[BetBCKRefresh] Re-scraping BetBCK for {event_id}: '{cleaned_home}' vs '{cleaned_away}' (term: '{search_term}')")

            loop = asyncio.get_event_loop()
            fresh_game_data = await loop.run_in_executor(
                None,
                lambda: scrape_betbck_for_game_queued(cleaned_home, cleaned_away, search_term, event_id)
            )

            if not fresh_game_data or (isinstance(fresh_game_data, dict) and fresh_game_data.get("status") == "error"):
                print(f"[BetBCKRefresh] No data returned for event {event_id}, keeping existing BetBCK data")
                return

            fresh_bets = analyze_markets_for_ev(fresh_game_data, pinnacle_snapshot)
            realistic_bets = []
            for bet in fresh_bets:
                try:
                    ev_val = float(bet.get("ev", "0").replace('%', ''))
                    if -30 <= ev_val <= 30:
                        realistic_bets.append(bet)
                    else:
                        print(f"[BetBCKRefresh] Filtering unrealistic EV: {bet.get('ev')} for {bet.get('market')} {bet.get('selection')}")
                except Exception:
                    realistic_bets.append(bet)

            if not realistic_bets:
                print(f"[BetBCKRefresh] No realistic bets after BetBCK refresh for event {event_id}")
                return

            fresh_game_data["potential_bets_analyzed"] = realistic_bets
            fresh_betbck_result = {"status": "success", "data": fresh_game_data}

            updated_pinnacle = dict(pinnacle_snapshot) if pinnacle_snapshot else {}
            updated_pinnacle["markets"] = realistic_bets

            print(f"[BetBCKRefresh] Updating event {event_id} with fresh BetBCK data ({len(realistic_bets)} markets)")
            self.update_event_data(event_id, {
                "betbck_data": fresh_betbck_result,
                "betbck_last_update": time.time(),
                "pinnacle_data_processed": updated_pinnacle,
            })

            if broadcast_function:
                current_event = self.get_active_events().get(event_id)
                if current_event:
                    broadcast_function(event_id, current_event)
                    print(f"[BetBCKRefresh] Broadcast sent for event {event_id}")

        except Exception as e:
            print(f"[BetBCKRefresh] Error for event {event_id}: {e}")
            logger.error(f"[BetBCKRefresh] Error for event {event_id}: {e}")
        finally:
            self._betbck_refresh_in_progress.discard(event_id)

    async def background_event_refresher(self, broadcast_function=None):
        print("[BackgroundRefresher] Background event refresher started (ASYNC)")
        logger.info("[BackgroundRefresher] Background event refresher started (ASYNC)")
        
        if broadcast_function is None:
            print("[BackgroundRefresher] No broadcast function provided - updates will not be sent!")
            logger.error("[BackgroundRefresher] No broadcast function provided - updates will not be sent!")
        else:
            print("[BackgroundRefresher] Broadcast function available - updates will be sent when odds change")
            logger.info("[BackgroundRefresher] Broadcast function available - updates will be sent when odds change")
        
        print("[BackgroundRefresher] Starting main loop...")
        loop_count = 0
        while True:
            try:
                await asyncio.sleep(self.BACKGROUND_REFRESH_INTERVAL_SECONDS)
                loop_count += 1
                current_time = time.time()
                active_events = self.get_active_events()
                
                # Log every 20 loops (every minute) to confirm it's running
                if loop_count % 20 == 0:
                    logger.info(f"[BackgroundRefresher] Loop #{loop_count} - Processing {len(active_events)} active events")
                    print(f"[BackgroundRefresher] Loop #{loop_count} - Processing {len(active_events)} active events")
                    
                    # FORCED CLEANUP: Remove any expired events that might have been missed
                    events_to_remove = []
                    for event_id, event_data in active_events.items():
                        try:
                            alert_age = current_time - event_data.get("alert_arrival_timestamp", 0)
                            markets = event_data.get("pinnacle_data_processed", {}).get("markets", [])
                            
                            # Check if all markets have negative EV
                            all_negative_ev = True
                            if markets:
                                for market in markets:
                                    ev_str = market.get("ev", "0")
                                    try:
                                        ev_value = float(ev_str.replace('%', ''))
                                        if ev_value > 0:
                                            all_negative_ev = False
                                            break
                                    except:
                                        pass
                            
                            # Check if event should be expired
                            expiry_time = 60 if all_negative_ev else 180
                            if alert_age > expiry_time:
                                print(f"[BackgroundRefresher] FORCED CLEANUP: Event {event_id} is {alert_age:.1f}s old (limit: {expiry_time}s), removing...")
                                events_to_remove.append(event_id)
                        except Exception as e:
                            print(f"[BackgroundRefresher] Error checking event {event_id} for cleanup: {e}")
                    
                    # Remove expired events (thread-safe)
                    for event_id in events_to_remove:
                        self.remove_active_event(event_id, broadcast_function)
                    
                    # Only broadcast events that are still being updated (not expired or too old)
                    if broadcast_function and active_events:
                        active_count = 0
                        for event_id, event_data in active_events.items():
                            try:
                                # Check if event is still being updated
                                alert_age = current_time - event_data.get("alert_arrival_timestamp", 0)
                                markets = event_data.get("pinnacle_data_processed", {}).get("markets", [])
                                
                                # Check if all markets have negative EV
                                all_negative_ev = True
                                if markets:
                                    for market in markets:
                                        ev_str = market.get("ev", "0")
                                        try:
                                            ev_value = float(ev_str.replace('%', ''))
                                            if ev_value > 0:
                                                all_negative_ev = False
                                                break
                                        except:
                                            pass
                                
                                # Only broadcast if event is still being updated
                                if not (all_negative_ev and alert_age > 60):
                                    broadcast_function(event_id, event_data)
                                    active_count += 1
                            except Exception as e:
                                print(f"[BackgroundRefresher] Error broadcasting event {event_id}: {e}")
                        
                        if active_count > 0:
                            print(f"[BackgroundRefresher] Broadcasted {active_count} active events to frontend")
                        else:
                            print(f"[BackgroundRefresher] No active events to broadcast (all are expired or too old)")
                else:
                    print(f"[BackgroundRefresher] Loop #{loop_count} - sleeping for {self.BACKGROUND_REFRESH_INTERVAL_SECONDS} seconds...")
                
                for event_id, event_data in active_events.items():
                    try:
                        # Per-event backoff: skip events that are cooling down
                        state = self._event_backoff_state.get(event_id, {"attempts": 0, "next_ts": 0.0})
                        if current_time < state.get("next_ts", 0.0):
                            remaining = state["next_ts"] - current_time
                            print(f"[BackgroundRefresher] Event {event_id} in backoff for {remaining:.1f}s, skipping this cycle")
                            continue

                        # Validate event data structure before processing
                        if not event_data or "pinnacle_data_processed" not in event_data or event_data["pinnacle_data_processed"] is None:
                            print(f"[BackgroundRefresher] Event {event_id} has corrupted data structure, removing...")
                            self.remove_active_event(event_id, broadcast_function)
                            continue
                        
                        # Check if event has expired - faster expiration for negative EV alerts
                        alert_age = current_time - event_data.get("alert_arrival_timestamp", 0)
                        
                        # Check if this is a negative EV alert (all markets have negative EV)
                        markets = event_data.get("pinnacle_data_processed", {}).get("markets", [])
                        all_negative_ev = True
                        if markets:
                            for market in markets:
                                ev_str = market.get("ev", "0")
                                try:
                                    ev_value = float(ev_str.replace('%', ''))
                                    if ev_value > 0:
                                        all_negative_ev = False
                                        break
                                except:
                                    pass
                        
                        # Expire negative EV alerts after 60 seconds, positive EV alerts after 3 minutes
                        expiry_time = 60 if all_negative_ev else 180

                        # Stop refreshing negative EV alerts after 60 seconds
                        if all_negative_ev and alert_age > 60:
                            print(f"[BackgroundRefresher] Event {event_id} is negative EV and older than 60s, skipping updates (age: {alert_age:.1f}s)")
                            continue
                        
                        # Remove expired alerts (thread-safe)
                        if alert_age > expiry_time:
                            print(f"[BackgroundRefresher] Event {event_id} has expired (age: {alert_age:.1f}s, limit: {expiry_time}s, negative_ev: {all_negative_ev}), removing...")
                            self.remove_active_event(event_id, broadcast_function)
                            continue
                        
                        try:
                            # Fetch previous odds/EV for comparison
                            prev_markets = event_data.get("pinnacle_data_processed", {}).get("markets", [])
                            prev_nvp_map = { (m.get("market"), m.get("selection"), m.get("line")): m.get("pinnacle_nvp") for m in prev_markets }
                            prev_ev_map = { (m.get("market"), m.get("selection"), m.get("line")): m.get("ev") for m in prev_markets }

                            pinnacle_api_result = fetch_live_pinnacle_event_odds(event_id)
                            
                            if pinnacle_api_result and pinnacle_api_result.get("success"):
                                print(f"[BackgroundRefresher] [SUCCESS] Pinnacle API call successful for {event_id}")
                                # Process the new odds - use SAME pipeline as initial alert
                                processed_odds = process_event_odds_for_display(pinnacle_api_result.get("data"))
                                
                                # DEBUG: Log what Swordfish returned
                                raw_data = pinnacle_api_result.get("data", {})
                                print(f"[BackgroundRefresher] DEBUG: Swordfish returned {len(raw_data.get('markets', []))} markets")
                                if raw_data.get('markets'):
                                    print(f"[BackgroundRefresher] DEBUG: ALL MARKETS FROM SWORDFISH for {event_id}:")
                                    for i, market in enumerate(raw_data['markets']):
                                        print(f"  Market {i}: {market.get('market')} {market.get('selection')} Line: {market.get('line')} NVP: {market.get('pinnacle_nvp')}")
                                
                                # Log the actual odds being fetched
                                new_markets = processed_odds.get("markets", [])
                                if new_markets:
                                    sample_market = new_markets[0]
                                    print(f"[BackgroundRefresher] Fetched fresh odds for {event_id}:")
                                    print(f"  Market: {sample_market.get('market', 'N/A')}")
                                    print(f"  Selection: {sample_market.get('selection', 'N/A')}")
                                    print(f"  NVP: {sample_market.get('pinnacle_nvp', 'N/A')}")
                                    print(f"  EV: {sample_market.get('ev', 'N/A')}")
                                    print(f"  BetBCK: {sample_market.get('betbck_odds', 'N/A')}")
                                
                                # Work on a deep copy to prevent cross-contamination across iterations
                                working_event_data = copy.deepcopy(event_data)
                                # Update the event data with new odds - ALWAYS update timestamp
                                working_event_data["pinnacle_data_processed"] = processed_odds
                                working_event_data["last_update"] = int(current_time)
                                working_event_data["last_pinnacle_data_update_timestamp"] = int(current_time)
                                
                                # Re-analyze markets for EV with fresh Pinnacle odds and existing BetBCK data
                                try:
                                    from utils.pod_utils import analyze_markets_for_ev
                                    betbck_data = working_event_data.get("betbck_data", {}).get("data", {})
                                    
                                    # Guard: skip EV re-analysis if Swordfish returned data for a
                                    # different game (wrong event ID captured by the extension).
                                    _sw_raw = pinnacle_api_result.get("data", {}) or {}
                                    _sw_home = (_sw_raw.get("home") or "").lower().strip()
                                    _sw_away = (_sw_raw.get("away") or "").lower().strip()
                                    _ev_home = (working_event_data.get("cleaned_home_team") or "").lower().strip()
                                    _ev_away = (working_event_data.get("cleaned_away_team") or "").lower().strip()
                                    _teams_match = True
                                    if _sw_home and _sw_away and _ev_home and _ev_away:
                                        # Simple token overlap check — same as Layer 0 in main.py
                                        def _tok(s): return set(s.replace("-", " ").split())
                                        _h_overlap = len(_tok(_sw_home) & _tok(_ev_home)) / max(len(_tok(_ev_home)), 1)
                                        _a_overlap = len(_tok(_sw_away) & _tok(_ev_away)) / max(len(_tok(_ev_away)), 1)
                                        _h2_overlap = len(_tok(_sw_home) & _tok(_ev_away)) / max(len(_tok(_ev_away)), 1)
                                        _a2_overlap = len(_tok(_sw_away) & _tok(_ev_home)) / max(len(_tok(_ev_home)), 1)
                                        _best_fwd = min(_h_overlap, _a_overlap)
                                        _best_rev = min(_h2_overlap, _a2_overlap)
                                        if max(_best_fwd, _best_rev) < 0.4:
                                            _teams_match = False
                                            print(f"[BackgroundRefresher] TEAM MISMATCH for {event_id}: "
                                                  f"Swordfish returned '{_sw_home}' vs '{_sw_away}' "
                                                  f"but expected '{_ev_home}' vs '{_ev_away}' — "
                                                  f"reverting pinnacle_data_processed to prevent cross-game EV")
                                            # CRITICAL: revert pinnacle_data_processed to the original
                                            # stub/old data.  The wrong game's Pinnacle NVPs were already
                                            # written at line 321; if we leave them there, build_event_object
                                            # will calculate EV by mixing them with this game's BetBCK odds
                                            # and produce completely false high-EV rows.
                                            working_event_data["pinnacle_data_processed"] = \
                                                event_data.get("pinnacle_data_processed", {})

                                    if betbck_data and processed_odds and _teams_match:
                                        print(f"[BackgroundRefresher] Re-analyzing markets for EV with fresh Pinnacle odds")
                                        fresh_potential_bets = analyze_markets_for_ev(betbck_data, processed_odds)
                                        
                                        # Filter out unrealistic EVs (outside ±30% range)
                                        realistic_bets = []
                                        for bet in fresh_potential_bets:
                                            try:
                                                ev_str = bet.get("ev", "0")
                                                ev_value = float(ev_str.replace('%', ''))
                                                if -30 <= ev_value <= 30:
                                                    realistic_bets.append(bet)
                                                else:
                                                    print(f"[BackgroundRefresher] Filtering out unrealistic EV: {ev_str} for {bet.get('market', 'N/A')} {bet.get('selection', 'N/A')}")
                                            except:
                                                realistic_bets.append(bet)  # Keep if we can't parse EV
                                        
                                        # Update the processed odds with fresh EV calculations
                                        processed_odds["markets"] = realistic_bets
                                        working_event_data["pinnacle_data_processed"] = processed_odds
                                        
                                        # NEW: Sync the fresh markets back to betbck_data so build_event_object uses them
                                        if "betbck_data" in working_event_data and "data" in working_event_data["betbck_data"]:
                                            working_event_data["betbck_data"]["data"]["potential_bets_analyzed"] = realistic_bets
                                            print(f"[BackgroundRefresher] Synced fresh markets to betbck_data for {event_id}")
                                        
                                        print(f"[BackgroundRefresher] Updated EV analysis: {len(realistic_bets)} realistic bets found")
                                    else:
                                        print(f"[BackgroundRefresher] No BetBCK data available for EV re-analysis")
                                except Exception as ev_error:
                                    print(f"[BackgroundRefresher] Error re-analyzing EV: {ev_error}")
                                    logger.error(f"[BackgroundRefresher] Error re-analyzing EV: {ev_error}")
                                
                                # Compare new odds/EV with previous
                                new_markets = processed_odds.get("markets", [])
                                new_nvp_map = { (m.get("market"), m.get("selection"), m.get("line")): m.get("pinnacle_nvp") for m in new_markets }
                                new_ev_map = { (m.get("market"), m.get("selection"), m.get("line")): m.get("ev") for m in new_markets }
                                
                                odds_changed = False
                                ev_changed = False
                                changes_found = []
                                
                                # DEBUG: Log all market data to see what's happening
                                print(f"[BackgroundRefresher] DEBUG: Checking {len(new_markets)} markets for {event_id}")
                                for i, market in enumerate(new_markets[:3]):  # Log first 3 markets
                                    print(f"[BackgroundRefresher] Market {i}: {market.get('market')} {market.get('selection')} NVP: {market.get('pinnacle_nvp')} EV: {market.get('ev')}")
                                
                                print(f"[BackgroundRefresher] Comparing odds for {event_id}:")
                                for key in new_nvp_map:
                                    old_nvp = prev_nvp_map.get(key)
                                    new_nvp = new_nvp_map[key]
                                    if old_nvp != new_nvp:
                                        odds_changed = True
                                        changes_found.append(f"NVP {key}: {old_nvp} -> {new_nvp}")
                                        print(f"  [CHANGE] NVP CHANGE: {key} {old_nvp} -> {new_nvp}")
                                    else:
                                        print(f"  [SAME] NVP SAME: {key} = {new_nvp}")
                                
                                for key in new_ev_map:
                                    old_ev = prev_ev_map.get(key)
                                    new_ev = new_ev_map[key]
                                    if old_ev != new_ev:
                                        ev_changed = True
                                        changes_found.append(f"EV {key}: {old_ev} -> {new_ev}")
                                        print(f"  [CHANGE] EV CHANGE: {key} {old_ev} -> {new_ev}")
                                    else:
                                        print(f"  [SAME] EV SAME: {key} = {new_ev}")
                                
                                if changes_found:
                                    print(f"[CHANGES] [BackgroundRefresher] ODDS CHANGES DETECTED for {event_id}:")
                                    for change in changes_found:
                                        print(f"  [CHANGE] {change}")
                                    print(f"[BROADCAST] [BackgroundRefresher] Broadcasting changes to frontend...")
                                else:
                                    print(f"[STABLE] [BackgroundRefresher] No odds changes for {event_id} (all values stable)")
                                
                                # Always broadcast to show the system is working (even if no changes)
                                if broadcast_function:
                                    # Log some key odds for debugging
                                    sample_market = new_markets[0] if new_markets else {}
                                    print(f"[BackgroundRefresher] Broadcasting update for event {event_id}")
                                    print(f"[BackgroundRefresher] Sample odds: {sample_market.get('market', 'N/A')} {sample_market.get('selection', 'N/A')} NVP: {sample_market.get('pinnacle_nvp', 'N/A')} EV: {sample_market.get('ev', 'N/A')}")
                                    print(f"[BackgroundRefresher] Total markets to broadcast: {len(new_markets)}")
                                    
                                    # IMPORTANT: Pass the raw event_data to broadcast function
                                    # The broadcast function will call build_event_object internally
                                    try:
                                        print(f"[BackgroundRefresher] Broadcasting update for event {event_id}")
                                        broadcast_function(event_id, working_event_data)
                                        print(f"[BackgroundRefresher] SUCCESS: Successfully broadcasted update for event {event_id}")
                                    except Exception as broadcast_error:
                                        print(f"[BackgroundRefresher] ERROR broadcasting for {event_id}: {broadcast_error}")
                                else:
                                    print(f"[BackgroundRefresher] No broadcast function available for event {event_id}")
                                
                                # Update the manager with the synced data (thread-safe) - ALWAYS persist
                                self.update_event_data(event_id, {
                                    "pinnacle_data_processed": working_event_data.get("pinnacle_data_processed"),
                                    "betbck_data": working_event_data.get("betbck_data"),
                                    "last_update": int(current_time),
                                    "last_pinnacle_data_update_timestamp": int(current_time)
                                })
                                print(f"[BackgroundRefresher] SUCCESS: Updated event data in manager for event {event_id}")

                                # Reset backoff on success
                                self._event_backoff_state[event_id] = {"attempts": 0, "next_ts": 0.0}
                            else:
                                print(f"[BackgroundRefresher] [FAILED] Pinnacle API call failed for {event_id}: {pinnacle_api_result}")
                                # Schedule per-event backoff on failure
                                state = self._event_backoff_state.get(event_id, {"attempts": 0, "next_ts": 0.0})
                                attempts = int(state.get("attempts", 0))
                                delay = min(30.0, float(2 ** min(attempts, 4))) + random.uniform(0.1, 0.5)
                                self._event_backoff_state[event_id] = {"attempts": attempts + 1, "next_ts": current_time + delay}
                                print(f"[BackgroundRefresher] Backing off {delay:.1f}s for event {event_id} (attempts={attempts + 1})")
                                continue
                                
                        except Exception as e:
                            print(f"[BackgroundRefresher] Error processing event {event_id}: {e}")
                            logger.error(f"[BackgroundRefresher] Error processing event {event_id}: {e}")
                            # Schedule per-event backoff on exception
                            state = self._event_backoff_state.get(event_id, {"attempts": 0, "next_ts": 0.0})
                            attempts = int(state.get("attempts", 0))
                            delay = min(30.0, float(2 ** min(attempts, 4))) + random.uniform(0.1, 0.5)
                            self._event_backoff_state[event_id] = {"attempts": attempts + 1, "next_ts": current_time + delay}
                            print(f"[BackgroundRefresher] Backing off {delay:.1f}s for event {event_id} due to error (attempts={attempts + 1})")
                            
                    except Exception as e:
                        print(f"[BackgroundRefresher] Error in event loop for {event_id}: {e}")
                        logger.error(f"[BackgroundRefresher] Error in event loop for {event_id}: {e}")

                    # ── BetBCK periodic refresh (30s for +EV, 90s otherwise) ─────────
                    last_bck = self._betbck_last_refresh.get(event_id, 0)
                    bck_interval = 30 if not all_negative_ev else self.BETBCK_REFRESH_INTERVAL_SECONDS
                    if (current_time - last_bck >= bck_interval
                            and event_id not in self._betbck_refresh_in_progress):
                        current_snap = self.get_active_events().get(event_id)
                        if current_snap:
                            snap_home = current_snap.get("cleaned_home_team", "")
                            snap_away = current_snap.get("cleaned_away_team", "")
                            snap_pinnacle = copy.deepcopy(current_snap.get("pinnacle_data_processed", {}))
                            if snap_home and snap_away:
                                self._betbck_last_refresh[event_id] = current_time
                                self._betbck_refresh_in_progress.add(event_id)
                                elapsed = current_time - last_bck
                                print(f"[BetBCKRefresh] Triggering refresh for {event_id} "
                                      f"({snap_home} vs {snap_away}, {elapsed:.0f}s since last refresh)")
                                asyncio.create_task(self._async_refresh_betbck(
                                    event_id, snap_home, snap_away, snap_pinnacle, broadcast_function
                                ))

            except Exception as e:
                print(f"[BackgroundRefresher] Critical error in main loop: {e}")
                logger.error(f"[BackgroundRefresher] Critical error in main loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

def broadcast_all_active_events():
    """Broadcast all active events to WebSocket clients"""
    try:
        # Use a callback approach instead of direct import to avoid circular dependencies
        logger.info("[PodEventManager] Need to broadcast all active events - will be handled by main.py")
    except Exception as e:
        logger.error(f"[PodEventManager] Error in broadcast_all_active_events: {e}")