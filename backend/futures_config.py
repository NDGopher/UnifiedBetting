"""
Futures market registry.

Adding a new market is as simple as adding one entry to FUTURES_MARKETS below.
The pipeline in main.py will pick it up automatically.

Market types:
  "win_total"  — Over/Under pairs (NFL, NCAAF, NBA wins, etc.)
  "outright"   — N-way winner (EPL, NBA champ, player awards, etc.)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WinTotalMarket:
    """Config for an Over/Under win-total market."""
    betbck_checkboxes: list[str]      # BetBCK POST checkbox values
    fd_pages: list[tuple[str, str]]   # [(sport_label, url), ...]
    dk_pages: list[tuple[str, str]]   # [(sport_label, url), ...]
    mgm_sports: dict[str, int]        # {sport_label: mgm_competition_id}


@dataclass
class OutrightMarket:
    """Config for an N-way outright winner market (EPL, NBA champ, etc.)."""
    betbck_checkbox: str              # Single BetBCK checkbox
    betbck_market_label: str          # Human label used when logging
    fd_url: str                       # FD page URL to intercept
    fd_market_type_kw: str            # Keyword in FD marketType for outright
    dk_url: str                       # DK page URL to intercept
    dk_market_type_kw: str            # Keyword in DK market name
    mgm_competition_id: int           # BetMGM CDS competition ID
    mgm_game_kw: str                  # Keyword in MGM game name to detect outright
    # Optional: sport path parts for BetMGM Referer header
    mgm_sport_path: str = "soccer-4/betting/england-147"


@dataclass
class FuturesMarketConfig:
    id: str
    name: str
    sport: str
    market_type: str   # "win_total" | "outright"
    config: WinTotalMarket | OutrightMarket


# ── Registry ───────────────────────────────────────────────────────────────────

FUTURES_MARKETS: dict[str, FuturesMarketConfig] = {

    # ── Football win totals (existing) ─────────────────────────────────────────
    "football_wins": FuturesMarketConfig(
        id           = "football_wins",
        name         = "NFL + NCAAF Season Win Totals",
        sport        = "Football",
        market_type  = "win_total",
        config       = WinTotalMarket(
            betbck_checkboxes = [
                "FOOTBALL_NFL@20;SEAS@20;WIN_Game_",
                "FOOTBALL_NCAA@20;SEA@20;WIN_Game_",
            ],
            fd_pages  = [
                ("NCAAF", "https://sportsbook.fanduel.com/navigation/ncaaf?tab=win-totals"),
                ("NFL",   "https://sportsbook.fanduel.com/navigation/nfl?tab=win-totals"),
            ],
            dk_pages  = [
                ("NFL",   "https://sportsbook.draftkings.com/leagues/football/nfl"
                          "?category=futures&subcategory=wins&nav_1=regular-season-wins"),
                ("NCAAF", "https://sportsbook.draftkings.com/leagues/football/ncaaf"
                          "?category=wins&subcategory=regular-season&nav_1=all-teams"),
            ],
            mgm_sports = {"NCAAF": 211, "NFL": 35},
        ),
    ),

    # ── EPL outright winner ─────────────────────────────────────────────────────
    "epl_winner": FuturesMarketConfig(
        id           = "epl_winner",
        name         = "EPL Outright Winner",
        sport        = "Soccer",
        market_type  = "outright",
        config       = OutrightMarket(
            betbck_checkbox     = "SOCCER_ENGLAND@20;PREMIER@20;LEAGUE@20;FUTURES_Prop_TO@20;WIN@20;OUTRIGHT",
            betbck_market_label = "EPL Winner",
            fd_url              = "https://sportsbook.fanduel.com/soccer?tab=epl",
            fd_market_type_kw   = "WINNER",      # marketType contains WINNER for outrights
            dk_url              = "https://sportsbook.draftkings.com/leagues/soccer/england---premier-league",
            dk_market_type_kw   = "Winner",
            mgm_competition_id  = 147,
            mgm_game_kw         = "outright",    # game name contains "outright"
            mgm_sport_path      = "soccer-4/betting/england-147",
        ),
    ),

    # ── Template: easy to add more ─────────────────────────────────────────────
    # "la_liga_winner": FuturesMarketConfig(
    #     id="la_liga_winner", name="La Liga Outright Winner", sport="Soccer",
    #     market_type="outright",
    #     config=OutrightMarket(
    #         betbck_checkbox="SOCCER_SPAIN@20;LA@20;LIGA@20;FUTURES_Prop_TO@20;WIN@20;OUTRIGHT",
    #         betbck_market_label="La Liga Winner",
    #         fd_url="https://sportsbook.fanduel.com/soccer?tab=la-liga",
    #         fd_market_type_kw="WINNER",
    #         dk_url="https://sportsbook.draftkings.com/leagues/soccer/spain---la-liga",
    #         dk_market_type_kw="Winner",
    #         mgm_competition_id=XXX,    # find in URL spain-XXX
    #         mgm_game_kw="outright",
    #         mgm_sport_path="soccer-4/betting/spain-XXX",
    #     ),
    # ),
    #
    # "nba_wins": FuturesMarketConfig(
    #     id="nba_wins", name="NBA Season Win Totals", sport="Basketball",
    #     market_type="win_total",
    #     config=WinTotalMarket(
    #         betbck_checkboxes=["BASKETBALL_NBA@20;SEAS@20;WIN_Game_"],   # verify exact name
    #         fd_pages=[("NBA", "https://sportsbook.fanduel.com/navigation/nba?tab=win-totals")],
    #         dk_pages=[("NBA", "https://sportsbook.draftkings.com/leagues/basketball/nba?category=futures&subcategory=wins")],
    #         mgm_sports={"NBA": XXX},   # find competition ID
    #     ),
    # ),
}
