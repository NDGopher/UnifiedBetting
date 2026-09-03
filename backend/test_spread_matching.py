#!/usr/bin/env python3
"""Signed spread matching: same-order NFL, reversed soccer 1H, no fake 41% EV."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pod_utils import (
    align_bck_spread_signs_to_pin,
    analyze_markets_for_ev,
    filter_realistic_ev_bets,
    pin_spread_quote_for_bet,
    spread_quotes_are_same_side,
)


def _spread(hdp, nvp_home, nvp_away, am_home, am_away):
    return {
        "hdp": hdp,
        "nvp_home": nvp_home,
        "nvp_away": nvp_away,
        "nvp_american_home": am_home,
        "nvp_american_away": am_away,
    }


def test_same_order_home_matches_pin_hdp():
    pin = _spread(3.5, 1.91, 1.91, "-110", "-110")
    quote = pin_spread_quote_for_bet(pin, 3.5, "home", nvp_swapped=False)
    assert quote is not None
    nvp, am, line = quote
    assert am == "-110"
    assert abs(line - 3.5) < 0.01
    away = pin_spread_quote_for_bet(pin, -3.5, "away", nvp_swapped=False)
    assert away is not None and away[1] == "-110"


def test_home_plus_does_not_match_opposite_hdp():
    pin = _spread(-3.5, 1.91, 1.91, "-110", "-110")
    assert pin_spread_quote_for_bet(pin, 3.5, "home", nvp_swapped=False) is None


def test_reversed_home_plus_uses_pin_away_at_negated_hdp():
    """POD Roma is Pin away. Roma +0.25 is Pin hdp -0.25 nvp_away, not hdp +0.25 nvp_home."""
    trap = _spread(0.25, 1.2488, 5.02, "-402", "+402")
    real = _spread(-0.25, 2.10, 1.80, "+110", "-125")
    assert pin_spread_quote_for_bet(trap, 0.25, "home", nvp_swapped=True) is None
    quote = pin_spread_quote_for_bet(real, 0.25, "home", nvp_swapped=True)
    assert quote is not None
    nvp, am, line = quote
    assert am == "-125"
    assert abs(line - 0.25) < 0.01
    assert abs(nvp - 1.80) < 0.001


def test_opposite_side_prices_rejected():
    assert spread_quotes_are_same_side("-130", "-402") is False
    assert spread_quotes_are_same_side("-135", "-289") is False
    assert spread_quotes_are_same_side("-130", "+402") is False
    assert spread_quotes_are_same_side("-110", "+100") is True
    assert spread_quotes_are_same_side("-110", "-115") is True


def test_filter_drops_41_pct_before_publish():
    kept = filter_realistic_ev_bets([
        {"market": "1H Spread", "selection": "Home", "line": "0.25", "ev": "41.65%"},
        {"market": "1H Spread", "selection": "Away", "line": "-0.25", "ev": "-60.14%"},
        {"market": "Total", "selection": "Under", "line": "2.5", "ev": "-2.10%"},
        {"market": "Total", "selection": "Over", "line": "37.5", "ev": "N/A"},
    ])
    assert len(kept) == 2
    assert {k["line"] for k in kept} == {"2.5", "37.5"}


def _total(points, nvp_over, nvp_under, am_over, am_under):
    return {
        "points": points,
        "nvp_over": nvp_over,
        "nvp_under": nvp_under,
        "nvp_american_over": am_over,
        "nvp_american_under": am_under,
    }


def _pin_payload(home, away, fg_spreads, h1_spreads, fg_totals=None, h1_totals=None):
    num_0 = {
        "money_line": {
            "nvp_home": 1.91,
            "nvp_away": 1.91,
            "nvp_american_home": "-110",
            "nvp_american_away": "-110",
        },
        "spreads": fg_spreads,
    }
    if fg_totals is not None:
        num_0["totals"] = fg_totals
    num_1 = {
        "money_line": {},
        "spreads": h1_spreads,
    }
    if h1_totals is not None:
        num_1["totals"] = h1_totals
    return {
        "data": {
            "home": home,
            "away": away,
            "periods": {
                "num_0": num_0,
                "num_1": num_1,
            },
        }
    }


def test_nfl_spread_same_order_still_matches():
    bet = {
        "pod_home_team": "Dallas Cowboys",
        "pod_away_team": "New Orleans Saints",
        "home_spreads": [{"line": 3.5, "odds": "-110"}],
        "away_spreads": [{"line": -3.5, "odds": "-110"}],
    }
    pin = _pin_payload(
        "Dallas Cowboys",
        "New Orleans Saints",
        {"3.5": _spread(3.5, 1.91, 1.91, "-110", "-110")},
        {},
    )
    rows = analyze_markets_for_ev(bet, pin)
    spreads = [r for r in rows if r.get("market") == "Spread"]
    assert any(r["selection"] == "Home" and "3.5" in str(r["line"]) for r in spreads)
    home = next(r for r in spreads if r["selection"] == "Home")
    assert home["pinnacle_nvp"] == "-110"
    ev = float(home["ev"].replace("%", ""))
    assert abs(ev) < 1.0


def test_roma_1h_reversed_matches_signed_line_not_trap():
    """Fiorentina vs Roma on Pin, Roma vs Fiorentina on POD. 1H Roma +0.25 -130."""
    bet = {
        "pod_home_team": "AS Roma",
        "pod_away_team": "Fiorentina",
        "home_spreads": [{"line": 0.75, "odds": "-110"}],
        "away_spreads": [{"line": -0.75, "odds": "-110"}],
        "1H_data": {
            "home_spreads": [{"line": 0.25, "odds": "-130"}],
            "away_spreads": [{"line": -0.25, "odds": "+100"}],
        },
    }
    pin = _pin_payload(
        "Fiorentina",
        "AS Roma",
        {
            "0.75": _spread(0.75, 1.91, 1.91, "-110", "-110"),
            "-0.75": _spread(-0.75, 1.91, 1.91, "-110", "-110"),
        },
        {
            # Trap: Fio +0.25 priced as huge favorite. Old matcher paired this with Roma +0.25.
            "0.25": _spread(0.25, 1.2488, 5.02, "-402", "+402"),
            # Real: Fio -0.25 / Roma +0.25 at -125.
            "-0.25": _spread(-0.25, 2.10, 1.80, "+110", "-125"),
        },
    )
    rows = analyze_markets_for_ev(bet, pin)
    evs = [r["ev"] for r in rows]
    assert not any(abs(float(str(e).replace("%", ""))) > 15 for e in evs)

    h1_home = [r for r in rows if r.get("market") == "1H Spread" and r.get("selection") == "Home"]
    assert len(h1_home) == 1, f"expected one 1H home spread, got {rows}"
    row = h1_home[0]
    assert row["pinnacle_nvp"] == "-125"
    assert abs(float(row["ev"].replace("%", ""))) < 15
    # Must not publish the -402 trap as a 41% EV.
    assert row["pinnacle_nvp"] != "-402"


def test_alt_line_41_pct_never_published_same_order():
    """Same-order books: BCK +0.25 -130 vs Pin +0.25 -402 is a far alt — drop, don't flash +41%."""
    bet = {
        "pod_home_team": "AS Roma",
        "pod_away_team": "Fiorentina",
        "1H_data": {
            "home_spreads": [{"line": "+0.25", "odds": "-130"}],
            "away_spreads": [{"line": "-0.25", "odds": "+100"}],
        },
    }
    pin = _pin_payload(
        "AS Roma",
        "Fiorentina",
        {"0.75": _spread(0.75, 1.91, 1.91, "-110", "-110")},
        {"0.25": _spread(0.25, 1.2488, 5.02, "-402", "+402")},
    )
    rows = analyze_markets_for_ev(bet, pin)
    h1 = [r for r in rows if str(r.get("market", "")).startswith("1H Spread")]
    assert h1 == [], f"unrealistic 1H spread must not be published: {h1}"
    assert not any("41" in str(r.get("ev")) for r in rows)


