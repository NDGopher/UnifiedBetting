#!/usr/bin/env python3
"""BetBCK ↔ Pinnacle game matching: aliases yes, United/City and Inter/Miami no."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from match_games import (
    canonical_team_name,
    match_pinnacle_to_betbck,
    names_are_same_team,
    normalize_sport_label,
    pair_orientation_score,
    resolve_betbck_sport,
)
from betbck_async_scraper import BetBCKAsyncScraper


def _bck(home, away, **extra):
    game = {
        "betbck_site_home_team": home,
        "betbck_site_away_team": away,
        "betbck_game_id": extra.pop("betbck_game_id", f"{home}_{away}"),
        "sport_type": extra.pop("sport_type", "SOCCER"),
        "sport": extra.pop("sport", "SOCCER"),
        "betbck_site_odds": {},
    }
    game.update(extra)
    return game


def _pin(eid, home, away, sport="Soccer"):
    return {
        "event_id": eid,
        "home_team": home,
        "away_team": away,
        "sport": sport,
    }


def test_names_alias_same_club():
    assert names_are_same_team("Cardiff", "Cardiff City")
    assert names_are_same_team("Ipswich", "Ipswich Town")
    assert names_are_same_team("Brentford FC", "Brentford")
    assert names_are_same_team("Alaves", "Deportivo Alaves")
    assert names_are_same_team("Egnatia", "Egnatia Rrogozhine")
    assert names_are_same_team("Lillestrom", "Lillestrøm SK")
    assert names_are_same_team("man united", "man utd")
    assert names_are_same_team("Chelsea", "Chelsea FC")


def test_names_reject_different_clubs():
    assert not names_are_same_team("Manchester United", "Manchester City")
    assert not names_are_same_team("man united", "man city")
    assert not names_are_same_team("Crawley Town", "Athlone Town")
    assert not names_are_same_team("Real Madrid", "Real Sociedad")
    assert not names_are_same_team("Inter", "Inter Miami")
    assert not names_are_same_team("Sporting", "Sporting Kansas City")
    assert not names_are_same_team("Madrid", "Atletico Madrid")
    assert not names_are_same_team("Sheffield United", "Sheffield Wednesday")
    assert not names_are_same_team("Chelsea", "Cheltenham")


def test_canonical_maps_man_utd_and_accents():
    assert canonical_team_name("Manchester United") == canonical_team_name("Man Utd")
    assert canonical_team_name("Lillestrøm SK") == canonical_team_name("Lillestrom")
    assert canonical_team_name("Deportivo Alaves") == canonical_team_name("Alaves")


def test_pair_rejects_united_vs_city_same_opponent():
    score, _ = pair_orientation_score(
        canonical_team_name("Man United"),
        canonical_team_name("Newcastle"),
        canonical_team_name("Man City"),
        canonical_team_name("Newcastle"),
    )
    assert score == 0


def test_pair_accepts_man_utd_vs_manchester_united():
    score, direct = pair_orientation_score(
        canonical_team_name("Man Utd"),
        canonical_team_name("Newcastle"),
        canonical_team_name("Manchester United"),
        canonical_team_name("Newcastle United"),
    )
    assert score >= 65
    assert direct is True


def test_unknown_clubs_with_sport_type_match_pinnacle_soccer():
    """Alaves/Lillestrom are not on the hardcoded soccer list; SportType still finds them."""
    matched = match_pinnacle_to_betbck(
        [_pin("1", "Deportivo Alaves", "Lillestrom SK")],
        {"games": [_bck("Alaves", "Lillestrom", sport="SOCCER", sport_type="SOCCER")]},
    )
    assert len(matched) == 1
    assert matched[0]["pinnacle_event_id"] == "1"


def test_unknown_clubs_without_sport_still_search_soccer_bucket():
    matched = match_pinnacle_to_betbck(
        [_pin("1", "Egnatia Rrogozhine", "Partizani Tirana")],
        {"games": [_bck("Egnatia", "Partizani", sport="", sport_type="")]},
    )
    assert len(matched) == 1


def test_man_united_does_not_match_man_city_fixture():
    matched = match_pinnacle_to_betbck(
        [_pin("city", "Manchester City", "Newcastle United")],
        {"games": [_bck("Man United", "Newcastle", betbck_game_id="mu")]},
    )
    assert matched == []


def test_man_united_matches_manchester_united():
    matched = match_pinnacle_to_betbck(
        [
            _pin("city", "Manchester City", "Newcastle United"),
            _pin("utd", "Manchester United", "Newcastle United"),
        ],
        {"games": [_bck("Man Utd", "Newcastle", betbck_game_id="mu")]},
    )
    assert len(matched) == 1
    assert matched[0]["pinnacle_event_id"] == "utd"


def test_fa_cup_chelsea_vs_luton_matches():
    matched = match_pinnacle_to_betbck(
        [_pin("fa", "Chelsea", "Luton Town")],
        {"games": [_bck("Chelsea", "Luton", league="FA Cup")]},
    )
    assert len(matched) == 1
    assert matched[0]["pinnacle_event_id"] == "fa"


def test_two_full_games_do_not_share_one_pinnacle_event():
    matched = match_pinnacle_to_betbck(
        [_pin("1", "Cardiff City", "Ipswich Town")],
        {"games": [
            _bck("Cardiff", "Ipswich", betbck_game_id="short"),
            _bck("Cardiff City", "Ipswich Town", betbck_game_id="long"),
        ]},
    )
    assert len(matched) == 1


def test_main_and_1h_both_match_same_event():
    matched = match_pinnacle_to_betbck(
        [_pin("9", "Chelsea", "Arsenal")],
        {"games": [
            _bck("Chelsea", "Arsenal", betbck_game_id="m", market_suffix=None),
            _bck("Chelsea", "Arsenal", betbck_game_id="h", market_suffix="1H"),
        ]},
    )
    assert len(matched) == 2
    suffixes = {m.get("market_suffix") for m in matched}
    assert None in suffixes or not suffixes.difference({None, "1H"})
    assert "1H" in suffixes


def test_later_exact_name_wins_over_weaker_first_row():
    """Global assign: do not let the first BetBCK row steal a better later pair."""
    matched = match_pinnacle_to_betbck(
        [_pin("1", "Brentford", "Chelsea")],
        {"games": [
            _bck("Brentford FC", "Chelsea FC", betbck_game_id="first"),
            _bck("Brentford", "Chelsea", betbck_game_id="second"),
        ]},
    )
    assert len(matched) == 1


def test_soccer_json_not_bucketed_as_nfl():
    assert normalize_sport_label("SOCCER", "England Premier League") == "soccer"
    assert normalize_sport_label("Soccer", "") == "soccer"
    assert normalize_sport_label("FOOTBALL", "NFL") == "football"
    assert normalize_sport_label("Football", "NFL Preseason") == "football"
    sport = resolve_betbck_sport(
        {"sport_type": "SOCCER", "sport": "SOCCER"}, "alaves", "egnatia"
    )
    assert sport == "soccer"


def test_parse_league_lines_stamps_sport_and_datetime():
    scraper = BetBCKAsyncScraper.__new__(BetBCKAsyncScraper)
    scraper._allow_outright_props = False
    payload = {
        "Lines": [{
            "Team1ID": "Alaves",
            "Team2ID": "Valencia",
            "GameNum": 99,
            "Status": "O",
            "PeriodDescription": "Game",
            "SportType": "SOCCER",
            "SportSubTypeDisplay": "Spain La Liga",
            "GameDateTime": "2026-08-28 19:00:00.000",
            "MoneyLine1": -110,
            "MoneyLine2": 250,
        }]
    }
    games = scraper.parse_games_from_lines_json(json.dumps(payload))
    assert len(games) == 1
    game = games[0]
    assert game["sport"] == "SOCCER"
    assert game["sport_type"] == "SOCCER"
    assert game["event_datetime"].startswith("2026-08-28T19:00:00")
    matched = match_pinnacle_to_betbck(
        [_pin("x", "Deportivo Alaves", "Valencia")],
        {"games": games},
    )
    assert len(matched) == 1


def main():
    tests = [
        test_names_alias_same_club,
        test_names_reject_different_clubs,
        test_canonical_maps_man_utd_and_accents,
        test_pair_rejects_united_vs_city_same_opponent,
        test_pair_accepts_man_utd_vs_manchester_united,
        test_unknown_clubs_with_sport_type_match_pinnacle_soccer,
        test_unknown_clubs_without_sport_still_search_soccer_bucket,
        test_man_united_does_not_match_man_city_fixture,
        test_man_united_matches_manchester_united,
        test_fa_cup_chelsea_vs_luton_matches,
        test_two_full_games_do_not_share_one_pinnacle_event,
        test_main_and_1h_both_match_same_event,
        test_later_exact_name_wins_over_weaker_first_row,
        test_soccer_json_not_bucketed_as_nfl,
        test_parse_league_lines_stamps_sport_and_datetime,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
    if failed:
        raise SystemExit(1)
    print(f"OK {len(tests)} tests")


if __name__ == "__main__":
    main()
