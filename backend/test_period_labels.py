#!/usr/bin/env python3
"""Football quarters are 1Q; hockey periods stay 1P."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pod_utils import row_type_market_label, _period_unit_letter


def test_football_period_is_quarter():
    assert row_type_market_label("period_1", sport_type="FOOTBALL") == "1Q "
    assert row_type_market_label("period_2", sport_type="FOOTBALL") == "2Q "
    assert row_type_market_label(
        "period_1", period_description="1st Quarter"
    ) == "1Q "


def test_ncaa_football_via_league():
    assert row_type_market_label(
        "period_1", sport_type="FOOTBALL", sport_subtype="NCAA", league_name="NCAA"
    ) == "1Q "


def test_hockey_period_stays_p():
    assert row_type_market_label("period_1", sport_type="HOCKEY") == "1P "
    assert row_type_market_label("period_3", sport_type="HOCKEY") == "3P "
    assert row_type_market_label(
        "period_1", period_description="1st Period"
    ) == "1P "


def test_basketball_quarter():
    assert row_type_market_label("period_1", sport_type="BASKETBALL") == "1Q "


def test_halves_unchanged():
    assert row_type_market_label("half_1", sport_type="FOOTBALL") == "1H "
    assert row_type_market_label("half_2", sport_type="FOOTBALL") == "2H "


def test_description_beats_sport():
    assert _period_unit_letter("hockey", "1st Quarter") == "Q"
    assert _period_unit_letter("football", "1st Period") == "P"


if __name__ == "__main__":
    test_football_period_is_quarter()
    test_ncaa_football_via_league()
    test_hockey_period_stays_p()
    test_basketball_quarter()
    test_halves_unchanged()
    test_description_beats_sport()
    print("test_period_labels: all passed")