def _ev_kwargs():
    return dict(
        period_label="",
        sport="soccer",
        event_name="Cardiff City vs Norwich City",
        start_time_fmt="-",
        league="Championship",
        event_id="1",
        market_suffix=None,
        meta_limits={},
    )


def test_ev_table_uses_orientation_not_exact_names():
    """Cardiff vs Cardiff City already matched; spreads must still map."""
    from calculate_ev_table import build_ev_spread_rows
    pin = {"0.25": _spread(0.25, 1.91, 1.91, "-110", "-110")}
    rows = build_ev_spread_rows(
        pin,
        [{"line": "0.25", "odds": "-110"}],
        [{"line": "-0.25", "odds": "-110"}],
        "direct",
        "Cardiff City",
        "Norwich City",
        **_ev_kwargs(),
    )
    assert len(rows) == 2
    home = next(r for r in rows if "Cardiff City" in r["bet"])
    assert home["pinnacle_nvp"] == "-110"
    assert abs(home["ev_val"]) < 0.02


def test_ev_table_flipped_orientation_maps_top_to_away():
    from calculate_ev_table import build_ev_spread_rows
    pin = {"-0.75": _spread(-0.75, 1.80, 2.05, "-125", "+105")}
    # BCK lists Fiorentina on top with -0.75; Pin home is Roma laying -0.75.
    rows = build_ev_spread_rows(
        pin,
        [{"line": "0.75", "odds": "+105"}],
        [{"line": "-0.75", "odds": "-125"}],
        "flipped",
        "AS Roma",
        "Fiorentina",
        period_label="",
        sport="soccer",
        event_name="AS Roma vs Fiorentina",
        start_time_fmt="-",
        league="Serie A",
        event_id="2",
        market_suffix=None,
        meta_limits={},
    )
    assert len(rows) >= 1
    roma = next(r for r in rows if "AS Roma" in r["bet"])
    assert roma["pinnacle_nvp"] == "-125"


