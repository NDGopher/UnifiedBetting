#!/usr/bin/env python3
"""Signed spread matching: same-order NFL, reversed soccer 1H, no fake 41% EV."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pod_utils import (
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
    assert spread_quotes_are_same_side("-130", "-402") is True
    assert spread_quotes_are_same_side("-130", "+402") is False
    assert spread_quotes_are_same_side("-110", "+100") is True


def test_filter_drops_41_pct_before_publish():
    kept = filter_realistic_ev_bets([
        {"market": "1H Spread", "selection": "Home", "line": "0.25", "ev": "41.65%"},
        {"market": "1H Spread", "selection": "Away", "line": "-0.25", "ev": "-60.14%"},
        {"market": "Total", "selection": "Under", "line": "2.5", "ev": "-2.10%"},
    ])
    assert len(kept) == 1
    assert kept[0]["market"] == "Total"


def _pin_payload(home, away, fg_spreads, h1_spreads):
    return {
        "data": {
            "home": home,
            "away": away,
            "periods": {
                "num_0": {
                    "money_line": {
                        "nvp_home": 1.91,
                        "nvp_away": 1.91,
                        "nvp_american_home": "-110",
                        "nvp_american_away": "-110",
                    },
                    "spreads": fg_spreads,
                },
                "num_1": {
                    "money_line": {},
                    "spreads": h1_spreads,
                },
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
