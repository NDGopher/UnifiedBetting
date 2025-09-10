#!/usr/bin/env python3
"""
Test script to debug the pipeline validation issue
"""
import asyncio
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_pipeline_step2():
    """Test Step 2 of the pipeline in isolation"""
    logger.info("=== TESTING PIPELINE STEP 2 ===")
    
    try:
        from betbck_async_scraper import _get_all_betbck_games_async
        logger.info("Importing async scraper...")
        
        # Add timeout to prevent hanging
        betbck_games = await asyncio.wait_for(_get_all_betbck_games_async(), timeout=300)
        logger.info(f"Async scraper returned type: {type(betbck_games)}")
        logger.info(f"Async scraper returned length: {len(betbck_games) if hasattr(betbck_games, '__len__') else 'N/A'}")
        
        if betbck_games and len(betbck_games) > 0:
            logger.info(f"First game type: {type(betbck_games[0])}")
            if isinstance(betbck_games[0], dict):
                logger.info(f"First game keys: {list(betbck_games[0].keys())}")
            else:
                logger.info(f"First game is not a dict: {betbck_games[0]}")
        
        # Test validation logic
        logger.info("=== TESTING VALIDATION LOGIC ===")
        if not betbck_games:
            logger.error("No BetBCK games scraped")
            return False
        
        # Validate BetBCK games structure
        valid_games = 0
        logger.info(f"BetBCK games type: {type(betbck_games)}, length: {len(betbck_games) if hasattr(betbck_games, '__len__') else 'N/A'}")
        
        if betbck_games and len(betbck_games) > 0:
            logger.info(f"First game type: {type(betbck_games[0])}, keys: {list(betbck_games[0].keys()) if isinstance(betbck_games[0], dict) else 'Not a dict'}")
        
        for i, game in enumerate(betbck_games):
            if isinstance(game, dict) and 'betbck_site_home_team' in game and 'betbck_site_away_team' in game:
                valid_games += 1
            else:
                if i < 5:  # Log first 5 invalid games
                    logger.warning(f"Invalid game {i}: type={type(game)}, keys={list(game.keys()) if isinstance(game, dict) else 'Not a dict'}")
        
        logger.info(f"Validation result: {valid_games} valid games out of {len(betbck_games)}")
        
        # Test sport detection
        logger.info("=== TESTING SPORT DETECTION ===")
        from match_games import determine_sport_from_teams
        from utils.pod_utils import normalize_team_name_for_matching
        
        for i, game in enumerate(betbck_games[:5]):  # Test first 5 games
            home_raw = game.get('betbck_site_home_team', '')
            away_raw = game.get('betbck_site_away_team', '')
            home_norm = normalize_team_name_for_matching(home_raw)
            away_norm = normalize_team_name_for_matching(away_raw)
            sport = determine_sport_from_teams(home_norm, away_norm)
            logger.info(f"Game {i}: {home_raw} vs {away_raw} -> {home_norm} vs {away_norm} -> Sport: {sport}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in pipeline step 2: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_pipeline_step2())
    print(f"Test result: {result}")
