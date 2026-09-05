#!/usr/bin/env python3
"""Fallback card rows must never invent +81% EV from a Draw no-vig."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pod_utils import (
    build_fallback_market_rows,
    fallback_moneyline_side,
    filter_realistic_ev_bets,
    is_timestamp_event_id,
    should_publish_event_card,
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


def test_old_bug_81pct_plus_na_card_is_not_published():
    """Even if Draw NVP is wrongly priced onto away +795, the 15% cap drops
    +81% and the leftover N/A rows must not become a card."""
    leaked = [
        {"market": "Moneyline", "selection": "alianza valledupar",
         "pinnacle_nvp": "+394", "betbck_odds": "+795", "ev": "+81.17%"},
        {"market": "Moneyline", "selection": "america de cali",
         "pinnacle_nvp": "N/A", "betbck_odds": "-285", "ev": "N/A"},
        {"market": "Spread", "selection": "america de cali",
         "pinnacle_nvp": "N/A", "betbck_odds": "-130", "ev": "N/A"},
        {"market": "Total", "selection": "Over",
         "pinnacle_nvp": "N/A", "betbck_odds": "-110", "ev": "N/A"},
    ]
    kept = filter_realistic_ev_bets(leaked)
    assert all(r["ev"] != "+81.17%" for r in kept)
    assert not any(abs(float(str(r["ev"]).replace("%", ""))) > 15
                   for r in kept if str(r.get("ev", "")).upper() != "N/A")
    assert should_publish_event_card(kept, from_fallback=True) is False
    assert should_publish_event_card(
        kept, event_id_suspect=True, from_fallback=True
    ) is False


def test_suspect_fallback_card_is_not_published():
    rows = build_fallback_market_rows(
        _cali_bck(),
        market_type="Moneyline",
        team_for_bet="Draw",
        no_vig="+394",
        pod_home="america de cali",
        pod_away="alianza valledupar",
        event_id_suspect=True,
    )
    assert should_publish_event_card(
        rows, event_id_suspect=True, from_fallback=True
    ) is False


def test_priced_draw_fallback_still_publishes():
    rows = build_fallback_market_rows(
        _cali_bck(),
        market_type="Moneyline",
        team_for_bet="Draw",
        no_vig="+394",
        pod_home="america de cali",
        pod_away="alianza valledupar",
        event_id_suspect=False,
    )
    assert should_publish_event_card(rows, from_fallback=True) is True


if __name__ == "__main__":
    test_timestamp_event_id()
    test_draw_is_not_away()
    test_draw_nvp_does_not_price_alianza_moneyline()
    test_suspect_timestamp_id_never_computes_ev()
    test_away_alert_still_attaches_to_away_only()
    test_unrealistic_fallback_ev_is_dropped()
    test_old_bug_81pct_plus_na_card_is_not_published()
    test_suspect_fallback_card_is_not_published()
    test_priced_draw_fallback_still_publishes()
    print("test_fallback_markets: all passed")
