from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, RootModel
import json
import asyncio
from datetime import datetime, timezone
import logging
import time
import threading
import traceback
from pod_event_manager import PodEventManager
from main_logic import process_alert_and_scrape_betbck, analyze_markets_for_ev
from odds_processing import fetch_live_pinnacle_event_odds
from utils import process_event_odds_for_display
import copy
from team_utils import match_betbck_to_pinnacle_markets
from utils.pod_utils import clean_pod_team_name_for_search, american_to_decimal, calculate_ev, decimal_to_american, normalize_team_name_for_matching, is_prop_or_corner_alert, determine_betbck_search_term
from pto_scraper import PTOScraper
from thread_safe_manager import event_manager
import gc
import psutil
from websocket_manager import manager
import subprocess
import os
import collections
# from betbck_async_scraper import get_all_betbck_games  # Removed - use async version instead
from betbck_request_manager import betbck_manager
from ace_scraper import AceScraper
from database_models import get_session, HighEVAlert
from config import setup_logging

# Setup proper logging configuration (suppresses Selenium spam)
setup_logging()
logger = logging.getLogger(__name__)

# Pydantic models for type safety
class Market(BaseModel):
    market: str
    selection: str
    line: str
    pinnacle_nvp: str
    betbck_odds: str
    ev: str

class EventData(BaseModel):
    title: str
    meta_info: str
    last_update: int
    alert_description: str
    alert_meta: str
    markets: List[Market]
    alert_arrival_timestamp: int

class EventsResponse(RootModel[dict[str, EventData]]):
    pass

app = FastAPI(title="Unified Betting App")
# Readiness flag used by launcher health checks
setattr(app.state, "ready", False)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lightweight health endpoint for launcher readiness checks
@app.get("/healthz")
async def healthz():
    try:
        return {"status": "ok", "ready": bool(getattr(app.state, "ready", False))}
    except Exception:
        # Never fail healthz
        return {"status": "ok", "ready": False}

# Load configuration
import os
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

pod_event_manager = PodEventManager()
pto_scraper = PTOScraper(config.get("pto", {}))
ace_scraper = AceScraper(config.get("ace", {}))

# Throttle logging for PTO props endpoints
_last_pto_props_log_time = 0
_last_pto_props_ev_log_time = 0
_pto_props_log_lock = threading.Lock()

# Add memory management with throttling
_last_memory_warning_time = 0
_memory_warning_interval = 600  # 10 minutes in seconds

# Add alert rate limiting
_alert_rate_limit_window = 60  # 1 minute window
_alert_rate_limit_max = 10     # Max 10 alerts per minute
_alert_timestamps = []         # Track alert timestamps for rate limiting
_alert_rate_limit_lock = threading.Lock()

def check_alert_rate_limit():
    """Check if we're within the alert rate limit (max 10 alerts per minute)"""
    global _alert_timestamps
    with _alert_rate_limit_lock:
        now = time.time()
        # Remove timestamps older than 1 minute
        _alert_timestamps = [ts for ts in _alert_timestamps if (now - ts) < _alert_rate_limit_window]
        
        # Check if we're at the limit
        if len(_alert_timestamps) >= _alert_rate_limit_max:
            return False
        
        # Add current timestamp
        _alert_timestamps.append(now)
        return True

def check_memory_usage():
    """Check memory usage and trigger cleanup if needed"""
    global _last_memory_warning_time
    try:
        memory = psutil.virtual_memory()
        current_time = time.time()
        
        # Only warn if >90% and haven't warned in last 10 minutes
        if memory.percent > 90 and (current_time - _last_memory_warning_time) > _memory_warning_interval:
            logger.warning(f"[Memory] High memory usage detected: {memory.percent}%")
            _last_memory_warning_time = current_time
            
            # Force garbage collection
            collected = gc.collect()
            logger.info(f"[Memory] Garbage collection freed {collected} objects")
            # Clean up expired events
            event_manager.cleanup_expired_events()
            # Get memory stats after cleanup
            memory_after = psutil.virtual_memory()
            logger.info(f"[Memory] After cleanup: {memory_after.percent}%")
            return True
        return False
    except Exception as e:
        logger.error(f"[Memory] Error checking memory usage: {e}")
        return False

# Add memory monitoring to the background task
def background_memory_monitor():
    """Monitor memory usage and trigger cleanup"""
    while True:
        try:
            time.sleep(300)  # Check every 5 minutes instead of 30 seconds
            check_memory_usage()
        except Exception as e:
            logger.error(f"[MemoryMonitor] Error: {e}")

# Start memory monitor in background
memory_monitor_thread = threading.Thread(target=background_memory_monitor, daemon=True)
memory_monitor_thread.start()

# Global variables for event processing
def queue_factory():
    return asyncio.Queue()

_event_queues = collections.defaultdict(queue_factory)
_event_workers = {}
refresher_running = False
refresher_thread = None
main_event_loop = None

# Track last processed time for each event ID to prevent duplicate processing within 2 minutes
_last_processed_times = {}

