#!/usr/bin/env python3
"""Offline parser tests for Get_LeagueLines2 JSON (no live BetBCK)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from betbck_scraper import (
    _score_team_pair,
    _team_name_pair_score,
    parse_specific_game_from_lines_json,
    parse_specific_game_from_search_html,
)


def _line(**kwargs):
    base = {
        "Team1ID": "Cincinnati Bengals",
        "Team2ID": "Philadelphia Eagles",
        "GameNum": 16346,
        "Status": "O",
        "PeriodDescription": "Game",
        "PeriodNumber": 0,
        "Spread": 3,
        "SpreadAdj1": -110,
        "SpreadAdj2": -110,
        "TotalPoints": 38.5,
        "TtlPtsAdj1": -110,
        "TtlPtsAdj2": -110,
        "MoneyLine1": 0,
        "MoneyLine2": 0,
        "GameDateTime": "2026-08-28 19:00:00.000",
        "SportType": "FOOTBALL",
        "SportSubType": "NFL",
        "SportSubTypeDisplay": "NFL Preseason",
        "ScheduleText": "Preseason Week 3 - CBS",
    }
    base.update(kwargs)
    return base


def _parse(lines, home="Philadelphia Eagles", away="Cincinnati Bengals"):
    return parse_specific_game_from_lines_json(
        {"Lines": lines}, home, away, event_id="test"
    )


def test_status_i_still_returns_spread_game():
    result = _parse([_line(Status="I")])
    assert result is not None, "Status I must not drop a matched NFL game"
    assert result.get("away_spreads") or result.get("home_spreads")


def test_status_open_word_still_returns():
    result = _parse([_line(Status="Open")])
    assert result is not None


def test_gamenum_int_and_string_merge():
    result = _parse([
        _line(GameNum=16346, Status="I"),
        _line(GameNum="16346", Status="I", PeriodDescription="1st Half", PeriodNumber=1),
    ])
    assert result is not None
    assert "full_game" in result.get("row_data", {})
    assert "half_1" in result.get("row_data", {})


def test_closed_status_is_skipped():
    result = _parse([_line(Status="C")])
    assert result is None


def test_json_with_preamble_still_detected():
    payload = {"status": "Success", "account": "x" * 800, "Lines": [_line(Status="I")]}
    raw = json.dumps(payload)
    assert '"Lines"' not in raw[:500]
    result = parse_specific_game_from_search_html(
        raw, "Philadelphia Eagles", "Cincinnati Bengals", event_id="test"
    )
    assert result is not None


def test_no_moneyline_still_counts_as_found():
    result = _parse([_line(Status="I", MoneyLine1=None, MoneyLine2=None)])
    assert result is not None
    assert result.get("game_total_line")


def test_flipped_soccer_ah_follows_ml_favorite():
    """Sportivo is Team1, Nacional is POD/Pin home and the ML favorite.

    JSON Spread=-0.25 would map to Nacional +0.25 after a naive flip.
    The site lists Nacional -0.25 -135; keep that juice on the laying number.
    """
    result = parse_specific_game_from_lines_json(
        {"Lines": [_line(
            Team1ID="Sportivo Luqueno",
            Team2ID="Nacional Asuncion",
            Spread=-0.25,
            SpreadAdj1=105,
            SpreadAdj2=-135,
            MoneyLine1=250,
            MoneyLine2=110,
            MoneyLineDraw=210,
            SportType="SOCCER",
            SportSubType="PARAGUAY",
            SportSubTypeDisplay="Division Profesional",
            PeriodDescription="Game",
            GameNum=619171580,
        )]},
        "Nacional Asuncion",
        "Sportivo Luqueno",
        event_id="1634197096",
    )
    assert result is not None
    assert result.get("home_moneyline_american") == "+110"
    assert result.get("away_moneyline_american") == "+250"
    home_sp = result["home_spreads"][0]
    assert float(home_sp["line"]) == -0.25
    assert home_sp["odds"] == "-135"
    away_sp = result["away_spreads"][0]
    assert float(away_sp["line"]) == 0.25
    assert away_sp["odds"] == "+105"


def test_flipped_cfb_maps_spread_via_orientation_without_ml():
    """Miami listed first, Pitt is POD home. Spread is Team1 (Miami) +16.5. No ML."""
    result = parse_specific_game_from_lines_json(
        {"Lines": [_line(
            Team1ID="Miami Ohio",
            Team2ID="Pittsburgh",
            Spread=16.5,
            SpreadAdj1=-110,
            SpreadAdj2=-110,
            MoneyLine1=0,
            MoneyLine2=0,
            SportType="FOOTBALL",
            SportSubType="NCAA",
            SportSubTypeDisplay="NCAA Football",
            PeriodDescription="Game",
            GameNum=88001,
        )]},
        "Pittsburgh",
        "Miami Ohio",
        event_id="cfb-pitt",
    )
    assert result is not None
    assert float(result["home_spreads"][0]["line"]) == -16.5
    assert float(result["away_spreads"][0]["line"]) == 16.5


def test_cfb_single_away_ml_flips_favorite_getting_points():
    """Flipped listing: Team1 is CMU (dog, +340) but Spread is -10.5 (not Team1's number).

    Naive flip maps New Mexico to +10.5. Away ML +340 must force NM to lay -10.5.
    """
    result = parse_specific_game_from_lines_json(
        {"Lines": [_line(
            Team1ID="Central Michigan",
            Team2ID="New Mexico",
            Spread=-10.5,
            SpreadAdj1=-105,
            SpreadAdj2=-105,
            MoneyLine1=340,
            MoneyLine2=0,
            SportType="FOOTBALL",
            SportSubType="NCAA",
            SportSubTypeDisplay="NCAA Football",
            PeriodDescription="Game",
            GameNum=88002,
        )]},
        "New Mexico",
        "Central Michigan",
        event_id="cfb-unm",
    )
    assert result is not None
    assert result.get("away_moneyline_american") == "+340"
    assert float(result["home_spreads"][0]["line"]) == -10.5
    assert float(result["away_spreads"][0]["line"]) == 10.5


def test_texas_vs_texas_st_orientation_is_not_tied():
    """token_set('texas','texas st') is 100 both ways. Extra 'state' must break the tie."""
    assert _team_name_pair_score("texas st", "texas state") == 100
    assert _team_name_pair_score("texas", "texas") == 100
    assert _team_name_pair_score("texas st", "texas") < 82
    assert _team_name_pair_score("texas", "texas state") < 82
    matched, local_is_pod_home, _, _ = _score_team_pair(
        "Texas St", "Texas", "Texas", "Texas State"
    )
    assert matched is True
    assert local_is_pod_home is False


def test_texas_1h_keeps_plus_105_on_texas_state():
    """BetBCK lists Texas St first at +17.5 +105; Texas is -17.5 -115.

    Wrong orientation + sign-align produced Texas -17.5 +105 (fake +18% EV).
    """
    import datetime
    _soon = (datetime.datetime.now() + datetime.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S.000")
    fg = _line(
        Team1ID="Texas St",
        Team2ID="Texas",
        Spread=29.5,
        SpreadAdj1=-105,
        SpreadAdj2=-105,
        MoneyLine1=0,
        MoneyLine2=-2000,
        SportType="FOOTBALL",
        SportSubType="NCAA",
        SportSubTypeDisplay="NCAA Football",
        PeriodDescription="Game",
        GameNum=88010,
        GameDateTime=_soon,
    )
    h1 = _line(
        Team1ID="Texas St",
        Team2ID="Texas",
        Spread=17.5,
        SpreadAdj1=105,
        SpreadAdj2=-115,
        MoneyLine1=0,
        MoneyLine2=-800,
        SportType="FOOTBALL",
        SportSubType="NCAA",
        SportSubTypeDisplay="NCAA Football",
        PeriodDescription="1st Half",
        PeriodNumber=1,
        GameNum=88010,
        GameDateTime=_soon,
    )
    result = parse_specific_game_from_lines_json(
        {"Lines": [fg, h1]},
        "Texas",
        "Texas State",
        event_id="cfb-texas",
    )
    assert result is not None
    h1_row = result["row_data"]["half_1"]
    home_sp = h1_row["home_spreads"][0]
    away_sp = h1_row["away_spreads"][0]
    assert float(home_sp["line"]) == -17.5
    assert home_sp["odds"] == "-115"
    assert float(away_sp["line"]) == 17.5
    assert away_sp["odds"] == "+105"


def test_cfb_zero_ml_does_not_block_parse():
    result = _parse([_line(
        Team1ID="Hawaii",
        Team2ID="UNLV",
        Spread=3,
        MoneyLine1=0,
        MoneyLine2=0,
        SportType="FOOTBALL",
        SportSubType="NCAA",
    )], home="Hawaii", away="UNLV")
    assert result is not None
    assert float(result["home_spreads"][0]["line"]) == 3


if __name__ == "__main__":
    tests = [
        test_status_i_still_returns_spread_game,
        test_status_open_word_still_returns,
        test_gamenum_int_and_string_merge,
        test_closed_status_is_skipped,
        test_json_with_preamble_still_detected,
        test_no_moneyline_still_counts_as_found,
        test_flipped_soccer_ah_follows_ml_favorite,
        test_flipped_cfb_maps_spread_via_orientation_without_ml,
        test_cfb_single_away_ml_flips_favorite_getting_points,
        test_texas_vs_texas_st_orientation_is_not_tied,
        test_texas_1h_keeps_plus_105_on_texas_state,
        test_cfb_zero_ml_does_not_block_parse,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("ok ", fn.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", fn.__name__, e)
    if failed:
        sys.exit(1)
    print("ALL", len(tests), "TESTS PASSED")