def test_nacional_asuncion_does_not_show_plus_quarter_at_minus_juice():
    """Flipped BetBCK listing: Nacional is home/favorite, not Sportivo's +0.25 -135."""
    bet = {
        "pod_home_team": "Nacional Asuncion",
        "pod_away_team": "Sportivo Luqueno",
        "home_moneyline_american": "+110",
        "away_moneyline_american": "+250",
        "home_spreads": [{"line": "-0.25", "odds": "-135"}],
        "away_spreads": [{"line": "0.25", "odds": "+105"}],
    }
    pin = _pin_payload(
        "Nacional Asuncion",
        "Sportivo Luqueno",
        {
            "0.25": _spread(0.25, 1.346, 3.89, "-289", "+289"),
            "-0.25": _spread(-0.25, 1.74, 2.05, "-135", "+105"),
        },
        {},
    )
    rows = analyze_markets_for_ev(bet, pin)
    evs = [abs(float(str(r["ev"]).replace("%", ""))) for r in rows if r.get("market") == "Spread"]
    assert evs and max(evs) < 15
    home = next(r for r in rows if r.get("market") == "Spread" and r.get("selection") == "Home")
    assert float(home["line"]) == -0.25
    assert home["betbck_odds"] == "-135"
    assert home["pinnacle_nvp"] != "-289"


def test_wrong_plus_quarter_minus_135_never_publishes_29pct():
    """If a caller still passes the unaligned +0.25 -135, do not pair Pin -289."""
    bet = {
        "pod_home_team": "Nacional Asuncion",
        "pod_away_team": "Sportivo Luqueno",
        "home_spreads": [{"line": "+0.25", "odds": "-135"}],
        "away_spreads": [{"line": "-0.25", "odds": "+105"}],
    }
    pin = _pin_payload(
        "Nacional Asuncion",
        "Sportivo Luqueno",
        {"0.25": _spread(0.25, 1.346, 3.89, "-289", "+289")},
        {},
    )
    rows = analyze_markets_for_ev(bet, pin)
    spreads = [r for r in rows if r.get("market") == "Spread"]
    assert spreads == [], f"trap +0.25/-289 must not publish: {spreads}"


def test_preseason_missing_pin_number_shows_unpriced_rows():
    """Pin 36.5 / 3.5 vs BCK 37.5 / ±2: show BCK lines, never EV-compare different numbers."""
    bet = {
        "pod_home_team": "Dallas Cowboys",
        "pod_away_team": "New Orleans Saints",
        "home_spreads": [{"line": "+2", "odds": "-110"}],
        "away_spreads": [{"line": "-2", "odds": "-110"}],
        "game_total_line": 37.5,
        "game_total_over_odds": "-110",
        "game_total_under_odds": "-110",
    }
    pin = _pin_payload(
        "Dallas Cowboys",
        "New Orleans Saints",
        {"3.5": _spread(3.5, 1.91, 1.91, "-110", "-110")},
        {},
        fg_totals={"36.5": _total(36.5, 1.83, 1.91, "-125", "-110")},
    )
    rows = analyze_markets_for_ev(bet, pin)
    assert rows, "card must not be empty when BetBCK has lines"
    totals = [r for r in rows if r.get("market") == "Total"]
    spreads = [r for r in rows if r.get("market") == "Spread"]
    assert len(totals) == 2
    assert {r["selection"] for r in totals} == {"Over", "Under"}
    for r in totals:
        assert "37.5" in str(r["line"])
        assert r["pinnacle_nvp"] == "N/A"
        assert r["ev"] == "N/A"
        assert r.get("unmatched_line") is True
        assert r["pinnacle_nvp"] != "-125"
    assert len(spreads) == 2
    for r in spreads:
        assert r["pinnacle_nvp"] == "N/A"
        assert r["ev"] == "N/A"
        assert r.get("unmatched_line") is True
    for r in rows:
        ev = str(r.get("ev") or "")
        if ev.upper() != "N/A":
            assert abs(float(ev.replace("%", ""))) < 15


