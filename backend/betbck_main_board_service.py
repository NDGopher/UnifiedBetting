"""
BetBCK Main Board Service
Optimized service that scrapes the main board periodically and caches results.
This reduces the number of individual searches needed and minimizes rate limiting.

Usage:
    from betbck_main_board_service import MainBoardService
    
    service = MainBoardService()
    service.start()  # Runs in background
    service.get_game_odds("Lakers", "Warriors")  # Get cached odds
    
    # Or run manually:
    games = service.refresh_games()
"""

import json
import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from betbck_scraper import scrape_all_betbck_games, login_to_betbck
import requests

logger = logging.getLogger(__name__)

class MainBoardService:
    """
    Service that periodically scrapes the main BetBCK board and caches results.
    This is much more efficient than searching for individual games.
    """
    
    def __init__(self, 
                 refresh_interval_minutes: int = 5,
                 cache_file: str = None,
                 auto_start: bool = False):
        """
        Args:
            refresh_interval_minutes: How often to refresh the main board (default: 5 minutes)
            cache_file: Path to cache file (default: data/betbck_main_board_cache.json)
            auto_start: Automatically start background refresh thread
        """
        self.refresh_interval = refresh_interval_minutes * 60  # Convert to seconds
        self.cache_file = cache_file or os.path.join(
            os.path.dirname(__file__), 'data', 'betbck_main_board_cache.json'
        )
        self.cache = {
            'games': [],
            'last_refresh': None,
            'refresh_count': 0,
            'errors': []
        }
        
        self.running = False
        self.worker_thread = None
        self.lock = threading.Lock()
        self.session = None
        self.last_refresh_time = 0
        
        # Load existing cache
        self._load_cache()
        
        if auto_start:
            self.start()
    
    def _load_cache(self):
        """Load cached games from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"[MainBoardService] Loaded {len(self.cache.get('games', []))} cached games")
        except Exception as e:
            logger.error(f"[MainBoardService] Error loading cache: {e}")
            self.cache = {'games': [], 'last_refresh': None, 'refresh_count': 0, 'errors': []}
    
    def _save_cache(self):
        """Save games to cache file"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[MainBoardService] Error saving cache: {e}")
    
    def refresh_games(self) -> List[Dict[str, Any]]:
        """
        Refresh games from main board. Returns list of game data.
        This is the main scraping function.
        """
        logger.info("[MainBoardService] Refreshing games from main board...")
        
        try:
            games = scrape_all_betbck_games()
            
            with self.lock:
                self.cache['games'] = games
                self.cache['last_refresh'] = datetime.now().isoformat()
                self.cache['refresh_count'] = self.cache.get('refresh_count', 0) + 1
                if 'errors' in self.cache:
                    self.cache['errors'] = []  # Clear errors on success
            
            self._save_cache()
            self.last_refresh_time = time.time()
            
            logger.info(f"[MainBoardService] Successfully refreshed {len(games)} games")
            return games
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[MainBoardService] Error refreshing games: {error_msg}")
            
            with self.lock:
                if 'errors' not in self.cache:
                    self.cache['errors'] = []
                self.cache['errors'].append({
                    'timestamp': datetime.now().isoformat(),
                    'error': error_msg
                })
                # Keep last 10 errors
                if len(self.cache['errors']) > 10:
                    self.cache['errors'] = self.cache['errors'][-10:]
            
            self._save_cache()
            return []
    
    def get_game_odds(self, home_team: str, away_team: str, 
                     normalize_func=None) -> Optional[Dict[str, Any]]:
        """
        Get odds for a specific game from cache.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            normalize_func: Optional function to normalize team names for matching
        
        Returns:
            Game data dict if found, None otherwise
        """
        with self.lock:
            games = self.cache.get('games', [])
        
        if not games:
            logger.warning("[MainBoardService] No games in cache, returning None")
            return None
        
        # Normalize team names for matching
        if normalize_func:
            norm_home = normalize_func(home_team)
            norm_away = normalize_func(away_team)
        else:
            from utils.pod_utils import normalize_team_name_for_matching
            norm_home = normalize_team_name_for_matching(home_team)
            norm_away = normalize_team_name_for_matching(away_team)
        
        # Try to find matching game
        for game in games:
            game_home = normalize_func(game['home_team']) if normalize_func else game.get('home_team', '')
            game_away = normalize_func(game['away_team']) if normalize_func else game.get('away_team', '')
            
            # Normalize for comparison
            if normalize_func:
                norm_game_home = normalize_func(game_home)
                norm_game_away = normalize_func(game_away)
            else:
                from utils.pod_utils import normalize_team_name_for_matching
                norm_game_home = normalize_team_name_for_matching(game_home)
                norm_game_away = normalize_team_name_for_matching(game_away)
            
            # Check both orderings (home/away might be flipped)
            if (norm_home == norm_game_home and norm_away == norm_game_away) or \
               (norm_home == norm_game_away and norm_away == norm_game_home):
                return game
        
        return None
    
    def get_all_games(self) -> List[Dict[str, Any]]:
        """Get all cached games"""
        with self.lock:
            return self.cache.get('games', []).copy()
    
    def is_cache_fresh(self, max_age_minutes: int = 10) -> bool:
        """Check if cache is fresh enough"""
        last_refresh = self.cache.get('last_refresh')
        if not last_refresh:
            return False
        
        try:
            last_refresh_dt = datetime.fromisoformat(last_refresh)
            age = datetime.now() - last_refresh_dt
            return age < timedelta(minutes=max_age_minutes)
        except:
            return False
    
    def _worker_loop(self):
        """Background worker thread that periodically refreshes games"""
        logger.info(f"[MainBoardService] Background worker started (refresh interval: {self.refresh_interval}s)")
        
        while self.running:
            try:
                # Check if we need to refresh
                time_since_refresh = time.time() - self.last_refresh_time
                
                if time_since_refresh >= self.refresh_interval:
                    logger.info("[MainBoardService] Background refresh triggered")
                    self.refresh_games()
                
                # Sleep for a short time before checking again
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"[MainBoardService] Worker loop error: {e}")
                time.sleep(60)
    
    def start(self):
        """Start background refresh thread"""
        if self.running:
            logger.warning("[MainBoardService] Already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("[MainBoardService] Background refresh started")
        
        # Do initial refresh if cache is stale
        if not self.is_cache_fresh():
            logger.info("[MainBoardService] Cache is stale, doing initial refresh")
            self.refresh_games()
    
    def stop(self):
        """Stop background refresh thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("[MainBoardService] Background refresh stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        with self.lock:
            last_refresh = self.cache.get('last_refresh')
            games_count = len(self.cache.get('games', []))
            refresh_count = self.cache.get('refresh_count', 0)
            errors = self.cache.get('errors', [])
        
        return {
            'running': self.running,
            'games_count': games_count,
            'last_refresh': last_refresh,
            'refresh_count': refresh_count,
            'is_fresh': self.is_cache_fresh(),
            'refresh_interval_minutes': self.refresh_interval / 60,
            'recent_errors': len([e for e in errors if datetime.fromisoformat(e['timestamp']) > datetime.now() - timedelta(hours=1)]),
            'cache_file': self.cache_file
        }


# Global instance (singleton pattern)
_main_board_service = None

def get_main_board_service(refresh_interval_minutes: int = 5, auto_start: bool = True) -> MainBoardService:
    """Get or create global MainBoardService instance"""
    global _main_board_service
    if _main_board_service is None:
        _main_board_service = MainBoardService(
            refresh_interval_minutes=refresh_interval_minutes,
            auto_start=auto_start
        )
    return _main_board_service