async def event_alert_worker(event_id):
    """Background worker for a single event_id, processes alerts in order. Never exits on error."""
    queue = _event_queues[event_id]
    logger.info(f"[PerEventQueue] Worker started for Event ID: {event_id}")
    while True:
        try:
            payload = await queue.get()
            
            # Clear any other alerts in the queue for this event (they're all duplicates)
            while not queue.empty():
                try:
                    old_payload = await queue.get()
                    logger.info(f"[PerEventQueue] Clearing duplicate alert from queue for Event ID: {event_id}")
                except:
                    break
            
            logger.info(f"[PerEventQueue] Got alert for Event ID: {event_id} (homeTeam={payload.get('homeTeam','?')})")
            try:
                lock = pod_event_manager.get_event_lock(event_id)
                logger.info(f"[PerEventQueue] Attempting to acquire lock for Event ID: {event_id}")
                with lock:
                    logger.info(f"[PerEventQueue] Lock acquired for Event ID: {event_id}")
                    logger.info(f"[PerEventQueue] Processing alert for Event ID: {event_id} ({payload.get('homeTeam','?')})")

                    # Update the last processed time BEFORE processing to prevent race conditions
                    now = time.time()
                    _last_processed_times[event_id] = now
                    
                    # Clean up old entries (older than 1 hour) to prevent memory bloat
                    current_time = now
                    old_entries = [eid for eid, timestamp in _last_processed_times.items() 
                                 if current_time - timestamp > 3600]  # 1 hour = 3600 seconds
                    for old_eid in old_entries:
                        del _last_processed_times[old_eid]
                    
                    # Clean up old queues and workers (older than 30 minutes)
                    old_queues = [eid for eid in list(_event_queues.keys()) 
                                if eid not in _last_processed_times or 
                                (current_time - _last_processed_times.get(eid, 0)) > 1800]  # 30 minutes
                    for old_eid in old_queues:
                        if old_eid in _event_queues:
                            del _event_queues[old_eid]
                        if old_eid in _event_workers:
                            del _event_workers[old_eid]

                    active_events = pod_event_manager.get_active_events()
                    if event_id in active_events:
                        last_processed = active_events[event_id].get("last_pinnacle_data_update_timestamp", 0)
                        if (now - last_processed) < 15:
                            logger.info(f"[PerEventQueue] Ignoring duplicate alert for Event ID: {event_id}")
                            continue

                    pinnacle_api_result = fetch_live_pinnacle_event_odds(event_id)
                    live_pinnacle_odds_processed = process_event_odds_for_display(pinnacle_api_result.get("data"))
                    league_name = live_pinnacle_odds_processed.get("league_name", payload.get("leagueName", "Unknown League"))
                    start_time = live_pinnacle_odds_processed.get("starts", payload.get("startTime", "N/A"))

                    pod_home_clean = clean_pod_team_name_for_search(payload.get("homeTeam", ""))
                    pod_away_clean = clean_pod_team_name_for_search(payload.get("awayTeam", ""))

                    betbck_last_update = None
                    if event_id not in active_events:
                        logger.info(f"[PerEventQueue] New event {event_id}. Initiating scrape.")
                        logger.info(f"[PerEventQueue] POD Teams: Home='{payload.get('homeTeam', '?')}', Away='{payload.get('awayTeam', '?')}'")
                        logger.info(f"[PerEventQueue] Cleaned Teams: Home='{pod_home_clean}', Away='{pod_away_clean}'")
                        betbck_result = process_alert_and_scrape_betbck(event_id, payload, live_pinnacle_odds_processed)

                        if not (betbck_result and betbck_result.get("status") == "success"):
                            fail_reason = betbck_result.get("message", "Scraper returned None")
                            logger.error(f"[PerEventQueue] Scrape failed. Dropping alert. Reason: {fail_reason}")
                            logger.error(f"[PerEventQueue] Failed teams: Home='{pod_home_clean}', Away='{pod_away_clean}' (raw: Home='{payload.get('homeTeam', '?')}', Away='{payload.get('awayTeam', '?')}')")
                            continue

                        logger.info(f"[PerEventQueue] Scrape successful. Storing event {event_id} for display.")
                        betbck_last_update = now
                        betbck_data = betbck_result.get("data", {})
                        potential_bets = betbck_data.get("potential_bets_analyzed", [])
                        
                        # Filter out unrealistic EVs (outside ±30% range)
                        realistic_bets = []
                        for bet in potential_bets:
                            try:
                                ev_str = bet.get("ev", "0")
                                ev_value = float(ev_str.replace('%', ''))
                                if -30 <= ev_value <= 30:
                                    realistic_bets.append(bet)
                                else:
                                    logger.warning(f"[PerEventQueue] Filtering out unrealistic EV: {ev_str} for {bet.get('market', 'N/A')} {bet.get('selection', 'N/A')}")
                            except:
                                realistic_bets.append(bet)  # Keep if we can't parse EV
                        
                        has_positive_ev = any(float(b.get("ev", "0").replace('%','')) > 0 for b in realistic_bets)
                        betbck_data["potential_bets_analyzed"] = realistic_bets
                        
                        # Only store and broadcast if we have valid data
                        if not betbck_data or not realistic_bets:
                            logger.warning(f"[PerEventQueue] No valid betting data for event {event_id}, skipping broadcast")
                            continue
                        event_data = {
                            "alert_arrival_timestamp": now,
                            "last_pinnacle_data_update_timestamp": now,
                            "pinnacle_data_processed": live_pinnacle_odds_processed,
                            "original_alert_details": payload,
                            "betbck_data": betbck_result,
                            "league_name": league_name,
                            "start_time": start_time,
                            "old_odds": payload.get("oldOdds", "N/A"),
                            "new_odds": payload.get("newOdds", "N/A"),
                            "no_vig": payload.get("noVigPriceFromAlert", "N/A"),
                            "cleaned_home_team": pod_home_clean,
                            "cleaned_away_team": pod_away_clean,
                            "betbck_last_update": betbck_last_update,
                            "has_positive_ev": has_positive_ev,
                            "ev_rescrape_done": False
                        }
                        pod_event_manager.add_active_event(event_id, event_data)
                        updated_event = pod_event_manager.get_active_events().get(event_id)
                        if updated_event:
                            broadcast_pod_alert_safe(event_id, updated_event)
                    else:
                        logger.info(f"[PerEventQueue] Updating existing event {event_id} with fresh Pinnacle data.")
                        event = active_events[event_id]
                        betbck_data = event.get("betbck_data", {}).get("data", {})
                        potential_bets = betbck_data.get("potential_bets_analyzed", [])
                        has_positive_ev = event.get("has_positive_ev", False) or any(float(b.get("ev", "0").replace('%','')) > 0 for b in potential_bets)
                        pod_event_manager.update_event_data(event_id, {
                            "last_pinnacle_data_update_timestamp": now,
                            "pinnacle_data_processed": live_pinnacle_odds_processed,
                            "has_positive_ev": has_positive_ev
                        })
                        updated_event = pod_event_manager.get_active_events().get(event_id)
                        if updated_event:
                            broadcast_pod_alert_safe(event_id, updated_event)
                logger.info(f"[PerEventQueue] Lock released for Event ID: {event_id}")
            except Exception as e:
                logger.error(f"[PerEventQueue] Error processing alert for {event_id}: {e}")
                traceback.print_exc()
        except Exception as outer_e:
            logger.error(f"[PerEventQueue] OUTER error in worker for {event_id}: {outer_e}")
            traceback.print_exc()
        # Always continue loop, never exit

@app.on_event("startup")
async def startup_event():
    global main_event_loop, refresher_running, refresher_thread
    main_event_loop = asyncio.get_running_loop()
    
    print("FASTAPI STARTUP EVENT FIRED!")
    logger.info("FASTAPI STARTUP EVENT FIRED!")
    
    logger.info("\n=== Starting up Unified Betting App ===")
    logger.info("Initializing services...")
    logger.info("Background event refresher started")

    # Start the refresher thread for real-time updates
    def start_background_refresher():
        global refresher_running
        print("[BackgroundRefresher] Thread refresher starting from FastAPI startup event...")
        logger.info("[BackgroundRefresher] Thread refresher starting from FastAPI startup event...")
        try:
            print("[BackgroundRefresher] About to call background_event_refresher...")
            logger.info("[BackgroundRefresher] Calling background_event_refresher...")
            refresher_running = True
            # Run the async function in a new event loop for the thread
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(pod_event_manager.background_event_refresher(broadcast_pod_alert_safe))
        except Exception as e:
            print(f"[BackgroundRefresher] Critical error: {e}")
            logger.error(f"[BackgroundRefresher] Critical error: {e}")
            refresher_running = False
            import traceback
            traceback.print_exc()
    
    print("About to start refresher thread...")
    # Create thread instead of async task
    refresher_thread = threading.Thread(target=start_background_refresher, daemon=True)
    refresher_thread.start()
    print("Refresher thread created and started")
    logger.info("[BackgroundRefresher] Thread launched successfully from FastAPI startup event")
    print("[BackgroundRefresher] Thread launched successfully from FastAPI startup event")
    
    print("BACKEND STARTUP COMPLETE - Refresher thread should be running!")
    logger.info("BACKEND STARTUP COMPLETE - Refresher thread should be running!")
    print("WEBSOCKET server ready on port 5001")
    print("Background refresher thread launched")
    print("Watch for '[BackgroundRefresher]' messages in console for real-time updates")
    print("=" * 60)

    logger.info("Server ready to receive alerts on port 5001")
    
    # Auto-start PTO scraper on backend startup
    logger.info("Auto-starting PTO scraper...")
    try:
        pto_scraper.start_scraping()
        logger.info("PTO scraper auto-started successfully")
    except Exception as e:
        logger.error(f"Failed to auto-start PTO scraper: {e}")
    
    logger.info("=====================================")
    # Mark app as ready for launcher health check
    try:
        setattr(app.state, "ready", True)
    except Exception:
        pass

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Unified Betting App...")
    pto_scraper.stop_scraping()
    logger.info("PTO scraper stopped")