def test_pitt_miami_cfb_flipped_signs_match_without_bck_ml():
    """Pitt is home favorite -16.5. BCK JSON had no ML and posted home +16.5."""
    bet = {
        "pod_home_team": "Pittsburgh",
        "pod_away_team": "Miami Ohio",
        "home_moneyline_american": None,
        "away_moneyline_american": None,
        "home_spreads": [{"line": "+16.5", "odds": "-110"}],
        "away_spreads": [{"line": "-16.5", "odds": "-110"}],
    }
    pin = _pin_payload(
        "Pittsburgh",
        "Miami Ohio",
        {"-16.5": _spread(-16.5, 1.91, 1.91, "-110", "-110")},
        {},
    )
    rows = analyze_markets_for_ev(bet, pin)
    spreads = [r for r in rows if r.get("market") == "Spread"]
    assert len(spreads) == 2, f"expected priced CFB spreads, got {spreads}"
    home = next(r for r in spreads if r.get("selection") == "Home")
    assert float(home["line"]) == -16.5
    assert home["pinnacle_nvp"] == "-110"
    assert home.get("unmatched_line") is not True
    ev = float(str(home["ev"]).replace("%", ""))
    assert abs(ev) < 1.0
    assert float(bet["home_spreads"][0]["line"]) == 16.5


def test_cfb_home_dog_plus_line_is_not_flipped():
    """Hawaii +3 vs Pin +3 must stay a dog line — do not invert a correct CFB card."""
    bet = {
        "pod_home_team": "Hawaii",
        "pod_away_team": "UNLV",
        "home_spreads": [{"line": "+3", "odds": "-110"}],
        "away_spreads": [{"line": "-3", "odds": "-110"}],
    }
    pin = _pin_payload(
        "Hawaii",
        "UNLV",
        {"3": _spread(3.0, 1.91, 1.91, "-110", "-110")},
        {},
    )
    rows = analyze_markets_for_ev(bet, pin)
    home = next(r for r in rows if r.get("market") == "Spread" and r.get("selection") == "Home")
    assert float(home["line"]) == 3
    assert home["pinnacle_nvp"] == "-110"


def test_align_skips_small_line_when_books_can_disagree():
    home = [{"line": "+1.5", "odds": "-110"}]
    away = [{"line": "-1.5", "odds": "-110"}]
    pin = {"-1.5": _spread(-1.5, 1.91, 1.91, "-110", "-110")}
    flipped = align_bck_spread_signs_to_pin(home, away, pin)
    assert flipped is False
    assert home[0]["line"] == "+1.5"


def test_matching_total_still_computes_ev():
    bet = {
        "pod_home_team": "Dallas Cowboys",
        "pod_away_team": "New Orleans Saints",
        "game_total_line": 37.5,
        "game_total_over_odds": "-110",
        "game_total_under_odds": "-110",
    }
    pin = _pin_payload(
        "Dallas Cowboys",
        "New Orleans Saints",
        {},
        {},
        fg_totals={"37.5": _total(37.5, 1.91, 1.91, "-110", "-110")},
    )
    rows = analyze_markets_for_ev(bet, pin)
    totals = [r for r in rows if r.get("market") == "Total"]
    assert len(totals) == 2
    for r in totals:
        assert r["pinnacle_nvp"] == "-110"
        ev = float(str(r["ev"]).replace("%", ""))
        assert abs(ev) < 1.0
        assert not r.get("unmatched_line")


def test_ev_table_does_not_publish_far_alt():
    from calculate_ev_table import build_ev_spread_rows
    pin = {"0.25": _spread(0.25, 1.2488, 5.02, "-402", "+402")}
    rows = build_ev_spread_rows(
        pin,
        [{"line": "0.25", "odds": "-130"}],
        [{"line": "-0.25", "odds": "+100"}],
        "direct",
        "AS Roma",
        "Fiorentina",
        period_label="1H ",
        sport="soccer",
        event_name="AS Roma vs Fiorentina",
        start_time_fmt="-",
        league="Serie A",
        event_id="3",
        market_suffix="1H",
        meta_limits={},
    )
    assert rows == []


def main():
    tests = [
        test_same_order_home_matches_pin_hdp,
        test_home_plus_does_not_match_opposite_hdp,
        test_reversed_home_plus_uses_pin_away_at_negated_hdp,
        test_opposite_side_prices_rejected,
        test_filter_drops_41_pct_before_publish,
        test_nfl_spread_same_order_still_matches,
        test_roma_1h_reversed_matches_signed_line_not_trap,
        test_alt_line_41_pct_never_published_same_order,
        test_ev_table_uses_orientation_not_exact_names,
        test_ev_table_flipped_orientation_maps_top_to_away,
        test_ev_table_does_not_publish_far_alt,
        test_nacional_asuncion_does_not_show_plus_quarter_at_minus_juice,
        test_wrong_plus_quarter_minus_135_never_publishes_29pct,
        test_preseason_missing_pin_number_shows_unpriced_rows,
        test_pitt_miami_cfb_flipped_signs_match_without_bck_ml,
        test_cfb_home_dog_plus_line_is_not_flipped,
        test_align_skips_small_line_when_books_can_disagree,
        test_matching_total_still_computes_ev,
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
