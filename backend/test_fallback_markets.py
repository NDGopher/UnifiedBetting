#!/usr/bin/env python3
"""Fallback card rows must never invent +81% EV from a Draw no-vig."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pod_utils import (
    build_fallback_market_rows,
    fallback_moneyline_side,
    is_timestamp_event_id,
)


def _cali_bck():
    return {
        "home_moneyline_american": "-285",
        "away_moneyline_american": "+795",
        "draw_moneyline_american": "+350",
        "home_spreads": [{"line": "-1.25", "odds": "-130"}],
        "away_spreads": [{"line": "+1.25", "odds": "+100"}],
        "game_total_line": "2.5",
        "game_total_over_odds": "-110",
        "game_total_under_odds": "-130",
    }


def test_timestamp_event_id():
    assert is_timestamp_event_id("1788467456273") is True
    assert is_timestamp_event_id(1634729454) is False
    assert is_timestamp_event_id("not-an-id") is False


def test_draw_is_not_away():
    assert fallback_moneyline_side("Draw", "america de cali", "alianza valledupar") == "draw"
    assert fallback_moneyline_side("Alianza Valledupar", "america de cali", "alianza valledupar") == "away"
    assert fallback_moneyline_side("America de Cali", "america de cali", "alianza valledupar") == "home"
    assert fallback_moneyline_side("", "america de cali", "alianza valledupar") is None


def test_draw_nvp_does_not_price_alianza_moneyline():
    """Reproduction: POD Draw no-vig +394 vs BCK away +795 must not become +81%."""
    rows = build_fallback_market_rows(
        _cali_bck(),
        market_type="Moneyline",
        team_for_bet="Draw",
        line_value="",
        no_vig="+394",
        pod_home="america de cali",
        pod_away="alianza valledupar",
        event_id_suspect=False,
    )
    by_sel = {(r["market"], r["selection"]): r for r in rows}
    away = by_sel[("Moneyline", "alianza valledupar")]
    home = by_sel[("Moneyline", "america de cali")]
    draw = by_sel[("Moneyline", "Draw")]
    assert away["pinnacle_nvp"] == "N/A"
    assert away["ev"] == "N/A"
    assert home["pinnacle_nvp"] == "N/A"
    assert home["ev"] == "N/A"
    assert draw["pinnacle_nvp"] == "+394"
    assert draw["ev"] != "N/A"
    ev = float(draw["ev"].replace("%", ""))
    assert abs(ev) <= 15


def test_suspect_timestamp_id_never_computes_ev():
    rows = build_fallback_market_rows(
        _cali_bck(),
        market_type="Moneyline",
        team_for_bet="Draw",
        line_value="",
        no_vig="+394",
        pod_home="america de cali",
        pod_away="alianza valledupar",
        event_id_suspect=True,
    )
    assert rows
    assert all(r["pinnacle_nvp"] == "N/A" for r in rows)
    assert all(r["ev"] == "N/A" for r in rows)
    assert not any("81" in str(r["ev"]) for r in rows)


def test_away_alert_still_attaches_to_away_only():
    rows = build_fallback_market_rows(
        _cali_bck(),
        market_type="Moneyline",
        team_for_bet="Alianza Valledupar",
        no_vig="+800",
        pod_home="america de cali",
        pod_away="alianza valledupar",
        event_id_suspect=False,
    )
    by_sel = {(r["market"], r["selection"]): r for r in rows}
    assert by_sel[("Moneyline", "alianza valledupar")]["pinnacle_nvp"] == "+800"
    assert by_sel[("Moneyline", "america de cali")]["pinnacle_nvp"] == "N/A"
    assert by_sel[("Moneyline", "Draw")]["pinnacle_nvp"] == "N/A"


def test_unrealistic_fallback_ev_is_dropped():
    """If a matching row still computes |EV| > 15%, drop it instead of publishing."""
    rows = build_fallback_market_rows(
        {"away_moneyline_american": "+795", "home_moneyline_american": "-285"},
        market_type="Moneyline",
        team_for_bet="alianza valledupar",
        no_vig="+394",
        pod_home="america de cali",
        pod_away="alianza valledupar",
        event_id_suspect=False,
    )
    away_rows = [r for r in rows if r["selection"] == "alianza valledupar"]
    assert away_rows == []


if __name__ == "__main__":
    test_timestamp_event_id()
    test_draw_is_not_away()
    test_draw_nvp_does_not_price_alianza_moneyline()
    test_suspect_timestamp_id_never_computes_ev()
    test_away_alert_still_attaches_to_away_only()
    test_unrealistic_fallback_ev_is_dropped()
    print("test_fallback_markets: all passed")