@app.post("/pod_alert")
async def handle_pod_alert(request: Request):
    logger.info("=== [DEBUG] /pod_alert called ===")
    try:
        payload = await request.json()
        event_id_str = str(payload.get("eventId"))
        logger.info(f"[PerEventQueue][DIAG] Incoming alert payload: {payload}")
        if not event_id_str:
            logger.error("[Server-PodAlert] Missing eventId in payload")
            return JSONResponse({"status": "error", "message": "Missing eventId"}, status_code=400)

        # CRITICAL: Check for prop bets FIRST - reject immediately without any processing
        home_team = payload.get("homeTeam", "")
        away_team = payload.get("awayTeam", "")
        prop_keywords = ['(Corners)', '(Bookings)', '(Hits+Runs+Errors)', '(Cards)', '(Fouls)', '(Shots)', '(Assists)', '(Rebounds)', '(Points)', '(Goals)']
        
        if any(keyword.lower() in home_team.lower() for keyword in prop_keywords) or \
           any(keyword.lower() in away_team.lower() for keyword in prop_keywords):
            logger.info(f"[PerEventQueue] REJECTING prop bet alert for Event ID: {event_id_str} - {home_team} vs {away_team}")
            return JSONResponse({
                "status": "success", 
                "message": f"Prop bet alert for {event_id_str} ignored (not supported)"
            })

        # CRITICAL: Check if BetBCK is rate limited - reject immediately
        if betbck_manager.rate_limited:
            logger.warning(f"[PerEventQueue] REJECTING alert for Event ID: {event_id_str} - BetBCK is rate limited")
            return JSONResponse({
                "status": "error", 
                "message": "BetBCK is rate limited - alert rejected to prevent further issues"
            }, status_code=429)

        # CRITICAL: Check alert rate limiting (max 10 alerts per minute)
        if not check_alert_rate_limit():
            logger.warning(f"[PerEventQueue] REJECTING alert for Event ID: {event_id_str} - Alert rate limit exceeded (max 10 per minute)")
            return JSONResponse({
                "status": "error", 
                "message": "Alert rate limit exceeded - too many alerts in the last minute"
            }, status_code=429)

        # CRITICAL: Check deduplication BEFORE queuing to prevent rate limiting
        now = time.time()
        last_processed = _last_processed_times.get(event_id_str, 0)
        time_since_last = now - last_processed
        
        if time_since_last < 120:  # 2 minutes = 120 seconds
            logger.info(f"[PerEventQueue] REJECTING duplicate alert for Event ID: {event_id_str} - processed {time_since_last:.1f}s ago (< 2 minutes)")
            return JSONResponse({
                "status": "success", 
                "message": f"Duplicate alert for {event_id_str} rejected (processed {time_since_last:.1f}s ago)"
            })

        logger.info(f"[PerEventQueue][DIAG] Queuing alert for Event ID: {event_id_str}")
        
        # Save high EV alerts to database (>3% EV) - ULTRA SAFE MODE
        try:
            ev_value = payload.get("ev", 0)
            if isinstance(ev_value, str):
                ev_value = float(ev_value.replace('%', ''))
            
            if ev_value > 3.0:
                try:
                    # Extra safety: wrap in try-catch with timeout
                    import threading
                    
                    def save_alert_with_timeout():
                        try:
                            session = get_session()
                            alert = HighEVAlert(
                                event_id=event_id_str,
                                sport=payload.get("sport", "Unknown"),
                                away_team=payload.get("awayTeam", "Unknown"),
                                home_team=payload.get("homeTeam", "Unknown"),
                                ev_percentage=ev_value,
                                bet_type=payload.get("bet", "N/A"),
                                odds=payload.get("odds", "N/A"),
                                nvp=payload.get("nvp", "N/A"),
                                alert_data=payload
                            )
                            session.add(alert)
                            session.commit()
                            logger.info(f"[Database] Saved high EV alert: {ev_value}% for event {event_id_str}")
                            session.close()
                        except Exception as e:
                            logger.error(f"[Database] Failed to save high EV alert: {e}")
                    
                    # Run database save in separate thread with timeout
                    db_thread = threading.Thread(target=save_alert_with_timeout)
                    db_thread.daemon = True
                    db_thread.start()
                    db_thread.join(timeout=5)  # 5 second timeout
                    
                    if db_thread.is_alive():
                        logger.warning("[Database] Database save timed out, continuing...")
                        
                except Exception as db_error:
                    logger.error(f"[Database] Failed to save high EV alert: {db_error}")
                    # Don't let database errors crash the entire alert processing
        except Exception as db_error:
            logger.error(f"[Database] Error processing high EV alert: {db_error}")
            # Don't let database errors crash the entire alert processing
        
        try:
            # Add alert to per-event queue (defaultdict will create queue if needed)
            queue = _event_queues[event_id_str]
            await queue.put(payload)
            logger.info(f"[PerEventQueue][DIAG] Alert put into queue for Event ID: {event_id_str}")
            
            # Start worker if not already running or if it has exited
            if event_id_str not in _event_workers or _event_workers[event_id_str].done():
                logger.info(f"[PerEventQueue][DIAG] Starting new worker for Event ID: {event_id_str}")
                _event_workers[event_id_str] = asyncio.create_task(event_alert_worker(event_id_str))
            
            return JSONResponse({"status": "success", "message": f"Alert for {event_id_str} queued for processing."})
        except Exception as queue_error:
            logger.error(f"[PerEventQueue] Error queuing alert for {event_id_str}: {queue_error}")
            return JSONResponse({"status": "error", "message": f"Failed to queue alert: {str(queue_error)}"}, status_code=500)
    except Exception as e:
        logger.error(f"[Server-PodAlert] CRITICAL Error in /pod_alert: {e}")
        traceback.print_exc()
        return JSONResponse({"status": "error", "message": f"Internal server error: {str(e)}"}, status_code=500)

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify the server is running"""
    active_events = pod_event_manager.get_active_events()
    return {
        "status": "success",
        "message": "Backend is running!",
        "active_events_count": len(active_events),
        "active_event_ids": list(active_events.keys()),
        "timestamp": time.time()
    }

@app.get("/get_active_events_data")
async def get_active_events_data():
    # logger.info("=== [DEBUG] get_active_events_data called ===")  # Remove log spam
    current_time_sec = time.time()
    data_to_send = {}
    
    # Debug: Log all active events
    active_events = pod_event_manager.get_active_events()
    # logger.info(f"[DEBUG] Total active events in manager: {len(active_events)}")  # Remove log spam
    # logger.info(f"[DEBUG] Active event IDs: {list(active_events.keys())}")  # Remove log spam
    
    for eid, entry in active_events.items():
        # logger.info(f"[DEBUG] Processing event {eid}")  # Remove log spam
        try:
            # Debug: Log entry structure
            # logger.info(f"[DEBUG] Event {eid} entry keys: {list(entry.keys())}")  # Remove log spam
            # logger.info(f"[DEBUG] Event {eid} betbck_data status: {entry.get('betbck_data', {}).get('status', 'NO_BETBCK_DATA')}")  # Remove log spam
            
            if entry["betbck_data"].get("status") != "success":
                logger.warning(f"[GetActiveEvents] Skipping event {eid} due to failed BetBCK scrape: {entry['betbck_data'].get('message', 'No message')}")
                continue
                
            if (current_time_sec - entry.get("alert_arrival_timestamp", 0)) > pod_event_manager.EVENT_DATA_EXPIRY_SECONDS:
                # logger.info(f"[DEBUG] Event {eid} expired (age: {current_time_sec - entry.get('alert_arrival_timestamp', 0)}s)")  # Remove log spam
                continue
                
            data_to_send[eid] = build_event_object(eid, entry)
        except Exception as e:
            logger.error(f"[GetActiveEvents] Error processing event {eid}: {e}\n{traceback.format_exc()}")
            continue
    expired_ids = set(pod_event_manager.get_active_events().keys()) - set(data_to_send.keys())
    for eid in expired_ids:
        pod_event_manager.remove_active_event(eid)
    # logger.info(f"[GetActiveEvents] Returning {len(data_to_send)} active events")  # Remove log spam
    # logger.info(f"[DEBUG] Final data_to_send keys: {list(data_to_send.keys())}")  # Remove log spam
    # logger.info("=== [DEBUG] get_active_events_data returning ===")  # Remove log spam
    return JSONResponse(data_to_send)

@app.get("/pto/props")
async def get_pto_props():
    try:
        result = pto_scraper.get_live_props()
        if result['data']['total_count'] > 0:
            global _last_pto_props_log_time
            now = time.time()
            with _pto_props_log_lock:
                if now - _last_pto_props_log_time > 20:
                    logger.info(f"[DEBUG] Returning {result['data']['total_count']} PTO props")
                    _last_pto_props_log_time = now
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[ERROR] Error getting PTO props: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/pto/props/ev/{min_ev}")
async def get_pto_props_by_ev(min_ev: float = 0.0):
    try:
        result = pto_scraper.get_props_by_ev_threshold(min_ev)
        if result['data']['total_count'] > 0:
            global _last_pto_props_ev_log_time
            now = time.time()
            with _pto_props_log_lock:
                if now - _last_pto_props_ev_log_time > 20:
                    logger.info(f"[DEBUG] Returning {result['data']['total_count']} PTO props with EV >= {min_ev}%")
                    _last_pto_props_ev_log_time = now
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[ERROR] Error getting PTO props by EV: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/pto/scraper/start")
async def start_pto_scraper():
    """Manually start the PTO scraper"""
    logger.info("=== [DEBUG] /pto/scraper/start called ===")
    try:
        pto_scraper.start_scraping()
        return JSONResponse({"status": "success", "message": "PTO scraper started"})
    except Exception as e:
        logger.error(f"[ERROR] Error starting PTO scraper: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/pto/scraper/stop")
async def stop_pto_scraper():
    """Manually stop the PTO scraper"""
    logger.info("=== [DEBUG] /pto/scraper/stop called ===")
    try:
        pto_scraper.stop_scraping()
        return JSONResponse({"status": "success", "message": "PTO scraper stopped"})
    except Exception as e:
        logger.error(f"[ERROR] Error stopping PTO scraper: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/pto/scraper/status")
async def get_pto_scraper_status():
    # logger.info("=== [DEBUG] /pto/scraper/status called ===")  # Remove log spam
    try:
        status = {
            "is_running": pto_scraper.is_running,
            "total_props": len(pto_scraper.live_props),
            "last_refresh": pto_scraper.last_refresh,
            "refresh_interval": pto_scraper.refresh_interval
        }
        return JSONResponse({"status": "success", "data": status})
    except Exception as e:
        logger.error(f"[ERROR] Error getting PTO scraper status: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# BuckeyeScraper endpoints
@app.get("/buckeye/events")
async def get_buckeye_events():
    """Get all BuckeyeScraper events with EV analysis"""
    try:
        # Get active events from pod_event_manager and format them for BuckeyeScraper
        active_events = pod_event_manager.get_active_events()
        buckeye_events = []
        
        for event_id, event_data in active_events.items():
            # Skip events without proper data
            if not event_data.get("betbck_data") or not event_data.get("pinnacle_data_processed"):
                continue
                
            # Build event object using existing logic
            event_obj = build_event_object(event_id, event_data)
            
            # Calculate best EV for sorting
            markets = event_obj.get("markets", [])
            best_ev = 0
            total_ev = 0
            ev_count = 0
            
            for market in markets:
                try:
                    ev_str = market.get("ev", "0%")
                    ev_value = float(ev_str.replace('%', ''))
                    if ev_value > best_ev:
                        best_ev = ev_value
                    if ev_value > 0:
                        total_ev += ev_value
                        ev_count += 1
                except:
                    continue
            
            # Add BuckeyeScraper specific fields
            buckeye_event = {
                "event_id": event_id,
                "home_team": event_obj.get("title", "").split(" vs ")[0] if " vs " in event_obj.get("title", "") else "",
                "away_team": event_obj.get("title", "").split(" vs ")[1] if " vs " in event_obj.get("title", "") else "",
                "league": event_obj.get("meta_info", "").split(" | ")[0] if " | " in event_obj.get("meta_info", "") else "",
                "start_time": event_obj.get("meta_info", "").split("Starts: ")[1] if "Starts: " in event_obj.get("meta_info", "") else "",
                "markets": markets,
                "total_ev": total_ev,
                "best_ev": best_ev,
                "last_updated": event_obj.get("last_update", "")
            }
            
            buckeye_events.append(buckeye_event)
        
        # Sort by best EV (descending)
        buckeye_events.sort(key=lambda x: x["best_ev"], reverse=True)
        
        return JSONResponse({
            "status": "success",
            "data": {
                "events": buckeye_events,
                "total_count": len(buckeye_events),
                "last_update": datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"Error getting BuckeyeScraper events: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.get("/buckeye/events/ev/{min_ev}")
async def get_buckeye_events_by_ev(min_ev: float = 0.0):
    """Get BuckeyeScraper events filtered by minimum EV"""
    try:
        # Get all events first
        all_events_response = await get_buckeye_events()
        if all_events_response.status_code != 200:
            return all_events_response
            
        all_events_data = all_events_response.body
        all_events = json.loads(all_events_data.decode())["data"]["events"]
        
        # Filter by minimum EV
        filtered_events = []
        for event in all_events:
            if event["best_ev"] >= min_ev:
                # Also filter markets within the event
                filtered_markets = []
                for market in event["markets"]:
                    try:
                        ev_str = market.get("ev", "0%")
                        ev_value = float(ev_str.replace('%', ''))
                        if ev_value >= min_ev:
                            filtered_markets.append(market)
                    except:
                        continue
                
                if filtered_markets:
                    event_copy = event.copy()
                    event_copy["markets"] = filtered_markets
                    filtered_events.append(event_copy)
        
        return JSONResponse({
            "status": "success",
            "data": {
                "events": filtered_events,
                "total_count": len(filtered_events),
                "last_update": datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"Error getting BuckeyeScraper events by EV: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.post("/buckeye/scraper/start")
async def start_buckeye_scraper():
    """Start the BuckeyeScraper (uses existing POD event manager)"""
    try:
        # The BuckeyeScraper uses the existing POD event manager
        # Just return success since it's always running
        return JSONResponse({
            "status": "success",
            "message": "BuckeyeScraper is always active via POD event manager"
        })
    except Exception as e:
        logger.error(f"Error starting BuckeyeScraper: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.post("/buckeye/scraper/stop")
async def stop_buckeye_scraper():
    """Stop the BuckeyeScraper (not applicable since it uses POD manager)"""
    try:
        # The BuckeyeScraper uses the existing POD event manager
        # Just return success since it's always running
        return JSONResponse({
            "status": "success",
            "message": "BuckeyeScraper uses POD event manager - cannot be stopped independently"
        })
    except Exception as e:
        logger.error(f"Error stopping BuckeyeScraper: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.get("/buckeye/scraper/status")
async def get_buckeye_scraper_status():
    """Get BuckeyeScraper status"""
    try:
        active_events = pod_event_manager.get_active_events()
        status = {
            "is_running": True,  # Always running via POD manager
            "total_events": len(active_events),
            "last_refresh": time.time(),
            "refresh_interval": 30  # POD manager refresh interval
        }
        return JSONResponse({
            "status": "success",
            "data": status
        })
    except Exception as e:
        logger.error(f"Error getting BuckeyeScraper status: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.post('/buckeye/get-event-ids')
def get_event_ids():
    try:
        result = subprocess.run(['python', 'eventID.py'], capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return JSONResponse(status_code=500, content={
                'status': 'error',
                'message': f'eventID.py failed: {result.stderr}',
                'data': {}
            })
        # Read data/buckeye_event_ids.json for event count
        if os.path.exists('data/buckeye_event_ids.json'):
            with open('data/buckeye_event_ids.json', 'r', encoding='utf-8') as f:
                events_data = f.read()
            import json
            events_json = json.loads(events_data)
            event_dicts = events_json.get('event_ids', [])
            event_count = len(event_dicts)
            return {
                'status': 'success',
                'message': f'Successfully retrieved {event_count} event IDs',
                'data': {
                    'event_count': event_count,
                    'event_ids': [event['event_id'] for event in event_dicts if isinstance(event, dict) and 'event_id' in event]
                }
            }
        else:
            return {
                'status': 'error',
                'message': 'data/buckeye_event_ids.json not found after running eventID.py',
                'data': {}
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            'status': 'error',
            'message': f'Exception running eventID.py: {e}',
            'data': {}
        })

BUCKEYE_RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'buckeye_results.json')
current_results = None
last_run_time = None

@app.post("/api/run-pipeline")
async def run_pipeline():
    """Run the Buckeye pipeline: scrape BetBCK, match/normalize, fetch Swordfish, calculate EV, output."""
    logger.info("=== [API] /run-pipeline endpoint called ===")
    global current_results, last_run_time
    import time
    try:
        # Step 1: Load event IDs from file
        logger.info("[STEP] Step 1: Loading event IDs from file...")
        event_ids_path = os.path.join(os.path.dirname(__file__), 'data', 'buckeye_event_ids.json')
        if not os.path.exists(event_ids_path):
            logger.error(f"[ERROR] Event IDs file does not exist: {event_ids_path}")
            return {
                "status": "error",
                "message": f"Event IDs file missing: {event_ids_path}",
                "data": {}
            }
        try:
            with open(event_ids_path, 'r') as f:
                events_data = json.load(f)
            event_dicts = events_data.get('event_ids', [])
            logger.info(f"[PIPELINE] Loaded {len(event_dicts)} event IDs from file.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load event IDs from file: {e}")
            return {
                "status": "error",
                "message": f"Failed to load event IDs: {str(e)}",
                "data": {}
            }
        # Step 2: Scrape BetBCK fresh
        logger.info("[STEP] Step 2: Scraping BetBCK fresh...")
        try:
            from betbck_async_scraper import _get_all_betbck_games_async
            scrape_start = time.time()
            betbck_games = await _get_all_betbck_games_async()
            scrape_end = time.time()
            logger.info(f"[PIPELINE] Scraped {len(betbck_games)} BetBCK games in {scrape_end-scrape_start:.2f}s.")
            # Ensure the file was written and is fresh
            betbck_games_path = os.path.join(os.path.dirname(__file__), 'data', 'betbck_games.json')
            if not os.path.exists(betbck_games_path):
                logger.error(f"[ERROR] BetBCK games file not found after scrape: {betbck_games_path}")
                return {
                    "status": "error",
                    "message": f"BetBCK games file not found after scrape: {betbck_games_path}",
                    "data": {}
                }
            file_mtime = os.path.getmtime(betbck_games_path)
            now = time.time()
            if now - file_mtime > 30:
                logger.error(f"[ERROR] BetBCK games file is stale (last modified {now-file_mtime:.1f}s ago)")
                return {
                    "status": "error",
                    "message": f"BetBCK games file is stale (last modified {now-file_mtime:.1f}s ago)",
                    "data": {}
                }
            logger.info(f"[PIPELINE] BetBCK games file is fresh (last modified {now-file_mtime:.1f}s ago)")
        except Exception as e:
            logger.error(f"[ERROR] Failed to scrape BetBCK data: {e}")
            return {
                "status": "error",
                "message": f"Failed to scrape BetBCK data: {str(e)}",
                "data": {}
            }
        # Step 3: Match/normalize BetBCK games to event IDs
        logger.info("[STEP] Step 3: Matching BetBCK games to event IDs...")
        try:
            from match_games import match_pinnacle_to_betbck
            matched_games = match_pinnacle_to_betbck(event_dicts, {"games": betbck_games})
            logger.info(f"[PIPELINE] Matched {len(matched_games)} games.")
            if not matched_games:
                logger.error("[ERROR] No games matched successfully")
                return {
                    "status": "error",
                    "message": "No games matched successfully",
                    "data": {}
                }
        except Exception as e:
            logger.error(f"[ERROR] Failed to match games: {e}")
            return {
                "status": "error",
                "message": f"Failed to match games: {str(e)}",
                "data": {}
            }
        # Step 4: Fetch Swordfish for matched games and calculate EV
        logger.info("[STEP] Step 4: Fetching Swordfish odds and calculating EV for matched games...")
        try:
            from calculate_ev_table import calculate_ev_table, format_ev_table_for_display
            ev_table = calculate_ev_table(matched_games)
            if not ev_table:
                logger.error("[PIPELINE] No EV opportunities found")
                return {
                    "status": "error",
                    "message": "No EV opportunities found",
                    "data": {}
                }
            formatted_events = format_ev_table_for_display(ev_table)
            total_opportunities = sum(event.get("total_ev_opportunities", 0) for event in ev_table)
            logger.info(f"[PIPELINE] Calculated EV for {len(formatted_events)} events.")
            logger.info(f"[PIPELINE] Step 4 completed: {len(formatted_events)} events with {total_opportunities} opportunities")
            # Store results in memory and on disk
            current_results = formatted_events
            last_run_time = datetime.now().isoformat()
            try:
                os.makedirs(os.path.dirname(BUCKEYE_RESULTS_FILE), exist_ok=True)
                with open(BUCKEYE_RESULTS_FILE, 'w', encoding='utf-8') as f:
                    json.dump({
                        "events": formatted_events,
                        "total_events": len(formatted_events),
                        "last_run": last_run_time
                    }, f, indent=2)
                logger.info(f"[PIPELINE] Results written to {BUCKEYE_RESULTS_FILE} ({len(formatted_events)} events)")
                # Final check: ensure file is written and fresh
                if not os.path.exists(BUCKEYE_RESULTS_FILE):
                    logger.error(f"[PIPELINE] Results file not found after write: {BUCKEYE_RESULTS_FILE}")
                    return {
                        "status": "error",
                        "message": f"Results file not found after write: {BUCKEYE_RESULTS_FILE}",
                        "data": {}
                    }
                file_mtime = os.path.getmtime(BUCKEYE_RESULTS_FILE)
                now = time.time()
                if now - file_mtime > 30:
                    logger.error(f"[PIPELINE] Results file is stale (last modified {now-file_mtime:.1f}s ago)")
                    return {
                        "status": "error",
                        "message": f"Results file is stale (last modified {now-file_mtime:.1f}s ago)",
                        "data": {}
                    }
                logger.info(f"[PIPELINE] Results file is fresh (last modified {now-file_mtime:.1f}s ago)")
            except Exception as e:
                logger.error(f"[PIPELINE] ERROR writing results to {BUCKEYE_RESULTS_FILE}: {e}")
            return {
                "status": "success",
                "message": f"Pipeline completed successfully: {len(formatted_events)} events, {total_opportunities} opportunities",
                "data": {
                    "step1": {
                        "status": "success",
                        "message": f"Loaded {len(event_dicts)} event IDs",
                        "data": {"event_count": len(event_dicts)}
                    },
                    "step2": {
                        "status": "success", 
                        "message": f"Scraped and matched {len(matched_games)} games",
                        "data": {
                            "total_events": len(formatted_events),
                            "total_opportunities": total_opportunities,
                            "events": formatted_events
                        }
                    },
                    "final_result": {
                        "status": "success",
                        "message": f"Pipeline completed: {len(formatted_events)} events, {total_opportunities} opportunities",
                        "data": {
                            "total_events": len(formatted_events),
                            "total_opportunities": total_opportunities,
                            "events": formatted_events
                        }
                    },
                    "pipeline_stats": {
                        "event_id_count": len(event_dicts),
                        "betbck_game_count": len(betbck_games),
                        "matched_game_count": len(matched_games),
                        "ev_count": len(formatted_events)
                    },
                    "top_10_evs": formatted_events
                }
            }
        except Exception as e:
            logger.error(f"[ERROR] Failed to calculate EV: {e}")
            return {
                "status": "error",
                "message": f"Failed to calculate EV: {str(e)}",
                "data": {}
            }
    except Exception as e:
        logger.error(f"[ERROR] [API] Pipeline endpoint error: {e}")
        import traceback
        logger.error(f"[API] Pipeline traceback: {traceback.format_exc()}")
        return {
            "status": "error",
            "message": f"Pipeline execution failed: {str(e)}",
            "data": {}
        }

@app.get("/api/get-results")
def get_results():
    global current_results, last_run_time
    if current_results is None:
        # Try to load from file
        try:
            if os.path.exists(BUCKEYE_RESULTS_FILE):
                with open(BUCKEYE_RESULTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                current_results = data.get("events", [])
                last_run_time = data.get("last_run", None)
                logger.info(f"[PIPELINE] Loaded results from {BUCKEYE_RESULTS_FILE} ({len(current_results)} events)")
            else:
                logger.info(f"[PIPELINE] No results file found at {BUCKEYE_RESULTS_FILE}")
        except Exception as e:
            logger.error(f"[PIPELINE] ERROR loading results from {BUCKEYE_RESULTS_FILE}: {e}")
            return {
                "status": "error",
                "message": f"Error loading results: {e}",
                "data": {"events": [], "total_events": 0}
            }
    if not current_results:
        return {
            "status": "error",
            "message": "No results available. Run calculations first.",
            "data": {"events": [], "total_events": 0}
        }
    return {
        "status": "success",
        "message": f"Loaded {len(current_results)} events",
        "data": {
            "events": current_results,
            "total_events": len(current_results),
            "last_run": last_run_time
        }
    }

@app.post("/api/betbck/open_bet")
async def open_bet(request: Request):
    payload = await request.json()
    import requests
    from betbck_scraper import login_to_betbck, SEARCH_ACTION_URL, BASE_HEADERS
    session = requests.Session()
    if not login_to_betbck(session):
        return JSONResponse({"status": "error", "message": "Failed to login to BetBCK"}, status_code=500)
    try:
        response = session.post(SEARCH_ACTION_URL, data=payload, headers=BASE_HEADERS, timeout=15)
        if response.ok:
            return JSONResponse({"status": "success", "message": "Bet page opened"})
        else:
            return JSONResponse({"status": "error", "message": "Failed to open bet page"}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("[WebSocket] New client attempting to connect")
    await manager.connect(websocket)
    logger.info("[WebSocket] Client connected successfully")
    
    # Send all active events immediately when client connects
    try:
        active_events = pod_event_manager.get_active_events()
        logger.info(f"[WebSocket] Found {len(active_events)} active events to send")
        if active_events:
            events_payload = {}
            for event_id, event_data in active_events.items():
                events_payload[event_id] = build_event_object(event_id, event_data)
            
            await websocket.send_text(json.dumps({
                "type": "pod_alerts_full",
                "events": events_payload
            }))
            logger.info(f"[WebSocket] Sent {len(events_payload)} active events to new client")
        else:
            logger.info("[WebSocket] No active events to send")
    except Exception as e:
        logger.error(f"[WebSocket] Error sending initial events: {e}")
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        logger.info("[WebSocket] Client disconnected")
        await manager.disconnect(websocket)

# Add this helper at module level

def format_start_time_nicely(start_time_val):
    """Convert start time to a nice relative format like 'Today @ 7:30 PM' or 'Tomorrow @ 8:00 AM'"""
    from datetime import datetime, timezone, timedelta
    
    try:
        # Parse the start time
        if isinstance(start_time_val, (int, float)) and start_time_val > 1000000000:
            # Unix timestamp in milliseconds
            dt = datetime.utcfromtimestamp(start_time_val/1000).replace(tzinfo=timezone.utc)
        elif isinstance(start_time_val, str):
            if 'T' in start_time_val and 'Z' in start_time_val:
                # ISO format with Z
                dt = datetime.fromisoformat(start_time_val.replace('Z', '+00:00'))
            elif 'T' in start_time_val:
                # ISO format without Z
                dt = datetime.fromisoformat(start_time_val)
            else:
                # Try other formats
                dt = datetime.strptime(start_time_val, '%Y-%m-%d %H:%M')
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            return "Time TBD"
        
        # Convert to Central Time (UTC-5 for CDT, UTC-6 for CST)
        # We're currently in CDT (Central Daylight Time) which is UTC-5
        dt_central = dt - timedelta(hours=5)
        
        # Get current time in UTC and convert to Central
        now_utc = datetime.now(timezone.utc)
        now_central = now_utc - timedelta(hours=5)
        
        # Format the time part
        time_str = dt_central.strftime("%I:%M %p").lstrip("0")  # Remove leading zero from hour
        
        # Determine the date part
        if dt_central.date() == now_central.date():
            return f"Today @ {time_str}"
        elif dt_central.date() == now_central.date() + timedelta(days=1):
            return f"Tomorrow @ {time_str}"
        else:
            # More than 1 day away, show the date
            date_str = dt_central.strftime("%m/%d")  # e.g., "08/02"
            return f"{date_str} @ {time_str}"
            
    except Exception as e:
        logger.warning(f"[TimeFormat] Error formatting time '{start_time_val}': {e}")
        return "Time TBD"

def build_event_object(event_id, entry):
    import copy
    from datetime import datetime, timezone
    
    # Defensive check for None entry
    if entry is None:
        logger.error(f"[BuildEventObject] Entry is None for event {event_id}")
        return None
    
    # NEW: Handle if a processed object is accidentally passed (prevent removal and return as-is)
    if "title" in entry and "markets" in entry:
        logger.warning(f"[BuildEventObject] Passed already-built object for {event_id}, returning as-is to avoid errors")
        return entry
    
    def normalize_team_name_for_matching(name):
        return name.strip().lower() if isinstance(name, str) else ''
    
    current_time_sec = time.time()
    
    # Defensive checks for required fields
    if "pinnacle_data_processed" not in entry or entry["pinnacle_data_processed"] is None:
        logger.error(f"[BuildEventObject] pinnacle_data_processed is None for event {event_id} - removing corrupted event")
        # Remove the corrupted event from active events
        try:
            pod_event_manager.remove_active_event(event_id)
            logger.info(f"[BuildEventObject] Removed corrupted event {event_id} from active events")
        except Exception as e:
            logger.error(f"[BuildEventObject] Failed to remove corrupted event {event_id}: {e}")
        return None
    
    # BetBCK data is optional for background refresher updates
    betbck_data_available = "betbck_data" in entry and entry["betbck_data"] is not None
    if not betbck_data_available:
        logger.info(f"[BuildEventObject] betbck_data not available for event {event_id} (background refresh)")
    
    if "original_alert_details" not in entry or entry["original_alert_details"] is None:
        logger.error(f"[BuildEventObject] original_alert_details is None for event {event_id} - removing corrupted event")
        # Remove the corrupted event from active events
        try:
            pod_event_manager.remove_active_event(event_id)
            logger.info(f"[BuildEventObject] Removed corrupted event {event_id} from active events")
        except Exception as e:
            logger.error(f"[BuildEventObject] Failed to remove corrupted event {event_id}: {e}")
        return None
    
    bet_data = copy.deepcopy(entry.get("betbck_data", {}).get("data", {})) if betbck_data_available else {}
    pinnacle_data = copy.deepcopy(entry["pinnacle_data_processed"].get("data", {}))
    home_team = normalize_team_name_for_matching(entry.get("cleaned_home_team", ""))
    away_team = normalize_team_name_for_matching(entry.get("cleaned_away_team", ""))
    league = entry.get("league_name", "")
    start_time = entry.get("start_time", "")
    league_name = pinnacle_data.get("league_name", entry.get("league_name", "Unknown League"))
    start_time_val = pinnacle_data.get("starts", entry.get("start_time", "N/A"))
    # Format the start time nicely
    formatted_start_time = format_start_time_nicely(start_time_val)
    # If potential_bets_analyzed is empty but odds are present, re-run EV analysis
    if not bet_data.get("potential_bets_analyzed") and bet_data and pinnacle_data:
        try:
            wrapped_pinnacle_data = {"data": pinnacle_data}
            bet_data["potential_bets_analyzed"] = analyze_markets_for_ev(bet_data, wrapped_pinnacle_data)
        except Exception:
            bet_data["potential_bets_analyzed"] = []
    
    # For background refresher updates, use the markets from pinnacle_data_processed
    # (which have been re-analyzed with fresh Pinnacle odds)
    if betbck_data_available:
        # For initial alerts, use the original potential_bets_analyzed
        potential_bets = bet_data.get("potential_bets_analyzed", [])
    else:
        # For background refreshes, use the re-analyzed markets from pinnacle_data_processed
        # These have been updated with fresh Pinnacle odds and existing BetBCK data
        potential_bets = entry["pinnacle_data_processed"].get("markets", [])
    markets = []
    for bet in potential_bets:
        market_type = bet.get("market")
        selection = bet.get("selection")
        line = bet.get("line", "")
        betbck_odds = bet.get("betbck_odds", "N/A")
        latest_nvp = bet.get("pinnacle_nvp", "N/A")
        ev_display = bet.get("ev", "N/A")
        if betbck_odds != "N/A" and latest_nvp != "N/A" and betbck_odds is not None and latest_nvp is not None:
            try:
                bet_decimal = american_to_decimal(betbck_odds)
                true_decimal = american_to_decimal(latest_nvp)
                ev = calculate_ev(bet_decimal, true_decimal)
                ev_display = f"{ev*100:.2f}%" if ev is not None else "N/A"
            except Exception:
                ev_display = "N/A"
        markets.append({
            "market": market_type,
            "selection": selection,
            "line": line,
            "pinnacle_nvp": str(latest_nvp) if latest_nvp != "N/A" else "N/A",
            "betbck_odds": str(betbck_odds) if betbck_odds != "N/A" else "N/A",
            "ev": ev_display
        })
    display_home = pinnacle_data.get('home', home_team)
    display_away = pinnacle_data.get('away', away_team)
    return {
        "title": f"{display_home} vs {display_away}",
        "meta_info": f"{league_name} | {formatted_start_time}",
        "last_update": entry.get("last_pinnacle_data_update_timestamp", "N/A"),
        "betbck_last_update": entry.get("betbck_last_update", None),
        "alert_description": entry['original_alert_details'].get("betDescription", "POD Alert Processed"),
        "alert_meta": f"(Alert: {entry['old_odds']} → {entry['new_odds']}, NVP: {entry['no_vig']})",
        "betbck_status": f"Data Fetched: {home_team} vs {away_team}" if betbck_data_available and entry["betbck_data"].get("status") == "success" else (entry["betbck_data"].get("message", "Odds check pending...") if betbck_data_available else "Background refresh - no BetBCK data"),
        "markets": markets,
        "alert_arrival_timestamp": entry.get("alert_arrival_timestamp", None),
        "betbck_payload": bet_data.get("betbck_payload") or {}
    }

# In broadcast_new_alert, use build_event_object

def broadcast_new_alert(event_id, event_data):
    # event_data is the raw entry from pod_event_manager
    event_obj = build_event_object(event_id, event_data)
    
    print(f"[Broadcast] Broadcasting new alert for event {event_id}")
    logger.info(f"[Broadcast] Broadcasting new alert for event {event_id}")
    
    # Use run_coroutine_threadsafe to bridge from threading to async context
    if main_event_loop and main_event_loop.is_running():
        try:
            print(f"[Broadcast] Sending WebSocket message: type='pod_alert', eventId={event_id}")
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "pod_alert",
                    "eventId": event_id,
                    "event": event_obj
                }),
                main_event_loop
            )
            print(f"[Broadcast] Successfully queued broadcast for event {event_id}")
            logger.info(f"[Broadcast] Successfully queued broadcast for event {event_id}")
        except Exception as e:
            print(f"[Broadcast] Error broadcasting event {event_id}: {e}")
            logger.error(f"[Broadcast] Error broadcasting event {event_id}: {e}")
    else:
        print(f"[Broadcast] Cannot broadcast event {event_id} - event loop not available")
        logger.warning(f"[Broadcast] Cannot broadcast event {event_id} - event loop not available")

# Create a global broadcast function that can be imported without circular dependencies
async def async_broadcast_pod_alert(event_id, event_data):
    """Async function to broadcast POD alerts - can be called from other modules"""
    try:
        # Check if this is a removal message
        if isinstance(event_data, dict) and event_data.get("removed"):
            # Send removal notification
            await manager.broadcast({
                "type": "pod_alert_removed",
                "eventId": event_id
            })
            logger.info(f"[AsyncBroadcast] Successfully broadcast removal for event {event_id}")
        else:
            # Send normal alert update
            event_obj = build_event_object(event_id, event_data)
            if event_obj is None:
                logger.error(f"[AsyncBroadcast] Cannot broadcast event {event_id} - build_event_object returned None")
                return
            
            await manager.broadcast({
                "type": "pod_alert",
                "eventId": event_id,
                "event": event_obj
            })
            logger.info(f"[AsyncBroadcast] Successfully broadcast event {event_id}")
    except Exception as e:
        logger.error(f"[AsyncBroadcast] Error broadcasting event {event_id}: {e}")

def broadcast_pod_alert_safe(event_id, event_data):
    """Thread-safe broadcast function that can be called from any context"""
    # Validate event data before attempting to broadcast
    if not event_data:
        logger.error(f"[SafeBroadcast] Cannot broadcast event {event_id} - event_data is None or empty")
        return
    
    # Check if this is a processed event object (from build_event_object) or raw event data
    if "pinnacle_data_processed" not in event_data:
        logger.warning(f"[SafeBroadcast] Event {event_id} missing pinnacle_data_processed - may be processed object")
        # Don't skip - let it try to process anyway
    elif event_data["pinnacle_data_processed"] is None:
        logger.error(f"[SafeBroadcast] Cannot broadcast event {event_id} - pinnacle_data_processed is None")
        # Remove the corrupted event
        try:
            pod_event_manager.remove_active_event(event_id)
            logger.info(f"[SafeBroadcast] Removed corrupted event {event_id}")
        except Exception as e:
            logger.error(f"[SafeBroadcast] Failed to remove corrupted event {event_id}: {e}")
        return
    
    if main_event_loop and main_event_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(
                async_broadcast_pod_alert(event_id, event_data),
                main_event_loop
            )
            logger.info(f"[SafeBroadcast] Queued broadcast for event {event_id}")
        except Exception as e:
            logger.error(f"[SafeBroadcast] Error queuing broadcast for event {event_id}: {e}")
    else:
        logger.warning(f"[SafeBroadcast] Cannot broadcast event {event_id} - event loop not available")

if __name__ == "__main__":
    print("MAIN MODULE LOADED")
    logger.info("[BackgroundRefresher] Launching refresher thread from __main__ block")
    print("[BackgroundRefresher] Launching refresher thread from __main__ block")
    # The refresher thread is now started in the FastAPI startup event
    # This block is no longer needed for the refresher thread start
    # threading.Thread(target=start_background_refresher, daemon=True).start()
    # logger.info("[BackgroundRefresher] Thread launched successfully from __main__ block")
    # print("[BackgroundRefresher] Thread launched successfully from __main__ block")
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5001, reload=True)

@app.get("/api/debug/matching")
async def debug_matching():
    """Debug endpoint to analyze matching issues and provide detailed information"""
    logger.info("=== [API] /debug/matching endpoint called ===")
    
    try:
        # Load current data
        betbck_data = None
        pinnacle_events = None
        
        try:
            with open('data/betbck_games.json', 'r') as f:
                betbck_data = json.load(f)
            logger.info(f"Loaded {len(betbck_data.get('games', []))} BetBCK games")
        except FileNotFoundError:
            logger.warning("BetBCK games file not found")
        
        try:
            with open('data/buckeye_event_ids.json', 'r') as f:
                events_data = json.load(f)
                pinnacle_events = events_data.get('event_ids', [])
            logger.info(f"Loaded {len(pinnacle_events)} Pinnacle events")
        except FileNotFoundError:
            logger.warning("Pinnacle events file not found")
        
        # Run matching analysis
        if betbck_data and pinnacle_events:
            from match_games import match_pinnacle_to_betbck
            
            logger.info("Running matching analysis...")
            matched_games = match_pinnacle_to_betbck(pinnacle_events, betbck_data)
            
            # Calculate statistics
            total_betbck = len(betbck_data.get('games', []))
            total_pinnacle = len(pinnacle_events)
            total_matched = len(matched_games)
            match_rate = (total_matched / total_betbck * 100) if total_betbck > 0 else 0
            
            return {
                "status": "success",
                "message": "Matching analysis completed",
                "data": {
                    "statistics": {
                        "total_betbck_games": total_betbck,
                        "total_pinnacle_events": total_pinnacle,
                        "total_matched": total_matched,
                        "match_rate_percent": round(match_rate, 2),
                        "unmatched_betbck": total_betbck - total_matched,
                        "unmatched_pinnacle": total_pinnacle - total_matched
                    },
                    "matched_games": matched_games[:10],  # First 10 for debugging
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            return {
                "status": "error",
                "message": "Missing data files for analysis",
                "data": {
                    "betbck_available": betbck_data is not None,
                    "pinnacle_available": pinnacle_events is not None
                }
            }
            
    except Exception as e:
        logger.error(f"[ERROR] [API] Debug matching error: {e}")
        import traceback
        logger.error(f"[API] Debug matching traceback: {traceback.format_exc()}")
        
        return {
            "status": "error",
            "message": f"Debug analysis failed: {str(e)}",
            "data": {}
        }

@app.get("/buckeye/results")
def get_buckeye_results():
    """Serve the latest BuckeyeScraper EV results from buckeye_results.json for frontend table population."""
    try:
        results_path = os.path.join(os.path.dirname(__file__), 'data', 'buckeye_results.json')
        if not os.path.exists(results_path):
            return JSONResponse({
                "status": "error",
                "message": "No results file found. Run calculations first.",
                "data": {"events": [], "total_events": 0}
            }, status_code=404)
        with open(results_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        events = data.get("events", [])
        last_update = data.get("last_run")
        # Map to frontend columns
        all_markets = []
        for event in events:
            home_team = event.get("event", "").split(" vs ")[0] if " vs " in event.get("event", "") else event.get("event", "")
            away_team = event.get("event", "").split(" vs ")[1] if " vs " in event.get("event", "") else ""
            league = event.get("league", "")
            for market in [event]:  # Each event is already a market row
                all_markets.append({
                    "matchup": f"{home_team} vs {away_team}",
                    "league": league,
                    "bet": market.get('bet', ''),
                    "betbck_odds": market.get("betbck_odds", ""),
                    "pinnacle_nvp": market.get("pin_nvp", ""),
                    "ev": market.get("ev", ""),
                    "start_time": market.get("start_time", ""),
                    "pinnacle_limit": market.get("max_bet")
                })
        return JSONResponse({
            "status": "success",
            "data": {
                "markets": all_markets,
                "last_update": last_update
            }
        })
    except Exception as e:
        logger.error(f"Error getting BuckeyeScraper results: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/api/betbck/status")
async def get_betbck_status():
    """Get BetBCK Request Manager status"""
    try:
        status = betbck_manager.get_status()
        return JSONResponse({
            "status": "success",
            "data": status
        })
    except Exception as e:
        logger.error(f"[BetBCK-Status] Error getting status: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@app.post("/ace/run-calculations")
def run_ace_calculations():
    """Run Ace calculations"""
    try:
        logger.info("=== Ace: Running Calculations ===")
        logger.info("Starting Ace calculations...")
        
        results = ace_scraper.run_ace_calculations()
        logger.info(f"Ace calculations returned: {results}")
        
        if results.get("status") == "success":
            logger.info(f"Ace calculations completed: {results.get('message', 'Success')}")
            return JSONResponse(content=results)
        else:
            error_msg = results.get("message") or results.get("error") or "Unknown error"
            logger.error(f"Ace calculations failed: {error_msg}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": error_msg}
            )
    except Exception as e:
        logger.error(f"Error running Ace calculations: {e}")
        import traceback
        logger.error(f"Ace calculations traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to run Ace calculations: {str(e)}"}
        )

@app.get("/ace/results")
def get_ace_results():
    """Get Ace results"""
    try:
        results = ace_scraper.get_ace_results()
        
        if results["status"] == "success":
            return JSONResponse(content=results)
        else:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": results["message"]}
            )
    except Exception as e:
        logger.error(f"Error getting Ace results: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to get Ace results: {str(e)}"}
        ) 

@app.get("/high-ev-alerts")
async def get_high_ev_alerts(limit: int = 100):
    """Get high EV alerts from database (>3% EV)"""
    try:
        session = get_session()
        alerts = session.query(HighEVAlert)\
            .order_by(HighEVAlert.created_at.desc())\
            .limit(limit)\
            .all()
        
        result = [
            {
                "id": alert.id,
                "event_id": alert.event_id,
                "sport": alert.sport,
                "away_team": alert.away_team,
                "home_team": alert.home_team,
                "ev_percentage": alert.ev_percentage,
                "bet_type": alert.bet_type,
                "odds": alert.odds,
                "nvp": alert.nvp,
                "created_at": alert.created_at.isoformat(),
                "processed": alert.processed
            }
            for alert in alerts
        ]
        
        session.close()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error getting high EV alerts: {e}")
        # Return empty result instead of error to prevent frontend crashes
        return JSONResponse([])

@app.get("/refresher-status")
async def get_refresher_status():
    """Check if the background refresher is running"""
    global refresher_running, refresher_thread
    try:
        # Check if we have any active events being processed
        active_events = pod_event_manager.get_active_events()
        
        # Check if refresher thread is running
        thread_running = refresher_thread.is_alive() if refresher_thread else False
        
        return {
            "status": "running" if refresher_running and thread_running else "not_running",
            "refresher_running": refresher_running,
            "thread_running": thread_running,
            "active_events_count": len(active_events),
            "active_event_ids": list(active_events.keys()),
            "refresher_interval_seconds": pod_event_manager.BACKGROUND_REFRESH_INTERVAL_SECONDS,
            "timestamp": time.time(),
            "message": "Check console logs for detailed refresher status."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        } 

@app.post("/refresher/start")
async def start_refresher_manually():
    """Manually start the background refresher"""
    global refresher_running, refresher_thread
    try:
        if refresher_running and refresher_thread and refresher_thread.is_alive():
            return {"status": "already_running", "message": "Refresher is already running"}
        
        def start_background_refresher():
            global refresher_running
            print("[BackgroundRefresher] Thread refresher starting manually...")
            logger.info("[BackgroundRefresher] Thread refresher starting manually...")
            try:
                refresher_running = True
                # Run the async function in a new event loop for the thread
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(pod_event_manager.background_event_refresher(broadcast_pod_alert_safe))
            except Exception as e:
                print(f"[BackgroundRefresher] Critical error: {e}")
                logger.error(f"[BackgroundRefresher] Critical error: {e}")
                refresher_running = False
                import traceback
                traceback.print_exc()
        
        refresher_thread = threading.Thread(target=start_background_refresher, daemon=True)
        refresher_thread.start()
        
        return {"status": "started", "message": "Background refresher started manually"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/test/remove-alert/{event_id}")
async def test_remove_alert(event_id: str):
    """Test endpoint to manually remove an alert"""
    try:
        # Remove the alert
        pod_event_manager.remove_active_event(event_id, broadcast_pod_alert_safe)
        return {"status": "success", "message": f"Alert {event_id} removed for testing"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/test/cleanup-corrupted-events")
async def cleanup_corrupted_events():
    """Clean up any corrupted events that are missing required data"""
    try:
        active_events = pod_event_manager.get_active_events()
        corrupted_events = []
        
        for event_id, event_data in active_events.items():
            if not event_data or "pinnacle_data_processed" not in event_data or event_data["pinnacle_data_processed"] is None:
                corrupted_events.append(event_id)
                try:
                    pod_event_manager.remove_active_event(event_id, broadcast_pod_alert_safe)
                    logger.info(f"[Cleanup] Removed corrupted event {event_id}")
                except Exception as e:
                    logger.error(f"[Cleanup] Failed to remove corrupted event {event_id}: {e}")
        
        return {
            "status": "success", 
            "message": f"Cleaned up {len(corrupted_events)} corrupted events",
            "removed_events": corrupted_events
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/test/cleanup-expired-events")
async def cleanup_expired_events():
    """Clean up any expired events"""
    try:
        active_events = pod_event_manager.get_active_events()
        current_time = time.time()
        expired_events = []
        
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
                    expired_events.append(event_id)
                    try:
                        pod_event_manager.remove_active_event(event_id, broadcast_pod_alert_safe)
                        logger.info(f"[Cleanup] Removed expired event {event_id} (age: {alert_age:.1f}s, limit: {expiry_time}s)")
                    except Exception as e:
                        logger.error(f"[Cleanup] Failed to remove expired event {event_id}: {e}")
            except Exception as e:
                logger.error(f"[Cleanup] Error checking event {event_id}: {e}")
        
        return {
            "status": "success", 
            "message": f"Cleaned up {len(expired_events)} expired events",
            "removed_events": expired_events
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Global exception handler to prevent crashes
import sys
import traceback

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow normal exit on Ctrl+C
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
    logger.error("Backend will attempt to continue running...")

sys.excepthook = handle_exception

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
    except Exception as e:
        logger.error(f"Uvicorn crashed: {e}")
        logger.error(traceback.format_exc())
        # Don't exit, let the process restart 