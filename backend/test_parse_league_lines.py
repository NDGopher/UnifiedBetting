#!/usr/bin/env python3
"""Offline parser tests for Get_LeagueLines2 JSON (no live BetBCK)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from betbck_scraper import parse_specific_game_from_lines_json, parse_specific_game_from_search_html


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


if __name__ == "__main__":
    tests = [
        test_status_i_still_returns_spread_game,
        test_status_open_word_still_returns,
        test_gamenum_int_and_string_merge,
        test_closed_status_is_skipped,
        test_json_with_preamble_still_detected,
        test_no_moneyline_still_counts_as_found,
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
